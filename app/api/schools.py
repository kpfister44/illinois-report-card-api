# ABOUTME: Schools endpoint
# ABOUTME: Returns school data for a given year

from fastapi import APIRouter, Depends
from app.dependencies import verify_api_key

router = APIRouter()


@router.get("/schools/{year}")
async def get_schools(year: int, api_key: str = Depends(verify_api_key)):
    """Returns school data for the specified year."""
    # Stub implementation - will return actual data from database later
    return {"data": [], "meta": {"count": 0, "year": year}}
