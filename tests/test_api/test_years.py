# ABOUTME: Tests for GET /years endpoint
# ABOUTME: Validates year listing functionality

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey
from app.services.table_manager import create_year_table


def test_get_years_returns_list_of_available_years(client):
    """Test #21: GET /years returns list of all available data years."""
    from tests.conftest import TestingSessionLocal, engine

    # Step 1: Import data for years 2024 and 2025 into the database
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_years_key"
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

        # Create year-partitioned tables for 2024 and 2025
        for year in [2024, 2025]:
            # Create schema
            schema = [
                {"column_name": "rcdts", "data_type": "string"},
                {"column_name": "school_name", "data_type": "string"},
                {"column_name": "city", "data_type": "string"},
                {"column_name": "county", "data_type": "string"},
                {"column_name": "enrollment", "data_type": "integer"},
                {"column_name": "type", "data_type": "string"}
            ]

            # Create year table
            create_year_table(year, "schools", schema, engine)

            # Insert test data
            table_name = f"schools_{year}"
            test_data = [
                {
                    "rcdts": f"01-001-0010-26-{year}",
                    "school_name": f"Test School {year}",
                    "city": "Springfield",
                    "county": "Sangamon",
                    "enrollment": 450,
                    "type": "School"
                },
                {
                    "rcdts": f"01-002-0020-26-{year}",
                    "school_name": f"Another School {year}",
                    "city": "Chicago",
                    "county": "Cook",
                    "enrollment": 850,
                    "type": "School"
                }
            ]

            for data in test_data:
                columns = ", ".join(data.keys())
                placeholders = ", ".join([f":{k}" for k in data.keys()])
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                db.execute(text(sql), data)

            db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /years
    response = client.get(
        "/years",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify response body has data array containing [2024, 2025]
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert 2024 in data["data"]
    assert 2025 in data["data"]

    # Step 5: Verify response body has meta.count equal to 2
    assert "meta" in data
    assert data["meta"]["count"] == 2
