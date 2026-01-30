# ABOUTME: Tests for full-text search endpoint
# ABOUTME: Validates FTS5 search functionality across entities

import pytest
import hashlib
from app.models.database import APIKey, EntitiesMaster


def test_get_search_returns_full_text_results(client):
    """Test #47: GET /search returns full-text search results across entities."""
    from tests.conftest import TestingSessionLocal

    # Step 1: Import schools with names Lincoln Elementary, Lincoln High, and Washington Elementary
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "test_search_key_12345"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix="test_sea",
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="standard",
            is_admin=False
        )
        db.add(api_key)

        # Create entities that will be synced to FTS5
        entities = [
            EntitiesMaster(
                rcdts="05-016-2140-17-0001",
                entity_type="school",
                name="Lincoln Elementary",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-17-0002",
                entity_type="school",
                name="Lincoln High School",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-17-0003",
                entity_type="school",
                name="Washington Elementary",
                city="Springfield",
                county="Sangamon"
            )
        ]

        for entity in entities:
            db.add(entity)

        db.commit()
    finally:
        db.close()

    # Step 2: Send authenticated GET request to /search?q=Lincoln
    response = client.get(
        "/search?q=Lincoln",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200
    data = response.json()

    # Step 4: Verify results include both Lincoln schools
    assert "data" in data
    results = data["data"]
    lincoln_schools = [r for r in results if "Lincoln" in r["name"]]
    assert len(lincoln_schools) == 2, f"Expected 2 Lincoln schools, got {len(lincoln_schools)}"

    # Step 5: Verify Washington school is not in results
    washington_schools = [r for r in results if "Washington" in r["name"]]
    assert len(washington_schools) == 0, f"Washington school should not be in results for 'Lincoln' query"

    # Step 6: Verify each result has rcdts, name, city, entity_type
    for result in results:
        assert "rcdts" in result
        assert "name" in result
        assert "city" in result
        assert "entity_type" in result

    # Step 7: Verify meta.total reflects actual match count
    assert "meta" in data
    assert "total" in data["meta"]
    assert data["meta"]["total"] == 2


def test_get_search_filters_by_entity_type(client):
    """Test #48: GET /search filters by entity type."""
    from tests.conftest import TestingSessionLocal

    # Step 1: Import schools and districts with similar names
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "test_search_type_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix="test_typ",
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="standard",
            is_admin=False
        )
        db.add(api_key)

        # Create entities with similar names but different types
        entities = [
            EntitiesMaster(
                rcdts="05-016-2140-17-0001",
                entity_type="school",
                name="Springfield Elementary",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-17-0002",
                entity_type="school",
                name="Springfield High School",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-00-0000",
                entity_type="district",
                name="Springfield School District",
                city="Springfield",
                county="Sangamon"
            )
        ]

        for entity in entities:
            db.add(entity)

        db.commit()
    finally:
        db.close()

    # Step 2: Send authenticated GET request to /search?q=Springfield&type=school
    response = client.get(
        "/search?q=Springfield&type=school",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200
    data = response.json()

    # Step 4: Verify only schools are returned (no districts)
    results = data["data"]
    assert len(results) == 2, f"Expected 2 schools, got {len(results)}"
    for result in results:
        assert result["entity_type"] == "school", f"Expected school, got {result['entity_type']}"

    # Step 5: Send GET request with ?type=district
    response = client.get(
        "/search?q=Springfield&type=district",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 6: Verify only districts are returned
    assert response.status_code == 200
    data = response.json()
    results = data["data"]
    assert len(results) == 1, f"Expected 1 district, got {len(results)}"
    assert results[0]["entity_type"] == "district"


def test_get_search_filters_by_year(client):
    """Test #49: GET /search filters by year."""
    from tests.conftest import TestingSessionLocal, engine
    from app.services.table_manager import create_year_table

    # Step 1: Import data for years 2024 and 2025 with different entities
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "test_search_year_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix="test_yr",
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="standard",
            is_admin=False
        )
        db.add(api_key)

        # Create entities for 2024 (Lincoln schools)
        entities_2024 = [
            EntitiesMaster(
                rcdts="05-016-2140-17-0001",
                entity_type="school",
                name="Lincoln Elementary 2024",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-17-0002",
                entity_type="school",
                name="Lincoln High 2024",
                city="Springfield",
                county="Sangamon"
            )
        ]

        # Create entities for 2025 (Washington schools)
        entities_2025 = [
            EntitiesMaster(
                rcdts="05-016-2140-17-0003",
                entity_type="school",
                name="Washington Elementary 2025",
                city="Springfield",
                county="Sangamon"
            ),
            EntitiesMaster(
                rcdts="05-016-2140-17-0004",
                entity_type="school",
                name="Washington High 2025",
                city="Springfield",
                county="Sangamon"
            )
        ]

        # Add all entities to entities_master
        for entity in entities_2024 + entities_2025:
            db.add(entity)

        db.commit()

        # Create year-partitioned tables for 2024 and 2025
        schema_2024 = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]

        schema_2025 = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "city", "data_type": "string"}
        ]

        # Create tables
        create_year_table(2024, "schools", schema_2024, engine)
        create_year_table(2025, "schools", schema_2025, engine)

        # Insert data into 2024 table
        from sqlalchemy import text
        for entity in entities_2024:
            insert_query = text("""
                INSERT INTO schools_2024 (rcdts, school_name, city)
                VALUES (:rcdts, :name, :city)
            """)
            db.execute(insert_query, {
                "rcdts": entity.rcdts,
                "name": entity.name,
                "city": entity.city
            })

        # Insert data into 2025 table
        for entity in entities_2025:
            insert_query = text("""
                INSERT INTO schools_2025 (rcdts, school_name, city)
                VALUES (:rcdts, :name, :city)
            """)
            db.execute(insert_query, {
                "rcdts": entity.rcdts,
                "name": entity.name,
                "city": entity.city
            })

        db.commit()
    finally:
        db.close()

    # Step 2: Send authenticated GET request to /search?q=Springfield&year=2024
    # NOTE: Searching for "Springfield" will match entities from BOTH years in FTS5
    # The year filter should restrict results to only 2024 entities
    response = client.get(
        "/search?q=Springfield&year=2024",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify only 2024 entities are returned
    assert response.status_code == 200
    data = response.json()
    results = data["data"]
    assert len(results) == 2, f"Expected 2 schools from 2024, got {len(results)}"

    # Verify all results are from 2024 (contain "2024" in name)
    for result in results:
        assert "2024" in result["name"], f"Expected 2024 entity, got {result['name']}"
        assert "2025" not in result["name"], f"2025 entity should not be in 2024 results: {result['name']}"

    # Verify meta.total reflects filtered count
    assert data["meta"]["total"] == 2

    # Step 4: Send GET request with ?year=2025
    response = client.get(
        "/search?q=Springfield&year=2025",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 5: Verify only 2025 entities are returned
    assert response.status_code == 200
    data = response.json()
    results = data["data"]
    assert len(results) == 2, f"Expected 2 schools from 2025, got {len(results)}"

    # Verify all results are from 2025 (contain "2025" in name)
    for result in results:
        assert "2025" in result["name"], f"Expected 2025 entity, got {result['name']}"
        assert "2024" not in result["name"], f"2024 entity should not be in 2025 results: {result['name']}"

    # Verify meta.total reflects filtered count
    assert data["meta"]["total"] == 2


def test_get_search_respects_limit_parameter_with_max_50(client):
    """Test #51: GET /search respects limit parameter with max 50."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_search_limit_key"
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

        # Step 1: Import 100+ schools with Chicago in name or city
        for i in range(100):
            school = EntitiesMaster(
                rcdts=f"15-016-{i:04d}-17-{i:04d}",
                entity_type="school",
                name=f"Chicago School {i}",
                city="Chicago",
                county="Cook"
            )
            db.add(school)

        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /search?q=Chicago
    response = client.get(
        "/search?q=Chicago",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify default limit of 10 is applied
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 10
    assert data["meta"]["limit"] == 10

    # Step 4: Send GET request with ?limit=30
    response = client.get(
        "/search?q=Chicago&limit=30",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 5: Verify exactly 30 results returned
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 30
    assert data["meta"]["limit"] == 30

    # Step 6: Send GET request with ?limit=100
    response = client.get(
        "/search?q=Chicago&limit=100",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 7: Verify results capped at 50 (max limit)
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 50  # Should be capped at 50
    assert data["meta"]["limit"] == 50  # Should show effective limit
