# ABOUTME: Authentication tests
# ABOUTME: Verifies API key authentication and authorization behavior

import pytest
import hashlib
from datetime import datetime
from app.models.database import APIKey


def create_test_api_key(db_session, key="test_key_12345", is_active=True, tier="free"):
    """Helper to create a test API key in the database."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key[:8] if len(key) >= 8 else key,
        owner_email="test@example.com",
        owner_name="Test User",
        is_active=is_active,
        rate_limit_tier=tier,
        is_admin=False
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return api_key


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


def test_valid_api_key_allows_access(client):
    """Valid API key should allow access to protected endpoints."""
    # Create a test API key in the database using a fresh session
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        api_key = create_test_api_key(db, key="valid_test_key_123")
        api_key_id = api_key.id
        original_last_used = api_key.last_used_at
        db.commit()  # Ensure it's committed
    finally:
        db.close()

    # Send request with valid API key
    response = client.get("/years", headers={"Authorization": "Bearer valid_test_key_123"})

    # Verify response is successful
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data

    # Verify last_used_at was updated and usage log was created
    db2 = TestingSessionLocal()
    try:
        api_key = db2.query(APIKey).filter(APIKey.id == api_key_id).first()
        assert api_key.last_used_at is not None
        if original_last_used:
            assert api_key.last_used_at > original_last_used

        # Verify usage log was created
        from app.models.database import UsageLog
        usage_log = db2.query(UsageLog).filter(UsageLog.api_key_id == api_key_id).first()
        assert usage_log is not None
        assert usage_log.endpoint == "/years"
        assert usage_log.method == "GET"
        assert usage_log.status_code == 200
    finally:
        db2.close()


def test_invalid_api_key_returns_401(client):
    """Request with invalid API key should return 401."""
    # Send request with invalid API key (not in database)
    response = client.get("/years", headers={"Authorization": "Bearer invalid_key_12345"})

    # Verify response status code is 401
    assert response.status_code == 401

    # Verify error response structure
    data = response.json()
    assert data["code"] == "INVALID_API_KEY"
    assert "API key is missing or invalid" in data["message"]
