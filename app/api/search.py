# ABOUTME: Search endpoint
# ABOUTME: Full-text search across all entities

from fastapi import APIRouter, Depends
from app.dependencies import verify_api_key

router = APIRouter()


@router.get("/search")
async def search(q: str, api_key: str = Depends(verify_api_key)):
    """Full-text search for schools, districts, and other entities."""
    # Stub implementation - will use FTS5 search later
    return {"data": [], "meta": {"count": 0, "query": q}}
