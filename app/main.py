# ABOUTME: FastAPI application entry point
# ABOUTME: Configures app, registers routers, and sets up middleware

from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="Illinois Report Card API",
    description="REST API for accessing Illinois public school data",
    version="0.1.0",
)

# Register routers
app.include_router(health.router)
