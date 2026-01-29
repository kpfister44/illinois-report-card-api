# ABOUTME: Districts endpoint
# ABOUTME: Returns district data for a given year

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text, inspect
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey
from app.services.table_manager import get_year_table, get_available_years

router = APIRouter()


@router.get("/districts/{year}")
async def get_districts(
    year: int,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    fields: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    county: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default="asc"),
    api_key: APIKey = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Returns district data for the specified year with pagination, field selection, filtering, and sorting."""
    # Get the year-partitioned table
    table = get_year_table(year, "districts", db.bind)

    if table is None:
        # Get available years to include in error message
        available_years = get_available_years("districts", db.bind)
        if available_years:
            years_str = ", ".join(str(y) for y in available_years)
            message = f"No data available for year {year}. Available years: {years_str}"
        else:
            message = f"No data available for year {year}. No district data has been imported yet."

        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAMETER", "message": message}
        )

    # Validate sort field if provided
    if sort:
        inspector = inspect(db.bind)
        table_columns = [col["name"] for col in inspector.get_columns(f"districts_{year}")]
        if sort not in table_columns:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_PARAMETER", "message": f"Invalid sort field: {sort}"}
            )

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

    # Build ORDER BY clause
    order_clause = ""
    if sort:
        order_direction = "DESC" if order.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY {sort} {order_direction}"

    # Get total count with filters
    count_query = f"SELECT COUNT(*) as total FROM districts_{year} {where_clause}"
    result = db.execute(text(count_query), query_params)
    total = result.scalar()

    # Get paginated data with field selection, filters, and sorting
    data_query = f"SELECT {select_clause} FROM districts_{year} {where_clause} {order_clause} LIMIT :limit OFFSET :offset"
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


@router.get("/districts/{year}/{rcdts}")
async def get_district_by_rcdts(
    year: int,
    rcdts: str,
    fields: Optional[str] = Query(default=None),
    api_key: APIKey = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Returns a single district by RCDTS code for the specified year."""
    # Get the year-partitioned table
    table = get_year_table(year, "districts", db.bind)

    if table is None:
        # Get available years to include in error message
        available_years = get_available_years("districts", db.bind)
        if available_years:
            years_str = ", ".join(str(y) for y in available_years)
            message = f"No data available for year {year}. Available years: {years_str}"
        else:
            message = f"No data available for year {year}. No district data has been imported yet."

        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAMETER", "message": message}
        )

    # Parse fields parameter
    if fields:
        field_list = [f.strip() for f in fields.split(",")]
        select_clause = ", ".join(field_list)
    else:
        select_clause = "*"
        field_list = None

    # Query for the district by RCDTS
    query = f"SELECT {select_clause} FROM districts_{year} WHERE rcdts = :rcdts"
    result = db.execute(text(query), {"rcdts": rcdts})

    # Get the district record
    row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"District with RCDTS {rcdts} not found for year {year}"}
        )

    # Convert row to dictionary
    columns = result.keys()
    district_data = dict(zip(columns, row))

    # Build meta response
    meta = {
        "year": year,
        "rcdts": rcdts
    }

    # Add fields_returned if field selection was used
    if field_list:
        meta["fields_returned"] = len(field_list)

    return {
        "data": district_data,
        "meta": meta
    }
