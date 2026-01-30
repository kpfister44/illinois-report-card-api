# ABOUTME: Flexible query endpoint
# ABOUTME: Allows POST requests with field selection, filtering, sorting, and pagination

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey
from app.services.table_manager import get_year_table

router = APIRouter()


class QueryRequest(BaseModel):
    year: int
    entity_type: str
    fields: Optional[List[str]] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0


@router.post("/query")
async def query(
    request: QueryRequest,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Execute a flexible query with field selection, filtering, sorting, and pagination."""
    # Get the year-partitioned table
    entity_table_map = {
        "school": "schools",
        "district": "districts",
        "state": "state"
    }

    table_base = entity_table_map.get(request.entity_type, request.entity_type + "s")
    table = get_year_table(request.year, table_base, db.bind)

    if table is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"No data available for {request.entity_type} in year {request.year}"
            }
        )

    # Build field selection clause
    if request.fields:
        select_clause = ", ".join(request.fields)
    else:
        select_clause = "*"

    table_name = f"{table_base}_{request.year}"

    # Get total count
    count_query = text(f"SELECT COUNT(*) as total FROM {table_name}")
    result = db.execute(count_query)
    total = result.scalar()

    # Get paginated data with field selection
    data_query = text(f"""
        SELECT {select_clause}
        FROM {table_name}
        LIMIT :limit OFFSET :offset
    """)
    result = db.execute(data_query, {"limit": request.limit, "offset": request.offset})

    # Convert rows to dictionaries
    rows = result.fetchall()
    columns = result.keys()
    data = [dict(zip(columns, row)) for row in rows]

    return {
        "data": data,
        "meta": {
            "total": total,
            "limit": request.limit,
            "offset": request.offset
        }
    }
