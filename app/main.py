# ABOUTME: FastAPI application entry point
# ABOUTME: Configures app, registers routers, and sets up middleware

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import health, years, schema, schools, districts, state, search, admin, query
from app.middleware.logging import UsageLoggingMiddleware

app = FastAPI(
    title="Illinois Report Card API",
    description="REST API for accessing Illinois public school data",
    version="0.1.0",
)

# Add middleware
app.add_middleware(UsageLoggingMiddleware)


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
app.include_router(schema.router)
app.include_router(schools.router)
app.include_router(districts.router)
app.include_router(state.router)
app.include_router(search.router)
app.include_router(query.router)
app.include_router(admin.router)
