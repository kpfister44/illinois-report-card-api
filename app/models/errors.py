# ABOUTME: Error response models
# ABOUTME: Pydantic models for API error responses

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response format."""
    code: str
    message: str
    details: dict | None = None
