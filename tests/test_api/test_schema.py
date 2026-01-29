# ABOUTME: Tests for GET /schema endpoints
# ABOUTME: Validates schema metadata retrieval functionality

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey, SchemaMetadata
from app.services.table_manager import create_year_table


def test_get_schema_returns_field_metadata_for_year(client):
    """Test #22: GET /schema/{year} returns field metadata for specified year."""
    from tests.conftest import TestingSessionLocal, engine

    # Step 1: Import 2025 data with schema_metadata populated
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_schema_key"
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

        # Create year table for 2025
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "enrollment", "data_type": "integer"},
            {"column_name": "white_pct", "data_type": "percentage"},
            {"column_name": "low_income_pct", "data_type": "percentage"},
        ]
        create_year_table(2025, "schools", schema, engine)

        # Populate schema_metadata
        metadata_entries = [
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="rcdts",
                data_type="string",
                category="identifier",
                description="Regional County District Type School ID",
                source_column_name="RCDTS",
                is_suppressed_indicator=False
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="school_name",
                data_type="string",
                category="identifier",
                description="School name",
                source_column_name="School Name",
                is_suppressed_indicator=False
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="enrollment",
                data_type="integer",
                category="enrollment",
                description="Total student enrollment",
                source_column_name="Enrollment",
                is_suppressed_indicator=False
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="white_pct",
                data_type="percentage",
                category="demographics",
                description="Percentage of white students",
                source_column_name="White %",
                is_suppressed_indicator=True  # Uses * for suppressed data
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="low_income_pct",
                data_type="percentage",
                category="demographics",
                description="Percentage of low income students",
                source_column_name="Low Income %",
                is_suppressed_indicator=True
            ),
        ]

        for entry in metadata_entries:
            db.add(entry)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schema/2025
    response = client.get(
        "/schema/2025",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    data = response.json()
    assert "data" in data

    # Step 4: Verify response contains array of column metadata objects
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 5

    # Step 5: Verify each metadata object has required fields
    for column_metadata in data["data"]:
        assert "column_name" in column_metadata
        assert "data_type" in column_metadata
        assert "category" in column_metadata
        assert "description" in column_metadata

    # Step 6: Verify source_column_name is included
    rcdts_metadata = next(m for m in data["data"] if m["column_name"] == "rcdts")
    assert "source_column_name" in rcdts_metadata
    assert rcdts_metadata["source_column_name"] == "RCDTS"

    # Step 7: Verify is_suppressed_indicator field is present
    white_pct_metadata = next(m for m in data["data"] if m["column_name"] == "white_pct")
    assert "is_suppressed_indicator" in white_pct_metadata
    assert white_pct_metadata["is_suppressed_indicator"] is True

    enrollment_metadata = next(m for m in data["data"] if m["column_name"] == "enrollment")
    assert enrollment_metadata["is_suppressed_indicator"] is False


def test_get_schema_filters_by_category(client):
    """Test #23: GET /schema/{year}/{category} filters fields by category."""
    from tests.conftest import TestingSessionLocal, engine

    # Step 1: Ensure schema_metadata has columns in multiple categories
    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_category_key"
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

        # Create year table
        schema = [
            {"column_name": "rcdts", "data_type": "string"},
            {"column_name": "school_name", "data_type": "string"},
            {"column_name": "enrollment", "data_type": "integer"},
            {"column_name": "white_pct", "data_type": "percentage"},
            {"column_name": "act_composite", "data_type": "float"},
        ]
        create_year_table(2025, "schools", schema, engine)

        # Populate with multiple categories
        metadata_entries = [
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="rcdts",
                data_type="string",
                category="identifier",
                description="School ID",
                source_column_name="RCDTS",
                is_suppressed_indicator=False
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="enrollment",
                data_type="integer",
                category="enrollment",
                description="Total enrollment",
                source_column_name="Enrollment",
                is_suppressed_indicator=False
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="white_pct",
                data_type="percentage",
                category="demographics",
                description="Percentage white",
                source_column_name="White %",
                is_suppressed_indicator=True
            ),
            SchemaMetadata(
                year=2025,
                table_name="schools_2025",
                column_name="act_composite",
                data_type="float",
                category="assessment",
                description="ACT composite score",
                source_column_name="ACT Composite",
                is_suppressed_indicator=False
            ),
        ]

        for entry in metadata_entries:
            db.add(entry)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /schema/2025/demographics
    response = client.get(
        "/schema/2025/demographics",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    data = response.json()
    assert "data" in data

    # Step 4: Verify all returned fields have category equal to demographics
    assert len(data["data"]) == 1
    for field in data["data"]:
        assert field["category"] == "demographics"

    # Step 5: Verify no fields from other categories are included
    column_names = [f["column_name"] for f in data["data"]]
    assert "white_pct" in column_names
    assert "enrollment" not in column_names  # enrollment category
    assert "act_composite" not in column_names  # assessment category
    assert "rcdts" not in column_names  # identifier category

    # Step 6: Send GET request to /schema/2025/invalid_category
    response = client.get(
        "/schema/2025/invalid_category",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 7: Verify response returns empty array
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 0
