# ABOUTME: Tests for GET /schools/{year} endpoint
# ABOUTME: Validates school listing with pagination functionality

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey
from app.services.table_manager import create_year_table


def test_get_schools_returns_list_with_pagination(client):
    """Test #24: GET /schools/{year} returns list of schools with pagination."""
    from tests.conftest import TestingSessionLocal, engine

    # Step 1: Import test data with at least 150 schools for year 2025
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_schools_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=test_key[:8],
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()

        # Create schema for schools_2025 table
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"},
            {"column_name": "county", "data_type": "string"},
            {"column_name": "enrollment", "data_type": "integer"},
            {"column_name": "type", "data_type": "string"}
        ]

        # Create year table
        create_year_table(2025, "schools", schema, engine)

        # Insert 150 test schools
        table_name = "schools_2025"
        for i in range(150):
            data = {
                "rcdts": f"01-{i:03d}-0010-26-2025",
                "school_name": f"Test School {i+1}",
                "city": "Springfield" if i % 3 == 0 else "Chicago" if i % 3 == 1 else "Naperville",
                "county": "Sangamon" if i % 3 == 0 else "Cook" if i % 3 == 1 else "DuPage",
                "enrollment": 400 + (i * 10),
                "type": "School"
            }
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schools/2025
    response = client.get(
        "/schools/2025",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify response has data array with school objects
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    # Step 5: Verify response has meta with total, limit, and offset
    assert "meta" in data
    assert "total" in data["meta"]
    assert "limit" in data["meta"]
    assert "offset" in data["meta"]

    # Step 6: Verify default limit of 100 is applied (exactly 100 schools returned)
    assert len(data["data"]) == 100
    assert data["meta"]["limit"] == 100

    # Step 7: Verify meta.total reflects actual total count (150+)
    assert data["meta"]["total"] == 150

    # Step 8: Send GET request with ?limit=5&offset=0
    response = client.get(
        "/schools/2025?limit=5&offset=0",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 9: Verify exactly 5 schools returned
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["limit"] == 5
    assert data["meta"]["offset"] == 0

    # Extract IDs from first 5 schools for comparison
    first_five_ids = [school["id"] for school in data["data"]]

    # Step 10: Send GET request with ?limit=5&offset=5
    response = client.get(
        "/schools/2025?limit=5&offset=5",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 11: Verify next 5 schools returned (no overlap with previous)
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["limit"] == 5
    assert data["meta"]["offset"] == 5

    # Verify no overlap with first 5 schools
    second_five_ids = [school["id"] for school in data["data"]]
    assert len(set(first_five_ids) & set(second_five_ids)) == 0
