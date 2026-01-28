# ABOUTME: FastAPI dependency injection utilities
# ABOUTME: Provides database sessions, auth validation, and common dependencies

from fastapi import Header, HTTPException
from typing import Annotated


async def verify_api_key(authorization: Annotated[str | None, Header()] = None) -> str:
    """
    Verify API key from Authorization header.

    Returns the API key if valid.
    Raises HTTPException with 401 if missing or invalid.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "API key is missing or invalid"}
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "API key is missing or invalid"}
        )

    api_key = authorization.replace("Bearer ", "", 1)

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "API key is missing or invalid"}
        )

    # For now, just return the key without validation
    # Database validation will be added in next iteration
    return api_key
