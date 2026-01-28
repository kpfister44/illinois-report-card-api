# ABOUTME: Tests for year-partitioned table management service
# ABOUTME: Validates dynamic table creation with different schemas per year

import pytest
from sqlalchemy import inspect, Integer, String, Float, Text
from app.services.table_manager import (
    create_year_table,
    get_year_table,
    table_exists,
)
from app.models.database import SchemaMetadata


def test_create_year_table_for_schools_2024(db_session):
    """Test creating a schools_2024 table with specific schema."""
    # Define schema for 2024
    schema = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
        {"column_name": "white_pct", "data_type": "percentage"},
    ]

    # Create table
    table = create_year_table(
        year=2024,
        entity_type="schools",
        schema=schema,
        engine=db_session.bind
    )

    # Verify table was created
    assert table_exists("schools_2024", db_session.bind)

    # Verify columns
    inspector = inspect(db_session.bind)
    columns = inspector.get_columns("schools_2024")
    column_names = [c["name"] for c in columns]

    assert "id" in column_names
    assert "rcdts" in column_names
    assert "school_name" in column_names
    assert "enrollment" in column_names
    assert "white_pct" in column_names
    assert "imported_at" in column_names


def test_create_year_table_for_schools_2025_with_different_schema(db_session):
    """Test creating a schools_2025 table with a different schema."""
    # Create 2024 table first
    schema_2024 = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
    ]
    create_year_table(2024, "schools", schema_2024, db_session.bind)

    # Create 2025 table with different schema
    schema_2025 = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
        {"column_name": "act_composite", "data_type": "float"},  # New column
        {"column_name": "ell_pct", "data_type": "percentage"},   # New column
    ]
    create_year_table(2025, "schools", schema_2025, db_session.bind)

    # Verify both tables exist
    assert table_exists("schools_2024", db_session.bind)
    assert table_exists("schools_2025", db_session.bind)

    # Verify 2024 columns
    inspector = inspect(db_session.bind)
    columns_2024 = inspector.get_columns("schools_2024")
    column_names_2024 = [c["name"] for c in columns_2024]

    # Verify 2025 columns
    columns_2025 = inspector.get_columns("schools_2025")
    column_names_2025 = [c["name"] for c in columns_2025]

    # Verify schema differences
    assert "act_composite" not in column_names_2024
    assert "ell_pct" not in column_names_2024
    assert "act_composite" in column_names_2025
    assert "ell_pct" in column_names_2025

    # Verify common columns exist in both
    assert "rcdts" in column_names_2024
    assert "rcdts" in column_names_2025
    assert "enrollment" in column_names_2024
    assert "enrollment" in column_names_2025


def test_get_year_table_returns_existing_table(db_session):
    """Test retrieving an existing year table."""
    # Create table
    schema = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
    ]
    created_table = create_year_table(2024, "schools", schema, db_session.bind)

    # Retrieve table
    retrieved_table = get_year_table(2024, "schools", db_session.bind)

    assert retrieved_table is not None
    assert retrieved_table.name == "schools_2024"


def test_table_exists_returns_false_for_nonexistent_table(db_session):
    """Test that table_exists returns False for tables that don't exist."""
    assert not table_exists("schools_2030", db_session.bind)
    assert not table_exists("nonexistent_table", db_session.bind)
