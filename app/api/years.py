# ABOUTME: Years endpoint
# ABOUTME: Returns list of available data years

from fastapi import APIRouter, Depends
from sqlalchemy import inspect
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey

router = APIRouter()


@router.get("/years")
async def get_years(api_key: APIKey = Depends(verify_api_key), db = Depends(get_db)):
    """Returns list of all available data years."""
    # Query database for all year-partitioned tables
    inspector = inspect(db.bind)
    table_names = inspector.get_table_names()

    # Extract years from table names (format: schools_YYYY, districts_YYYY)
    years = set()
    for table_name in table_names:
        if '_' in table_name:
            parts = table_name.split('_')
            if len(parts) == 2:
                try:
                    year = int(parts[1])
                    years.add(year)
                except ValueError:
                    continue

    # Sort years in descending order (most recent first)
    sorted_years = sorted(years, reverse=True)

    return {
        "data": sorted_years,
        "meta": {"count": len(sorted_years)}
    }
