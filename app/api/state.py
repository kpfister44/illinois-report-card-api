# ABOUTME: State endpoint
# ABOUTME: Returns state-level aggregate data for a given year

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey
from app.models.errors import AUTH_REQUIRED, INVALID_YEAR, NOT_FOUND
from app.services.table_manager import get_year_table, get_available_years

router = APIRouter()


@router.get("/state/{year}", responses={
    200: {"description": "State-level aggregate data", "content": {"application/json": {"example": {
        "data": {"total_students": 1891622, "total_schools": 1542, "avg_reading_score": 45.2},
        "meta": {"year": 2024}
    }}}},
    **INVALID_YEAR, **AUTH_REQUIRED, **NOT_FOUND,
})
async def get_state(
    year: int,
    fields: Optional[str] = Query(default=None),
    api_key: APIKey = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Returns state-level aggregate data for the specified year."""
    # Get the year-partitioned table
    table = get_year_table(year, "state", db.bind)

    if table is None:
        # Get available years to include in error message
        available_years = get_available_years("state", db.bind)
        if available_years:
            years_str = ", ".join(str(y) for y in available_years)
            message = f"No data available for year {year}. Available years: {years_str}"
        else:
            message = f"No data available for year {year}. No state data has been imported yet."

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

    # Query for the state data
    query = f"SELECT {select_clause} FROM state_{year} LIMIT 1"
    result = db.execute(text(query))

    # Get the state record
    row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"No state data found for year {year}"}
        )

    # Convert row to dictionary
    columns = result.keys()
    state_data = dict(zip(columns, row))

    # Build meta response
    meta = {
        "year": year
    }

    # Add fields_returned if field selection was used
    if field_list:
        meta["fields_returned"] = len(field_list)

    return {
        "data": state_data,
        "meta": meta
    }
