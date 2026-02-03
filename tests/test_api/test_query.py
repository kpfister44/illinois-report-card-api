# ABOUTME: Tests for flexible POST /query endpoint
# ABOUTME: Validates field selection, filtering, sorting, and pagination

import pytest
import hashlib
from app.models.database import APIKey


def test_post_query_executes_flexible_queries_with_field_selection(client):
    """Test #54: POST /query executes flexible queries with field selection."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_key"
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

        # Step 1: Import test schools for year 2025
        # Create schools_2025 table if it doesn't exist
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "student_enrollment", "data_type": "integer"},
            {"column_name": "city", "data_type": "string"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, student_enrollment, city)
            VALUES
                ('05-016-2140-17-2001', 'Test Query School 1', 500, 'Springfield'),
                ('05-016-2140-17-2002', 'Test Query School 2', 300, 'Chicago'),
                ('05-016-2140-17-2003', 'Test Query School 3', 450, 'Naperville')
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated POST request to /query with field selection
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "fields": ["rcdts", "school_name", "student_enrollment"]
        }
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200
    data = response.json()

    # Step 4: Verify each result contains only requested fields
    assert "data" in data
    results = data["data"]
    assert len(results) > 0, "Should have at least some results"

    # Check that each result has exactly the requested fields (plus nothing extra)
    requested_fields = {"rcdts", "school_name", "student_enrollment"}
    for result in results:
        result_fields = set(result.keys())
        assert result_fields == requested_fields, \
            f"Result has unexpected fields. Expected {requested_fields}, got {result_fields}"

    # Step 5: Verify meta includes total, limit, offset
    assert "meta" in data
    meta = data["meta"]
    assert "total" in meta
    assert "limit" in meta
    assert "offset" in meta
    assert isinstance(meta["total"], int)
    assert isinstance(meta["limit"], int)
    assert isinstance(meta["offset"], int)


def test_post_query_supports_equality_filters(client):
    """Test #55: POST /query supports equality filters."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_filters_key"
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

        # Step 1: Import schools in multiple cities
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"},
            {"column_name": "county", "data_type": "string"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data with schools in different cities
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, city, county)
            VALUES
                ('15-016-0001-17-0001', 'Chicago School 1', 'Chicago', 'Cook'),
                ('15-016-0002-17-0002', 'Chicago School 2', 'Chicago', 'Cook'),
                ('15-016-0003-17-0003', 'Chicago School 3', 'Chicago', 'Cook'),
                ('05-016-0004-17-0004', 'Springfield School 1', 'Springfield', 'Sangamon'),
                ('05-016-0005-17-0005', 'Springfield School 2', 'Springfield', 'Sangamon'),
                ('19-016-0006-17-0006', 'Naperville School 1', 'Naperville', 'DuPage')
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated POST to /query with filters: {"city": "Chicago"}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"city": "Chicago"}
        }
    )

    # Step 3: Verify all returned schools are in Chicago
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    results = data["data"]

    assert len(results) > 0, "Should have some Chicago schools"

    for result in results:
        assert "city" in result
        assert result["city"] == "Chicago", f"Expected Chicago, got {result['city']}"

    # Step 4: Verify total matches expected Chicago schools count
    assert "meta" in data
    assert data["meta"]["total"] == 3, f"Expected 3 Chicago schools, got {data['meta']['total']}"
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"


