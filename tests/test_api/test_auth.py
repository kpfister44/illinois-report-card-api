# ABOUTME: Authentication tests
# ABOUTME: Verifies API key authentication and authorization behavior

import pytest


def test_unauthenticated_request_to_years_returns_401(client):
    """Requests without Authorization header should return 401."""
    response = client.get("/years")
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "INVALID_API_KEY"


def test_unauthenticated_request_to_schools_returns_401(client):
    """Requests to /schools/{year} without Authorization should return 401."""
    response = client.get("/schools/2025")
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "INVALID_API_KEY"


def test_unauthenticated_request_to_search_returns_401(client):
    """Requests to /search without Authorization should return 401."""
    response = client.get("/search?q=chicago")
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "INVALID_API_KEY"
