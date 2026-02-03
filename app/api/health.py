# ABOUTME: Health check endpoint
# ABOUTME: Returns API health status without authentication

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", responses={
    200: {"description": "API is healthy", "content": {"application/json": {"example": {"status": "ok"}}}}
})
async def health_check():
    """Returns API health status."""
    return {"status": "ok"}
