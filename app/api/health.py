# ABOUTME: Health check endpoint
# ABOUTME: Returns API health status without authentication

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Returns API health status."""
    return {"status": "ok"}
