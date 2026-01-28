# ABOUTME: FastAPI application entry point
# ABOUTME: Configures app, registers routers, and sets up middleware

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import health, years, schools, search

app = FastAPI(
    title="Illinois Report Card API",
    description="REST API for accessing Illinois public school data",
    version="0.1.0",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler to format error responses."""
    # If detail is a dict, use it directly (for our custom error format)
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    # Otherwise, wrap it in standard format
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "ERROR", "message": exc.detail}
    )


# Register routers
app.include_router(health.router)
app.include_router(years.router)
app.include_router(schools.router)
app.include_router(search.router)
