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
