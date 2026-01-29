# ABOUTME: Search endpoint
# ABOUTME: Full-text search across all entities

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key
from app.database import get_db
from app.models.database import APIKey

router = APIRouter()


@router.get("/search")
async def search(
    q: str,
    type: str = None,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Full-text search for schools, districts, and other entities."""
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
        """)
        result = db.execute(query, {"search_query": q, "entity_type": type})
    else:
        # No type filter
        query = text("""
            SELECT rcdts, entity_type, name, city, county
            FROM entities_fts
            WHERE entities_fts MATCH :search_query
            ORDER BY rank
        """)
        result = db.execute(query, {"search_query": q})

    rows = result.fetchall()

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
            "query": q
        }
    }
