# ABOUTME: Schools endpoint
# ABOUTME: Returns school data for a given year

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey
from app.services.table_manager import get_year_table

router = APIRouter()


@router.get("/schools/{year}")
async def get_schools(
    year: int,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    fields: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    county: Optional[str] = Query(default=None),
    api_key: APIKey = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Returns school data for the specified year with pagination, field selection, and filtering."""
    # Get the year-partitioned table
    table = get_year_table(year, "schools", db.bind)

    if table is None:
        return {"data": [], "meta": {"total": 0, "limit": limit, "offset": offset}}

    # Parse fields parameter
    if fields:
        field_list = [f.strip() for f in fields.split(",")]
        select_clause = ", ".join(field_list)
    else:
        select_clause = "*"
        field_list = None

    # Build WHERE clause for filters
    where_conditions = []
    query_params = {"limit": limit, "offset": offset}

    if city:
        where_conditions.append("city = :city")
        query_params["city"] = city

    if county:
        where_conditions.append("county = :county")
        query_params["county"] = county

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # Get total count with filters
    count_query = f"SELECT COUNT(*) as total FROM schools_{year} {where_clause}"
    result = db.execute(text(count_query), query_params)
    total = result.scalar()

    # Get paginated data with field selection and filters
    data_query = f"SELECT {select_clause} FROM schools_{year} {where_clause} LIMIT :limit OFFSET :offset"
    result = db.execute(text(data_query), query_params)

    # Convert rows to dictionaries
    rows = result.fetchall()
    columns = result.keys()
    data = [dict(zip(columns, row)) for row in rows]

    # Build meta response
    meta = {
        "total": total,
        "limit": limit,
        "offset": offset
    }

    # Add fields_returned if field selection was used
    if field_list:
        meta["fields_returned"] = len(field_list)

    return {
        "data": data,
        "meta": meta
    }
