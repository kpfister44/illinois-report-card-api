# ABOUTME: Search endpoint
# ABOUTME: Full-text search across all entities

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key
from app.database import get_db
from app.models.database import APIKey

router = APIRouter()


def sanitize_fts5_query(query: str) -> str:
    """
    Sanitize a query string for safe use with FTS5 MATCH.

    FTS5 has special characters that can cause syntax errors if not escaped.
    This function wraps the query in double quotes to treat it as a phrase,
    which escapes all special characters.

    Args:
        query: Raw user input query string

    Returns:
        Sanitized query string safe for FTS5 MATCH
    """
    # Remove any existing double quotes to prevent nesting
    query = query.replace('"', '')

    # Wrap in double quotes to treat as a phrase (escapes all special chars)
    return f'"{query}"'


@router.get("/search")
async def search(
    q: str,
    type: str = None,
    year: int = None,
    limit: int = Query(default=10, ge=1),
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Full-text search for schools, districts, and other entities."""
    # Cap limit at 50 (max for search endpoint)
    limit = min(limit, 50)

    # Sanitize query for FTS5
    sanitized_query = sanitize_fts5_query(q)

    # Validate year parameter if provided
    if year:
        # Get all available years from year-partitioned tables
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()

        available_years = set()
        for table_name in table_names:
            if '_' in table_name:
                parts = table_name.split('_')
                if len(parts) == 2:
                    try:
                        year_val = int(parts[1])
                        available_years.add(year_val)
                    except ValueError:
                        continue

        if year not in available_years:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_PARAMETER",
                    "message": f"Invalid year: {year}. Available years: {sorted(available_years, reverse=True)}"
                }
            )

    # Query FTS5 virtual table for full-text search
    # The query searches across name, city, and county fields
    if type:
        # Filter by entity type
        query = text("""
            SELECT rcdts, entity_type, name, city, county
            FROM entities_fts
            WHERE entities_fts MATCH :search_query
            AND entity_type = :entity_type
            ORDER BY rank
            LIMIT :limit
        """)
        result = db.execute(query, {"search_query": sanitized_query, "entity_type": type, "limit": limit})
    else:
        # No type filter
        query = text("""
            SELECT rcdts, entity_type, name, city, county
            FROM entities_fts
            WHERE entities_fts MATCH :search_query
            ORDER BY rank
            LIMIT :limit
        """)
        result = db.execute(query, {"search_query": sanitized_query, "limit": limit})

    rows = result.fetchall()

    # Filter results by year if specified
    if year:
        filtered_rows = []

        # Entity type to table name mapping
        entity_table_map = {
            "school": "schools",
            "district": "districts",
            "state": "state"
        }

        for row in rows:
            rcdts = row[0]
            entity_type = row[1]

            # Get table name for this entity type
            table_base = entity_table_map.get(entity_type, entity_type + "s")
            table_name = f"{table_base}_{year}"

            # Check if entity exists in year table
            try:
                check_query = text(f"SELECT 1 FROM {table_name} WHERE rcdts = :rcdts LIMIT 1")
                exists = db.execute(check_query, {"rcdts": rcdts}).fetchone()
                if exists:
                    filtered_rows.append(row)
            except Exception:
                # Table might not exist for this entity type + year combo
                continue

        rows = filtered_rows

    # Convert rows to dictionaries
    data = [
        {
            "rcdts": row[0],
            "entity_type": row[1],
            "name": row[2],
            "city": row[3],
            "county": row[4]
        }
        for row in rows
    ]

    return {
        "data": data,
        "meta": {
            "total": len(data),
            "limit": limit,
            "query": q
        }
    }