def test_post_query_supports_comparison_operators(client):
    """Test #56: POST /query supports comparison operators (gte, lte, gt, lt)."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_comparison_key"
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

        # Step 1: Import schools with varying enrollment (100, 500, 1000, 2000)
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "enrollment", "data_type": "integer"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data with varying enrollment
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, enrollment)
            VALUES
                ('01-016-0001-17-0001', 'Small School', 100),
                ('02-016-0002-17-0002', 'Medium School', 500),
                ('03-016-0003-17-0003', 'Large School', 1000),
                ('04-016-0004-17-0004', 'Very Large School', 2000)
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send POST with filters: {"enrollment": {"gte": 500}}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"enrollment": {"gte": 500}}
        }
    )

    # Step 3: Verify only schools with enrollment >= 500 returned
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    results = data["data"]

    assert len(results) == 3, f"Expected 3 schools (>=500), got {len(results)}"
    enrollments = [r["enrollment"] for r in results]
    assert all(e >= 500 for e in enrollments), f"All enrollments should be >= 500, got {enrollments}"
    assert set(enrollments) == {500, 1000, 2000}, f"Expected enrollments [500, 1000, 2000], got {enrollments}"

    # Step 4: Send POST with filters: {"enrollment": {"lt": 1000}}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"enrollment": {"lt": 1000}}
        }
    )

    # Step 5: Verify only schools with enrollment < 1000 returned
    assert response.status_code == 200
    data = response.json()
    results = data["data"]

    assert len(results) == 2, f"Expected 2 schools (<1000), got {len(results)}"
    enrollments = [r["enrollment"] for r in results]
    assert all(e < 1000 for e in enrollments), f"All enrollments should be < 1000, got {enrollments}"
    assert set(enrollments) == {100, 500}, f"Expected enrollments [100, 500], got {enrollments}"

    # Step 6: Send POST with filters: {"enrollment": {"gte": 500, "lte": 1500}}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"enrollment": {"gte": 500, "lte": 1500}}
        }
    )

    # Step 7: Verify range filter works correctly
    assert response.status_code == 200
    data = response.json()
    results = data["data"]

    assert len(results) == 2, f"Expected 2 schools (500-1500), got {len(results)}"
    enrollments = [r["enrollment"] for r in results]
    assert all(500 <= e <= 1500 for e in enrollments), f"All enrollments should be 500-1500, got {enrollments}"
    assert set(enrollments) == {500, 1000}, f"Expected enrollments [500, 1000], got {enrollments}"


def test_post_query_supports_in_operator(client):
    """Test #57: POST /query supports IN operator for multiple values."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_in_key"
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

        # Step 1: Import schools in Chicago, Springfield, and Peoria
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data with schools in different cities
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, city)
            VALUES
                ('15-016-0001-17-0001', 'Chicago School 1', 'Chicago'),
                ('15-016-0002-17-0002', 'Chicago School 2', 'Chicago'),
                ('05-016-0003-17-0003', 'Springfield School 1', 'Springfield'),
                ('05-016-0004-17-0004', 'Springfield School 2', 'Springfield'),
                ('19-016-0005-17-0005', 'Peoria School 1', 'Peoria'),
                ('19-016-0006-17-0006', 'Peoria School 2', 'Peoria')
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send POST to /query with filters: {"city": {"in": ["Chicago", "Springfield"]}}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"city": {"in": ["Chicago", "Springfield"]}}
        }
    )

    # Step 3: Verify only schools in Chicago or Springfield returned
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    results = data["data"]

    assert len(results) == 4, f"Expected 4 schools (Chicago + Springfield), got {len(results)}"

    cities = [r["city"] for r in results]
    assert all(c in ["Chicago", "Springfield"] for c in cities), f"All cities should be Chicago or Springfield, got {cities}"

    # Step 4: Verify Peoria schools are excluded
    assert "Peoria" not in cities, "Peoria schools should be excluded"

    # Verify we got both Chicago and Springfield schools
    assert "Chicago" in cities, "Should have Chicago schools"
    assert "Springfield" in cities, "Should have Springfield schools"


