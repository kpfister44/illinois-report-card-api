# ABOUTME: Tests for GET /districts/{year} endpoint
# ABOUTME: Validates district listing with pagination and filtering functionality

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey
from app.services.table_manager import create_year_table


def test_get_districts_returns_list_with_filtering_and_pagination(client):
    """Test #36: GET /districts/{year} returns list of districts with filtering and pagination."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_key"
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

        # Step 1: Import test data with multiple districts for year 2025
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"},
            {"column_name": "county", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        districts_data = [
            {
                "rcdts": "15-016-0000-26",
                "district_name": "Chicago Public Schools",
                "city": "Chicago",
                "county": "Cook"
            },
            {
                "rcdts": "15-016-0010-26",
                "district_name": "Chicago Heights SD 170",
                "city": "Chicago Heights",
                "county": "Cook"
            },
            {
                "rcdts": "46-062-0000-26",
                "district_name": "Springfield SD 186",
                "city": "Springfield",
                "county": "Sangamon"
            },
            {
                "rcdts": "53-078-0000-26",
                "district_name": "Peoria SD 150",
                "city": "Peoria",
                "county": "Peoria"
            },
            {
                "rcdts": "15-016-0020-26",
                "district_name": "Cicero SD 99",
                "city": "Cicero",
                "county": "Cook"
            },
            {
                "rcdts": "15-016-0030-26",
                "district_name": "Berwyn SD 100",
                "city": "Berwyn",
                "county": "Cook"
            }
        ]

        for data in districts_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /districts/2025
    response = client.get(
        "/districts/2025",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify response has data array with district objects
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 6  # Should have all 6 districts

    # Step 5: Verify response has meta with total, limit, offset
    assert "meta" in data
    assert "total" in data["meta"]
    assert data["meta"]["total"] == 6
    assert "limit" in data["meta"]
    assert "offset" in data["meta"]

    # Step 6: Send GET request with ?city=Chicago
    response = client.get(
        "/districts/2025?city=Chicago",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 7: Verify only Chicago districts are returned
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1  # Only Chicago Public Schools
    assert data["data"][0]["city"] == "Chicago"
    assert data["data"][0]["district_name"] == "Chicago Public Schools"

    # Step 8: Send GET request with ?limit=5&offset=0
    response = client.get(
        "/districts/2025?limit=5&offset=0",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 9: Verify pagination works correctly
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5  # Limited to 5
    assert data["meta"]["limit"] == 5
    assert data["meta"]["offset"] == 0
    assert data["meta"]["total"] == 6  # Total count is still 6
