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


def test_get_districts_filters_by_city(client):
    """Test #37: GET /districts/{year} filters by city."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_city_key"
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

        # Step 1: Import districts in multiple cities (Chicago, Springfield, Peoria)
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        districts_data = [
            {
                "rcdts": "15-016-0000-26",
                "district_name": "Chicago Public Schools",
                "city": "Chicago"
            },
            {
                "rcdts": "15-016-0010-26",
                "district_name": "Chicago SD 100",
                "city": "Chicago"
            },
            {
                "rcdts": "46-062-0000-26",
                "district_name": "Springfield SD 186",
                "city": "Springfield"
            },
            {
                "rcdts": "53-078-0000-26",
                "district_name": "Peoria SD 150",
                "city": "Peoria"
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

    # Step 2: Send authenticated GET request to /districts/2025?city=Chicago
    response = client.get(
        "/districts/2025?city=Chicago",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify all returned districts have city equal to Chicago
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 2  # Should have exactly 2 Chicago districts

    for district in data["data"]:
        assert district["city"] == "Chicago"

    # Step 5: Verify districts from other cities are not included
    district_names = [district["district_name"] for district in data["data"]]
    assert "Chicago Public Schools" in district_names
    assert "Chicago SD 100" in district_names
    assert "Springfield SD 186" not in district_names
    assert "Peoria SD 150" not in district_names


def test_get_districts_filters_by_county(client):
    """Test #38: GET /districts/{year} filters by county."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_county_key"
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

        # Step 1: Import districts in multiple counties
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"},
            {"column_name": "county", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        districts_data = [
            {
                "rcdts": "15-016-0000-26",
                "district_name": "Chicago Public Schools",
                "county": "Cook"
            },
            {
                "rcdts": "15-016-0010-26",
                "district_name": "Evanston SD 65",
                "county": "Cook"
            },
            {
                "rcdts": "46-062-0000-26",
                "district_name": "Springfield SD 186",
                "county": "Sangamon"
            },
            {
                "rcdts": "53-078-0000-26",
                "district_name": "Peoria SD 150",
                "county": "Peoria"
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

    # Step 2: Send authenticated GET request to /districts/2025?county=Cook
    response = client.get(
        "/districts/2025?county=Cook",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify all returned districts have county equal to Cook
    data = response.json()
    assert len(data["data"]) == 2

    for district in data["data"]:
        assert district["county"] == "Cook"

    # Step 5: Verify districts from other counties are not included
    district_names = [district["district_name"] for district in data["data"]]
    assert "Chicago Public Schools" in district_names
    assert "Evanston SD 65" in district_names
    assert "Springfield SD 186" not in district_names
    assert "Peoria SD 150" not in district_names


def test_get_districts_supports_field_selection(client):
    """Test #39: GET /districts/{year} supports field selection."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_fields_key"
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

        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"},
            {"column_name": "county", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        data = {
            "rcdts": "15-016-0000-26",
            "district_name": "Chicago Public Schools",
            "city": "Chicago",
            "county": "Cook"
        }

        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), data)
        db.commit()

    finally:
        db.close()

    # Step 1: Send authenticated GET request with fields parameter
    response = client.get(
        "/districts/2025?fields=rcdts,district_name,city",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 200
    assert response.status_code == 200

    # Step 3: Verify each district object only contains requested fields
    data = response.json()
    assert len(data["data"]) > 0

    first_district = data["data"][0]
    assert "rcdts" in first_district
    assert "district_name" in first_district
    assert "city" in first_district

    # Step 4: Verify no other fields are present in the response
    assert "county" not in first_district
    assert "id" not in first_district
    assert "imported_at" not in first_district
    assert len(first_district.keys()) == 3


def test_get_districts_supports_sorting(client):
    """Test #40: GET /districts/{year} supports sorting."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_sorting_key"
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

        # Step 1: Import districts with varying data
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        districts_data = [
            {"rcdts": "01-001-0000-26", "district_name": "Zebra District"},
            {"rcdts": "01-002-0000-26", "district_name": "Apple District"},
            {"rcdts": "01-003-0000-26", "district_name": "Mango District"},
            {"rcdts": "01-004-0000-26", "district_name": "Banana District"}
        ]

        for data in districts_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request with sort=district_name&order=asc
    response = client.get(
        "/districts/2025?sort=district_name&order=asc",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify districts are ordered alphabetically by name ascending
    data = response.json()
    district_names = [district["district_name"] for district in data["data"]]
    assert district_names == ["Apple District", "Banana District", "Mango District", "Zebra District"]

    # Step 5: Send GET request with ?sort=district_name&order=desc
    response = client.get(
        "/districts/2025?sort=district_name&order=desc",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 6: Verify districts are ordered alphabetically descending
    assert response.status_code == 200
    data = response.json()
    district_names = [district["district_name"] for district in data["data"]]
    assert district_names == ["Zebra District", "Mango District", "Banana District", "Apple District"]


def test_get_district_by_rcdts_returns_single_district(client):
    """Test #41: GET /districts/{year}/{district_id} returns single district detail."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_single_district_key"
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

        # Step 1: Import a district with known district_id
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"},
            {"column_name": "county", "data_type": "string"},
            {"column_name": "total_enrollment", "data_type": "integer"}
        ]

        create_year_table(2025, "districts", schema, engine)

        table_name = "districts_2025"
        district_data = {
            "rcdts": "15-016-0000-26",
            "district_name": "Chicago Public Schools",
            "city": "Chicago",
            "county": "Cook",
            "total_enrollment": 355156
        }

        columns = ", ".join(district_data.keys())
        placeholders = ", ".join([f":{k}" for k in district_data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), district_data)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /districts/2025/{district_id}
    response = client.get(
        "/districts/2025/15-016-0000-26",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify response has data object with district details
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], dict)

    # Step 5: Verify all district-level fields are included
    district = data["data"]
    assert district["rcdts"] == "15-016-0000-26"
    assert district["district_name"] == "Chicago Public Schools"
    assert district["city"] == "Chicago"
    assert district["county"] == "Cook"
    assert district["total_enrollment"] == 355156


def test_get_district_by_rcdts_returns_404_for_nonexistent_district(client):
    """Test #42: GET /districts/{year}/{district_id} returns 404 for non-existent district."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_district_404_key"
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

        # Create year table (but don't insert the district we'll query for)
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"}
        ]

        create_year_table(2025, "districts", schema, engine)

    finally:
        db.close()

    # Step 1: Send authenticated GET request to /districts/2025/nonexistent-id
    response = client.get(
        "/districts/2025/nonexistent-id",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 404
    assert response.status_code == 404

    # Step 3: Verify error response has code NOT_FOUND
    data = response.json()
    assert "code" in data
    assert data["code"] == "NOT_FOUND"
    assert "message" in data
    assert "nonexistent-id" in data["message"]


def test_get_districts_returns_400_for_invalid_year(client):
    """Test #41 (feature_list.json): GET /districts/{year} returns 400 for invalid year."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_districts_invalid_year_key"
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

        # Create a valid year table for comparison (2025)
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "district_name", "data_type": "string"}
        ]
        create_year_table(2025, "districts", schema, engine)

    finally:
        db.close()

    # Step 1: Send authenticated GET request to /districts/2030 (non-existent year)
    response = client.get(
        "/districts/2030",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 400
    assert response.status_code == 400

    # Step 3: Verify error response has code INVALID_PARAMETER
    error_data = response.json()
    assert "code" in error_data
    assert error_data["code"] == "INVALID_PARAMETER"

    # Step 4: Verify error message indicates available years
    assert "message" in error_data
    assert "year" in error_data["message"].lower() or "2030" in error_data["message"]
