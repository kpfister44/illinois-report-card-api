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


def test_get_schools_supports_field_selection(client):
    """Test #25: GET /schools/{year} supports field selection via fields parameter."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_fields_key"
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

        # Create schema for schools_2025 table with multiple fields
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

        # Insert test school
        table_name = "schools_2025"
        data = {
            "rcdts": "01-001-0010-26-2025",
            "school_name": "Test School",
            "city": "Springfield",
            "county": "Sangamon",
            "enrollment": 450,
            "type": "School"
        }
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), data)
        db.commit()

    finally:
        db.close()

    # Step 1: Send authenticated GET request to /schools/2025?fields=rcdts,name,city
    response = client.get(
        "/schools/2025?fields=rcdts,school_name,city",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 200
    assert response.status_code == 200

    # Step 3: Verify each school object only contains rcdts, name, and city fields
    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0

    first_school = data["data"][0]
    assert "rcdts" in first_school
    assert "school_name" in first_school
    assert "city" in first_school

    # Step 4: Verify no other fields are present in the response
    # Should not have id, county, enrollment, type, or imported_at
    assert "county" not in first_school
    assert "enrollment" not in first_school
    assert "type" not in first_school

    # Verify exactly 3 fields (the ones we requested)
    assert len(first_school.keys()) == 3

    # Step 5: Verify meta.fields_returned reflects the count of selected fields
    assert "meta" in data
    assert "fields_returned" in data["meta"]
    assert data["meta"]["fields_returned"] == 3


def test_get_schools_filters_by_city(client):
    """Test #26: GET /schools/{year} filters by city."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_city_filter_key"
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

        # Step 1: Import schools in multiple cities (Chicago, Springfield, Peoria)
        table_name = "schools_2025"
        schools_data = [
            {
                "rcdts": "01-001-0010-26-2025",
                "school_name": "Chicago School 1",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 500,
                "type": "School"
            },
            {
                "rcdts": "01-002-0020-26-2025",
                "school_name": "Chicago School 2",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 600,
                "type": "School"
            },
            {
                "rcdts": "01-003-0030-26-2025",
                "school_name": "Springfield School 1",
                "city": "Springfield",
                "county": "Sangamon",
                "enrollment": 450,
                "type": "School"
            },
            {
                "rcdts": "01-004-0040-26-2025",
                "school_name": "Peoria School 1",
                "city": "Peoria",
                "county": "Peoria",
                "enrollment": 400,
                "type": "School"
            }
        ]

        for data in schools_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schools/2025?city=Chicago
    response = client.get(
        "/schools/2025?city=Chicago",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify all returned schools have city equal to Chicago
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 2  # Should have exactly 2 Chicago schools

    for school in data["data"]:
        assert school["city"] == "Chicago"

    # Step 5: Verify schools from other cities are not included
    school_names = [school["school_name"] for school in data["data"]]
    assert "Chicago School 1" in school_names
    assert "Chicago School 2" in school_names
    assert "Springfield School 1" not in school_names
    assert "Peoria School 1" not in school_names


def test_get_schools_filters_by_county(client):
    """Test #27: GET /schools/{year} filters by county."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_county_filter_key"
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

        # Step 1: Import schools in multiple counties
        table_name = "schools_2025"
        schools_data = [
            {
                "rcdts": "01-001-0010-26-2025",
                "school_name": "Cook County School 1",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 500,
                "type": "School"
            },
            {
                "rcdts": "01-002-0020-26-2025",
                "school_name": "Cook County School 2",
                "city": "Evanston",
                "county": "Cook",
                "enrollment": 600,
                "type": "School"
            },
            {
                "rcdts": "01-003-0030-26-2025",
                "school_name": "Sangamon County School 1",
                "city": "Springfield",
                "county": "Sangamon",
                "enrollment": 450,
                "type": "School"
            },
            {
                "rcdts": "01-004-0040-26-2025",
                "school_name": "DuPage County School 1",
                "city": "Naperville",
                "county": "DuPage",
                "enrollment": 400,
                "type": "School"
            }
        ]

        for data in schools_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schools/2025?county=Cook
    response = client.get(
        "/schools/2025?county=Cook",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify all returned schools have county equal to Cook
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 2  # Should have exactly 2 Cook County schools

    for school in data["data"]:
        assert school["county"] == "Cook"

    # Step 5: Verify schools from other counties are not included
    school_names = [school["school_name"] for school in data["data"]]
    assert "Cook County School 1" in school_names
    assert "Cook County School 2" in school_names
    assert "Sangamon County School 1" not in school_names
    assert "DuPage County School 1" not in school_names


def test_get_schools_filters_by_type(client):
    """Test #28: GET /schools/{year} filters by school type."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_type_filter_key"
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

        # Step 1: Import schools of different types (elementary, middle, high)
        table_name = "schools_2025"
        schools_data = [
            {
                "rcdts": "01-001-0010-26-2025",
                "school_name": "Lincoln Elementary",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 400,
                "type": "elementary"
            },
            {
                "rcdts": "01-002-0020-26-2025",
                "school_name": "Washington Elementary",
                "city": "Springfield",
                "county": "Sangamon",
                "enrollment": 350,
                "type": "elementary"
            },
            {
                "rcdts": "01-003-0030-26-2025",
                "school_name": "Jefferson Middle School",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 600,
                "type": "middle"
            },
            {
                "rcdts": "01-004-0040-26-2025",
                "school_name": "Roosevelt High School",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 1200,
                "type": "high"
            },
            {
                "rcdts": "01-005-0050-26-2025",
                "school_name": "Kennedy High School",
                "city": "Springfield",
                "county": "Sangamon",
                "enrollment": 1100,
                "type": "high"
            }
        ]

        for data in schools_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schools/2025?type=high
    response = client.get(
        "/schools/2025?type=high",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify all returned schools are high schools
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 2  # Should have exactly 2 high schools

    for school in data["data"]:
        assert school["type"] == "high"

    # Step 5: Verify elementary and middle schools are not included
    school_names = [school["school_name"] for school in data["data"]]
    assert "Roosevelt High School" in school_names
    assert "Kennedy High School" in school_names
    assert "Lincoln Elementary" not in school_names
    assert "Washington Elementary" not in school_names
    assert "Jefferson Middle School" not in school_names


def test_get_schools_supports_sorting(client):
    """Test #29: GET /schools/{year} supports sorting with sort and order parameters."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_sorting_key"
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

        # Step 1: Import schools with varying enrollment numbers
        table_name = "schools_2025"
        schools_data = [
            {
                "rcdts": "01-001-0010-26-2025",
                "school_name": "Zebra School",
                "city": "Chicago",
                "county": "Cook",
                "enrollment": 300,
                "type": "School"
            },
            {
                "rcdts": "01-002-0020-26-2025",
                "school_name": "Apple School",
                "city": "Springfield",
                "county": "Sangamon",
                "enrollment": 800,
                "type": "School"
            },
            {
                "rcdts": "01-003-0030-26-2025",
                "school_name": "Mango School",
                "city": "Peoria",
                "county": "Peoria",
                "enrollment": 500,
                "type": "School"
            },
            {
                "rcdts": "01-004-0040-26-2025",
                "school_name": "Banana School",
                "city": "Naperville",
                "county": "DuPage",
                "enrollment": 1200,
                "type": "School"
            }
        ]

        for data in schools_data:
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), data)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schools/2025?sort=enrollment&order=desc
    response = client.get(
        "/schools/2025?sort=enrollment&order=desc",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify schools are ordered by enrollment descending
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 4

    enrollments = [school["enrollment"] for school in data["data"]]
    assert enrollments == [1200, 800, 500, 300]  # Descending order
    assert data["data"][0]["school_name"] == "Banana School"  # Highest enrollment

    # Step 5: Send GET request with ?sort=school_name&order=asc
    response = client.get(
        "/schools/2025?sort=school_name&order=asc",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 6: Verify schools are ordered alphabetically by name ascending
    assert response.status_code == 200
    data = response.json()
    school_names = [school["school_name"] for school in data["data"]]
    assert school_names == ["Apple School", "Banana School", "Mango School", "Zebra School"]

    # Step 7: Send GET request with ?sort=invalid_field
    response = client.get(
        "/schools/2025?sort=invalid_field",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 8: Verify appropriate error response for invalid sort field
    assert response.status_code == 400
    error_data = response.json()
    assert "code" in error_data
    assert error_data["code"] == "INVALID_PARAMETER"
