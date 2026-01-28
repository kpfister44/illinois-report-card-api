# ABOUTME: Years endpoint
# ABOUTME: Returns list of available data years

from fastapi import APIRouter, Depends
from app.dependencies import verify_api_key
from app.models.database import APIKey

router = APIRouter()


@router.get("/years")
async def get_years(api_key: APIKey = Depends(verify_api_key)):
    """Returns list of all available data years."""
    # Stub implementation - will return actual data from database later
    return {"data": [], "meta": {"count": 0}}
