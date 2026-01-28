# ABOUTME: FastAPI dependency injection utilities
# ABOUTME: Provides database sessions, auth validation, and common dependencies

import hashlib
from datetime import datetime
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Annotated

from app.database import get_db
from app.models.database import APIKey, UsageLog


async def verify_api_key(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db)
) -> APIKey:
    """
    Verify API key from Authorization header.

    Returns the APIKey model if valid.
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

    api_key_str = authorization.replace("Bearer ", "", 1)

    if not api_key_str:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "API key is missing or invalid"}
        )

    # Hash the API key to look it up in the database
    key_hash = hashlib.sha256(api_key_str.encode()).hexdigest()

    # Look up the API key in the database
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not api_key or not api_key.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "API key is missing or invalid"}
        )

    # Update last_used_at
    api_key.last_used_at = datetime.utcnow()

    # Create usage log entry
    usage_log = UsageLog(
        api_key_id=api_key.id,
        endpoint=request.url.path,
        method=request.method,
        status_code=200,  # Will be updated by middleware if different
        ip_address=request.client.host if request.client else None
    )
    db.add(usage_log)
    db.commit()

    return api_key
