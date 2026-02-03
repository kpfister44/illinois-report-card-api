# ABOUTME: FastAPI dependency injection utilities
# ABOUTME: Provides database sessions, auth validation, and common dependencies

import hashlib
import time
from datetime import datetime, timedelta, timezone
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

    # Check rate limiting
    rate_limits = {
        "free": 100,
        "standard": 1000,
        "premium": 10000
    }
    rate_limit = rate_limits.get(api_key.rate_limit_tier, 100)
    window_seconds = 60  # 1 minute window

    # Count requests in the current window
    window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    recent_requests = db.query(UsageLog).filter(
        UsageLog.api_key_id == api_key.id,
        UsageLog.timestamp >= window_start
    ).count()

    if recent_requests >= rate_limit:
        # Log the rate-limited request
        usage_log = UsageLog(
            api_key_id=api_key.id,
            endpoint=request.url.path,
            method=request.method,
            status_code=429,
            ip_address=request.client.host if request.client else None
        )
        db.add(usage_log)
        db.commit()

        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMITED",
                "message": f"Rate limit exceeded. Retry after {window_seconds} seconds.",
                "retry_after": window_seconds
            }
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)

    # Store start time for response time calculation
    request.state.request_start_time = time.time()

    # Create usage log entry (will be updated by middleware with accurate status_code and response_time_ms)
    usage_log = UsageLog(
        api_key_id=api_key.id,
        endpoint=request.url.path,
        method=request.method,
        status_code=200,  # Will be updated by middleware
        ip_address=request.client.host if request.client else None
    )
    db.add(usage_log)
    db.commit()
    db.refresh(usage_log)

    # Store usage log ID and database session in request state for middleware
    request.state.usage_log_id = usage_log.id
    request.state.db_for_logging = db

    return api_key
