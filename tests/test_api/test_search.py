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
