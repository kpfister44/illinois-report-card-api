# ABOUTME: Response format tests
# ABOUTME: Validates API responses follow consistent JSON structure per spec

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey
from app.services.table_manager import create_year_table


def _setup_test_data(db, key, year=2025):
    """Set up test API key and schools table with sample data."""
    from tests.conftest import engine

    # Create test API key
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key[:8],
        owner_email="format@example.com",
        owner_name="Format Test",
        is_active=True,
        rate_limit_tier="premium",
        is_admin=False
    )
    db.add(api_key)
    db.commit()

    # Create schools table for the year
    schema = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "city", "data_type": "string"},
        {"column_name": "county", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
        {"column_name": "type", "data_type": "string"}
    ]
    create_year_table(year, "schools", schema, engine)

    # Insert sample schools
    table_name = f"schools_{year}"
    for i in range(5):
        data = {
            "rcdts": f"01-{i:03d}-0010-26-{year}",
            "school_name": f"Format Test School {i+1}",
            "city": "Springfield",
            "county": "Sangamon",
            "enrollment": 400 + (i * 50),
            "type": "School"
        }
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), data)

    db.commit()


def test_api_success_responses_follow_consistent_format(client):
    """Test #75: API responses follow consistent JSON format for success."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    test_key = "test_key_success_fmt"
    try:
        _setup_test_data(db, test_key)
    finally:
        db.close()

    auth_header = {"Authorization": f"Bearer {test_key}"}

    # Step 1: Send GET /years and verify structure {data: [...], meta: {...}}
    response = client.get("/years", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data, "GET /years should have 'data' field"
    assert "meta" in data, "GET /years should have 'meta' field"
    assert isinstance(data["data"], list), "GET /years data should be a list"

    # Step 2: Send GET /schools/2025 and verify same structure
    response = client.get("/schools/2025", headers=auth_header)
    assert response.status_code == 200, f"GET /schools/2025 failed: {response.text}"
    data = response.json()
    assert "data" in data, "GET /schools/2025 should have 'data' field"
    assert "meta" in data, "GET /schools/2025 should have 'meta' field"
    assert isinstance(data["data"], list), "GET /schools/2025 data should be a list"

    # Step 3: Send GET /schools/2025/{rcdts} and verify {data: {...}, meta: {...}}
    rcdts = data["data"][0]["rcdts"]
    response = client.get(f"/schools/2025/{rcdts}", headers=auth_header)
    assert response.status_code == 200, f"GET /schools/2025/{rcdts} failed: {response.text}"
    data = response.json()
    assert "data" in data, "GET /schools/2025/{rcdts} should have 'data' field"
    assert "meta" in data, "GET /schools/2025/{rcdts} should have 'meta' field"
    assert isinstance(data["data"], dict), "Single resource data should be a dict"

    # Step 4: Send POST /query and verify consistent structure
    query_body = {
        "year": 2025,
        "entity_type": "school",
        "fields": ["rcdts", "school_name"],
        "limit": 3
    }
    response = client.post("/query", headers=auth_header, json=query_body)
    assert response.status_code == 200, f"POST /query failed: {response.text}"
    data = response.json()
    assert "data" in data, "POST /query should have 'data' field"
    assert "meta" in data, "POST /query should have 'meta' field"

    # Step 5: Verify all responses include appropriate meta fields
    # meta should be a dict with relevant fields for the response type
    response = client.get("/schools/2025", headers=auth_header)
    meta = response.json()["meta"]
    assert isinstance(meta, dict), "meta should be a dict"


def test_api_error_responses_follow_consistent_format(client):
    """Test #76: API responses follow consistent JSON format for errors."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    test_key = "test_key_error_fmt!"
    try:
        _setup_test_data(db, test_key)
    finally:
        db.close()

    auth_header = {"Authorization": f"Bearer {test_key}"}

    # Helper to validate error format (FastAPI HTTPException with detail={code, message})
    # The format is: {"code": "...", "message": "..."} (or nested under "detail")
    def assert_error_format(resp_data):
        """Verify error response has code and message fields."""
        if "error" in resp_data:
            assert "code" in resp_data["error"], f"Error should have 'code': {resp_data}"
            assert "message" in resp_data["error"], f"Error should have 'message': {resp_data}"
        elif "detail" in resp_data:
            detail = resp_data["detail"]
            assert "code" in detail, f"Error detail should have 'code': {resp_data}"
            assert "message" in detail, f"Error detail should have 'message': {resp_data}"
        else:
            assert "code" in resp_data, f"Error should have 'code': {resp_data}"
            assert "message" in resp_data, f"Error should have 'message': {resp_data}"

    # Step 1: Trigger 400 error - request invalid year
    response = client.get("/schools/9999", headers=auth_header)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert_error_format(response.json())

    # Step 2: Trigger 401 error and verify same structure
    response = client.get("/years", headers={"Authorization": "Bearer invalid_key_xyz"})
    assert response.status_code == 401
    assert_error_format(response.json())

    # Step 3: Trigger 403 error - non-admin accessing admin endpoint
    response = client.get("/admin/keys", headers=auth_header)
    assert response.status_code == 403
    assert_error_format(response.json())

    # Step 4: Trigger 404 error - non-existent RCDTS for valid year
    response = client.get("/schools/2025/99-999-9999-99-9999", headers=auth_header)
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    assert_error_format(response.json())

    # Step 5: Trigger 429 error and verify same structure with retry_after
    # Use a separate free key to hit the 100 req/min limit quickly
    db2 = TestingSessionLocal()
    try:
        rate_key = "test_key_rate_limit!"
        key_hash = hashlib.sha256(rate_key.encode()).hexdigest()
        rate_api_key = APIKey(
            key_hash=key_hash,
            key_prefix=rate_key[:8],
            owner_email="rate@example.com",
            owner_name="Rate Test",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db2.add(rate_api_key)
        db2.commit()
    finally:
        db2.close()

    rate_header = {"Authorization": f"Bearer {rate_key}"}
    for _ in range(100):
        client.get("/years", headers=rate_header)

    response = client.get("/years", headers=rate_header)
    assert response.status_code == 429, f"Expected 429, got {response.status_code}"

    # 429 response should have retry_after
    resp_data = response.json()
    if "detail" in resp_data:
        assert "retry_after" in resp_data["detail"], f"429 should have retry_after: {resp_data}"
    elif "error" in resp_data:
        assert "retry_after" in resp_data["error"], f"429 should have retry_after: {resp_data}"
    else:
        assert "retry_after" in resp_data, f"429 should have retry_after: {resp_data}"
