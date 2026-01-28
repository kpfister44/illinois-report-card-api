# ABOUTME: Admin API endpoint tests
# ABOUTME: Verifies admin functionality for key management and imports

import pytest
import hashlib
from app.models.database import APIKey


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
