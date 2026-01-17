# ABOUTME: Pytest fixtures and configuration
# ABOUTME: Provides test database, client, and API key fixtures

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Provides a FastAPI test client."""
    return TestClient(app)
