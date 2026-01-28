# ABOUTME: Admin API endpoint tests
# ABOUTME: Verifies admin functionality for key management and imports

import pytest
import hashlib
from app.models.database import APIKey, UsageLog


def create_admin_api_key(db_session):
    """Helper to create an admin API key for testing admin endpoints."""
    key = "admin_key_12345"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key[:8],
        owner_email="admin@example.com",
        owner_name="Admin User",
        is_active=True,
        rate_limit_tier="premium",
        is_admin=True
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return key  # Return plaintext key for auth


def test_admin_create_api_key_with_hashing(client):
    """Test #7: Admin endpoint creates API key with proper hashing."""
    # Create admin API key
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Create new API key via admin endpoint
    response = client.post(
        "/admin/keys",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={
            "owner_email": "newuser@example.com",
            "owner_name": "New User",
            "rate_limit_tier": "standard",
            "is_admin": False
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert "api_key" in data
    assert "key_prefix" in data

    plaintext_key = data["api_key"]

    # Step 2: Query api_keys table directly
    db2 = TestingSessionLocal()
    try:
        api_key = db2.query(APIKey).filter(APIKey.key_prefix == plaintext_key[:8]).first()
        assert api_key is not None

        # Step 3: Verify key_hash column contains SHA-256 hash (not plaintext)
        expected_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        assert api_key.key_hash == expected_hash
        assert api_key.key_hash != plaintext_key  # Ensure it's not storing plaintext

        # Step 4: Verify key_prefix column contains first 8 characters
        assert api_key.key_prefix == plaintext_key[:8]

    finally:
        db2.close()

    # Step 5: Verify authentication works by hashing provided key and comparing
    response = client.get("/years", headers={"Authorization": f"Bearer {plaintext_key}"})
    assert response.status_code == 200


def test_usage_logging_captures_all_requests(client):
    """Test #8: Usage logging captures all requests accurately."""
    from tests.conftest import TestingSessionLocal

    # Create a test API key
    db = TestingSessionLocal()
    try:
        key = "usage_test_key_123"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key[:8],
            owner_email="usage@example.com",
            owner_name="Usage Test",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        api_key_id = api_key.id
    finally:
        db.close()

    # Step 1: Make authenticated request to any endpoint
    response = client.get("/years", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200

    # Step 2: Query usage_logs table
    db2 = TestingSessionLocal()
    try:
        usage_log = db2.query(UsageLog).filter(UsageLog.api_key_id == api_key_id).first()
        assert usage_log is not None

        # Step 3: Verify entry contains api_key_id, endpoint, method
        assert usage_log.api_key_id == api_key_id
        assert usage_log.endpoint == "/years"
        assert usage_log.method == "GET"

        # Step 4: Verify entry contains status_code, response_time_ms, timestamp
        assert usage_log.status_code == 200
        assert usage_log.response_time_ms is not None
        assert usage_log.response_time_ms >= 0
        assert usage_log.timestamp is not None

        # Step 5: Verify ip_address captured
        assert usage_log.ip_address is not None
    finally:
        db2.close()
