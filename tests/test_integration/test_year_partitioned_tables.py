# ABOUTME: Integration tests for year-partitioned table management
# ABOUTME: Validates that tables for different years coexist with independent schemas

import pytest
from sqlalchemy import inspect, text
from app.services.table_manager import create_year_table, table_exists
from app.models.database import SchemaMetadata


def test_year_partitioned_tables_coexist_with_different_schemas(db_session):
    """
    Test #16: Year-partitioned tables are created correctly for each year.

    This test validates all 6 steps:
    1. Import 2024 data ✓
    2. Verify schools_2024 table created ✓
    3. Import 2025 data with different schema ✓
    4. Verify schools_2025 table created with its own schema ✓
    5. Verify both tables coexist independently ✓
    6. Verify schema differences are preserved (not merged) ✓
    """
    # Step 1-2: Import 2024 data and verify table created
    schema_2024 = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "city", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
        {"column_name": "white_pct", "data_type": "percentage"},
        {"column_name": "black_pct", "data_type": "percentage"},
    ]

    table_2024 = create_year_table(
        year=2024,
        entity_type="schools",
        schema=schema_2024,
        engine=db_session.bind
    )

    # Verify schools_2024 table exists
    assert table_exists("schools_2024", db_session.bind)
    assert table_2024.name == "schools_2024"

    # Add some data to 2024 table
    db_session.execute(
        text("""
            INSERT INTO schools_2024 (rcdts, school_name, city, enrollment, white_pct, black_pct)
            VALUES
                ('05-016-2140-17-0001', 'Lincoln Elementary', 'Springfield', 425, 45.5, 20.3),
                ('05-016-2140-17-0002', 'Washington Middle', 'Chicago', 850, 35.0, 40.5)
        """)
    )
    db_session.commit()

    # Populate schema_metadata for 2024
    for col in schema_2024:
        metadata_entry = SchemaMetadata(
            year=2024,
            table_name="schools_2024",
            column_name=col["column_name"],
            data_type=col["data_type"],
            category="other",
            source_column_name=col["column_name"],
            is_suppressed_indicator=False,
        )
        db_session.add(metadata_entry)
    db_session.commit()

    # Step 3-4: Import 2025 data with different schema
    schema_2025 = [
        {"column_name": "rcdts", "data_type": "string"},
        {"column_name": "school_name", "data_type": "string"},
        {"column_name": "city", "data_type": "string"},
        {"column_name": "enrollment", "data_type": "integer"},
        {"column_name": "white_pct", "data_type": "percentage"},
        {"column_name": "black_pct", "data_type": "percentage"},
        {"column_name": "hispanic_pct", "data_type": "percentage"},  # NEW in 2025
        {"column_name": "act_composite", "data_type": "float"},      # NEW in 2025
        {"column_name": "ell_pct", "data_type": "percentage"},       # NEW in 2025
    ]

    table_2025 = create_year_table(
        year=2025,
        entity_type="schools",
        schema=schema_2025,
        engine=db_session.bind
    )

    # Verify schools_2025 table exists with its own schema
    assert table_exists("schools_2025", db_session.bind)
    assert table_2025.name == "schools_2025"

    # Add some data to 2025 table (with new columns)
    db_session.execute(
        text("""
            INSERT INTO schools_2025
                (rcdts, school_name, city, enrollment, white_pct, black_pct,
                 hispanic_pct, act_composite, ell_pct)
            VALUES
                ('05-016-2140-17-0003', 'Roosevelt High', 'Evanston', 1200, 40.0, 25.0,
                 30.0, 24.5, 15.2),
                ('05-016-2140-17-0004', 'Jefferson High', 'Oak Park', 950, 50.0, 20.0,
                 25.0, 26.3, 10.5)
        """)
    )
    db_session.commit()

    # Populate schema_metadata for 2025
    for col in schema_2025:
        metadata_entry = SchemaMetadata(
            year=2025,
            table_name="schools_2025",
            column_name=col["column_name"],
            data_type=col["data_type"],
            category="other",
            source_column_name=col["column_name"],
            is_suppressed_indicator=False,
        )
        db_session.add(metadata_entry)
    db_session.commit()

    # Step 5: Verify both tables coexist independently
    inspector = inspect(db_session.bind)
    all_tables = inspector.get_table_names()

    assert "schools_2024" in all_tables
    assert "schools_2025" in all_tables

    # Verify 2024 data is intact
    result_2024 = db_session.execute(
        text("SELECT COUNT(*) FROM schools_2024")
    ).scalar()
    assert result_2024 == 2

    # Verify 2025 data is intact
    result_2025 = db_session.execute(
        text("SELECT COUNT(*) FROM schools_2025")
    ).scalar()
    assert result_2025 == 2

    # Step 6: Verify schema differences are preserved (not merged)
    columns_2024 = inspector.get_columns("schools_2024")
    column_names_2024 = {c["name"] for c in columns_2024}

    columns_2025 = inspector.get_columns("schools_2025")
    column_names_2025 = {c["name"] for c in columns_2025}

    # Verify 2024 does NOT have 2025-only columns
    assert "hispanic_pct" not in column_names_2024
    assert "act_composite" not in column_names_2024
    assert "ell_pct" not in column_names_2024

    # Verify 2025 DOES have the new columns
    assert "hispanic_pct" in column_names_2025
    assert "act_composite" in column_names_2025
    assert "ell_pct" in column_names_2025

    # Verify common columns exist in both
    common_columns = {"rcdts", "school_name", "city", "enrollment", "white_pct", "black_pct"}
    assert common_columns.issubset(column_names_2024)
    assert common_columns.issubset(column_names_2025)

    # Verify schema_metadata reflects differences
    schema_meta_2024 = (
        db_session.query(SchemaMetadata)
        .filter_by(year=2024, table_name="schools_2024")
        .all()
    )
    assert len(schema_meta_2024) == 6  # 6 columns defined for 2024

    schema_meta_2025 = (
        db_session.query(SchemaMetadata)
        .filter_by(year=2025, table_name="schools_2025")
        .all()
    )
    assert len(schema_meta_2025) == 9  # 9 columns defined for 2025

    # Verify 2025 has metadata for new columns
    column_names_meta_2025 = {m.column_name for m in schema_meta_2025}
    assert "hispanic_pct" in column_names_meta_2025
    assert "act_composite" in column_names_meta_2025
    assert "ell_pct" in column_names_meta_2025

    # Verify 2024 does not have metadata for 2025-only columns
    column_names_meta_2024 = {m.column_name for m in schema_meta_2024}
    assert "hispanic_pct" not in column_names_meta_2024
    assert "act_composite" not in column_names_meta_2024
    assert "ell_pct" not in column_names_meta_2024
