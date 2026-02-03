# ABOUTME: Error response models and OpenAPI response examples
# ABOUTME: Pydantic models for API error responses and shared response schemas

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response format."""
    code: str
    message: str
    details: dict | None = None


def _error_example(code: str, message: str) -> dict:
    """Builds a single OpenAPI response entry with an error example."""
    return {"content": {"application/json": {"example": {"code": code, "message": message}}}}


# Reusable OpenAPI response fragments for route decorators
AUTH_REQUIRED = {
    401: {
        "description": "API key missing or invalid",
        **_error_example("INVALID_API_KEY", "API key is missing or invalid"),
    }
}

ADMIN_REQUIRED = {
    **AUTH_REQUIRED,
    403: {
        "description": "Admin privileges required",
        **_error_example("FORBIDDEN", "Admin privileges required"),
    },
}

NOT_FOUND = {
    404: {
        "description": "Requested resource not found",
        **_error_example("NOT_FOUND", "Resource not found"),
    }
}

INVALID_YEAR = {
    400: {
        "description": "Invalid parameter",
        **_error_example("INVALID_PARAMETER", "No data available for year 2030. Available years: 2024, 2023"),
    }
}