def test_post_query_supports_sorting(client):
    """Test #58: POST /query supports sorting."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_sort_key"
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

        # Step 1: Import schools with varying enrollment
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "enrollment", "data_type": "integer"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data with varying enrollment and names
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, enrollment)
            VALUES
                ('01-016-0001-17-0001', 'Zebra School', 300),
                ('02-016-0002-17-0002', 'Apple School', 500),
                ('03-016-0003-17-0003', 'Banana School', 100),
                ('04-016-0004-17-0004', 'Cherry School', 1000)
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send POST to /query with sort: {"field": "enrollment", "order": "desc"}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "sort": {"field": "enrollment", "order": "desc"}
        }
    )

    # Step 3: Verify schools ordered by enrollment descending
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    results = data["data"]

    assert len(results) == 4, f"Expected 4 schools, got {len(results)}"

    enrollments = [r["enrollment"] for r in results]
    assert enrollments == [1000, 500, 300, 100], f"Expected descending order [1000, 500, 300, 100], got {enrollments}"

    # Step 4: Send POST with sort: {"field": "school_name", "order": "asc"}
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "sort": {"field": "school_name", "order": "asc"}
        }
    )

    # Step 5: Verify schools ordered alphabetically ascending
    assert response.status_code == 200
    data = response.json()
    results = data["data"]

    assert len(results) == 4, f"Expected 4 schools, got {len(results)}"

    names = [r["school_name"] for r in results]
    assert names == ["Apple School", "Banana School", "Cherry School", "Zebra School"], \
        f"Expected alphabetical order, got {names}"


def test_post_query_supports_pagination(client):
    """Test #59: POST /query supports pagination with limit and offset."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_pagination_key"
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

        # Step 1: Import 50 test schools
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert 50 test schools
        values = []
        for i in range(1, 51):
            rcdts = f"{i:02d}-016-{i:04d}-17-{i:04d}"
            name = f"Test School {i:02d}"
            city = "TestCity"
            values.append(f"('{rcdts}', '{name}', '{city}')")

        insert_query = text(f"""
            INSERT INTO schools_2025 (rcdts, school_name, city)
            VALUES {', '.join(values)}
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 2: Send POST to /query with limit: 10, offset: 0
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "limit": 10,
            "offset": 0
        }
    )

    # Step 3: Verify 10 results returned
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    results_page1 = data["data"]

    assert len(results_page1) == 10, f"Expected 10 results in first page, got {len(results_page1)}"

    # Extract IDs from first page for overlap checking
    page1_rcdts = [r["rcdts"] for r in results_page1]

    # Step 4: Send POST with limit: 10, offset: 10
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "limit": 10,
            "offset": 10
        }
    )

    # Step 5: Verify next 10 results returned (no overlap)
    assert response.status_code == 200
    data = response.json()
    results_page2 = data["data"]

    assert len(results_page2) == 10, f"Expected 10 results in second page, got {len(results_page2)}"

    # Extract IDs from second page
    page2_rcdts = [r["rcdts"] for r in results_page2]

    # Verify no overlap between pages
    overlap = set(page1_rcdts) & set(page2_rcdts)
    assert len(overlap) == 0, f"Found overlap between pages: {overlap}"

    # Step 6: Verify meta.total reflects actual total count
    assert "meta" in data
    meta = data["meta"]
    assert "total" in meta
    assert meta["total"] == 50, f"Expected total=50, got {meta['total']}"
    assert meta["limit"] == 10, f"Expected limit=10, got {meta['limit']}"
    assert meta["offset"] == 10, f"Expected offset=10, got {meta['offset']}"


def test_post_query_validates_request_body(client):
    """Test #60: POST /query validates request body and returns appropriate errors."""
    from tests.conftest import TestingSessionLocal
    from app.models.database import APIKey

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_validation_key"
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

    finally:
        db.close()

    headers = {"Authorization": f"Bearer {test_key}"}

    # Step 1: Send POST to /query with missing year field
    response = client.post(
        "/query",
        headers=headers,
        json={
            "entity_type": "school"
        }
    )

    # Step 2: Verify response is 422 with validation error
    assert response.status_code == 422, f"Expected 422 for missing year, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "Response should contain validation error details"

    # Step 3: Send POST with invalid entity_type
    response = client.post(
        "/query",
        headers=headers,
        json={
            "year": 2025,
            "entity_type": "invalid_entity"
        }
    )

    # Step 4: Verify response is 400 with validation error
    assert response.status_code == 400, f"Expected 400 for invalid entity_type, got {response.status_code}"
    data = response.json()
    # Response format is {"code": "...", "message": "..."}
    assert "code" in data, "Response should contain error code"
    assert "message" in data, "Response should contain error message"
    assert data["code"] == "INVALID_PARAMETER"

    # Step 7: Send POST with non-existent year
    response = client.post(
        "/query",
        headers=headers,
        json={
            "year": 1900,
            "entity_type": "school"
        }
    )

    # Step 8: Verify 400 error indicating invalid year
    assert response.status_code == 400, f"Expected 400 for non-existent year, got {response.status_code}"
    data = response.json()
    assert "code" in data
    assert "message" in data
    assert data["code"] == "INVALID_PARAMETER"
    # Verify error message mentions year or data not available
    message = data["message"]
    assert "year" in message.lower() or "data" in message.lower()


def test_post_query_prevents_sql_injection(client):
    """Test #62: POST /query prevents SQL injection through filter values."""
    from tests.conftest import TestingSessionLocal, engine
    from sqlalchemy import text
    from app.services.table_manager import create_year_table

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_query_sqli_key"
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

        # Create schools_2025 table with test data
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]
        create_year_table(2025, "schools", schema, engine)

        # Insert test data
        insert_query = text("""
            INSERT INTO schools_2025 (rcdts, school_name, city)
            VALUES
                ('01-016-0001-17-0001', 'Test School 1', 'Chicago'),
                ('02-016-0002-17-0002', 'Test School 2', 'Springfield'),
                ('03-016-0003-17-0003', 'Test School 3', 'Naperville')
        """)
        db.execute(insert_query)
        db.commit()

    finally:
        db.close()

    # Step 1: Send POST to /query with malicious SQL injection in filter value
    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {test_key}"},
        json={
            "year": 2025,
            "entity_type": "school",
            "filters": {"city": "Chicago'; DROP TABLE schools_2025; --"}
        }
    )

    # Step 2: Verify no SQL injection occurs (should return 200, not 500)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    # Step 3: Verify query returns no results or empty array
    # (since no city matches the malicious string exactly)
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 0, "Should return empty results for non-matching city"

    # Step 4: Verify schools_2025 table still exists and has data
    db = TestingSessionLocal()
    try:
        # Verify table exists and has correct data
        check_query = text("SELECT COUNT(*) as count FROM schools_2025")
        result = db.execute(check_query)
        count = result.scalar()

        assert count == 3, f"Table should still have 3 schools, but has {count}"

        # Verify specific test data is intact
        verify_query = text("SELECT city FROM schools_2025 WHERE rcdts = '01-016-0001-17-0001'")
        result = db.execute(verify_query)
        row = result.fetchone()

        assert row is not None, "Test data should still exist"
        assert row[0] == "Chicago", "Test data should be unchanged"

    finally:
        db.close()
