# ABOUTME: Logging middleware for request/response tracking
# ABOUTME: Captures response times and updates usage logs

import time
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import SessionLocal
from app.models.database import UsageLog


class UsageLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request/response metrics and update usage logs.

    This middleware captures:
    - Response time in milliseconds
    - Actual response status code
    - Updates the usage log entry created during authentication
    """

    async def dispatch(self, request: Request, call_next):
        # Process the request
        response = await call_next(request)

        # If there's a usage log attached to the request (from verify_api_key),
        # update it with accurate timing and status code
        if hasattr(request.state, "usage_log_id") and hasattr(request.state, "request_start_time"):
            # Calculate response time
            response_time_ms = int((time.time() - request.state.request_start_time) * 1000)

            # Get the database session from request state (created in verify_api_key)
            if hasattr(request.state, "db_for_logging"):
                db = request.state.db_for_logging
                try:
                    # Find and update the specific usage log entry
                    usage_log = db.query(UsageLog).filter(
                        UsageLog.id == request.state.usage_log_id
                    ).first()

                    if usage_log:
                        usage_log.status_code = response.status_code
                        usage_log.response_time_ms = response_time_ms
                        db.commit()
                except Exception:
                    # Don't let logging errors break the request
                    pass

        return response
