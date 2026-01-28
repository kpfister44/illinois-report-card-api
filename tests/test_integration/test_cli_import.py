# ABOUTME: Integration tests for CLI data import command
# ABOUTME: Tests import Excel files and verify database changes

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.config import get_settings


@pytest.fixture
def test_excel_file():
    """Create a test Excel file with school data"""
    # Create temporary Excel file
    wb = Workbook()

    # General sheet with school data
    ws = wb.active
    ws.title = "General"

    # Headers
    headers = [
        "RCDTS",
        "School Name",
        "City",
        "County",
        "Type",
        "Enrollment",
        "Pct Low Income",
        "SAT Average",
        "Graduation Rate %"
    ]
    ws.append(headers)

    # Sample data rows
    ws.append([
        "01-001-0010-26-0001",
        "Test Elementary School",
        "Springfield",
        "Sangamon",
        "School",
        "425",
        "45.5%",
        "980",
        "92.3%"
    ])
    ws.append([
        "01-001-0010-26-0002",
        "Test High School",
        "Springfield",
        "Sangamon",
        "School",
        "1,250",
        "38.2%",
        "1150",
        "95.1%"
    ])
    ws.append([
        "01-001-0010-26-0003",
        "Test Middle School",
        "Chicago",
        "Cook",
        "School",
        "650",
        "55.0%",
        "*",
        "88.5%"
    ])

    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False)
    wb.save(temp_file.name)
    temp_file.close()

    yield temp_file.name

    # Cleanup
    os.unlink(temp_file.name)


def test_cli_import_processes_excel_file_correctly(test_excel_file):
    """
    Test #17: CLI import command processes Excel file correctly

    Steps:
    1. Create test Excel file with school data including multiple sheets
    2. Run python -m app.cli.import_data test_file.xlsx --year 2025
    3. Verify command completes successfully
    4. Verify schools_2025 table created and populated
    5. Verify schema_metadata contains column info
    6. Verify entities_master updated
    """
    import subprocess

    # Use a temporary database for this test
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Create database tables
    from sqlalchemy import create_engine
    from app.models.database import Base
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    # Step 1: Test Excel file created by fixture
    assert os.path.exists(test_excel_file)

    # Step 2: Run CLI import command with test database
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    result = subprocess.run(
        [".venv/bin/python", "-m", "app.cli.import_data", test_excel_file, "--year", "2025"],
        cwd="/Users/kyle.pfister/ReportCardAPI",
        capture_output=True,
        text=True,
        env=env
    )

    # Step 3: Verify command completes successfully
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "Import completed successfully" in result.stdout or "successfully" in result.stdout.lower()

    # Connect to database to verify changes
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 4: Verify schools_2025 table created and populated
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schools_2025'")
        table_exists = cursor.fetchone()
        assert table_exists is not None, "schools_2025 table not created"

        cursor.execute("SELECT COUNT(*) FROM schools_2025")
        row_count = cursor.fetchone()[0]
        assert row_count == 3, f"Expected 3 schools, got {row_count}"

        # Verify data was imported correctly
        cursor.execute("SELECT rcdts, school_name, city, enrollment FROM schools_2025 ORDER BY rcdts")
        schools = cursor.fetchall()

        assert schools[0][0] == "01-001-0010-26-0001"
        assert schools[0][1] == "Test Elementary School"
        assert schools[0][2] == "Springfield"
        assert schools[0][3] == 425

        assert schools[1][0] == "01-001-0010-26-0002"
        assert schools[1][1] == "Test High School"
        assert schools[1][3] == 1250  # Comma was cleaned

        # Step 5: Verify schema_metadata contains column info
        cursor.execute("""
            SELECT COUNT(*) FROM schema_metadata
            WHERE year = 2025 AND table_name = 'schools_2025'
        """)
        schema_count = cursor.fetchone()[0]
        assert schema_count > 0, "schema_metadata not populated"

        # Verify specific columns are documented
        cursor.execute("""
            SELECT column_name, data_type, category, source_column_name
            FROM schema_metadata
            WHERE year = 2025 AND table_name = 'schools_2025'
            ORDER BY column_name
        """)
        schema_rows = cursor.fetchall()

        column_names = [row[0] for row in schema_rows]
        assert "rcdts" in column_names
        assert "school_name" in column_names
        assert "enrollment" in column_names
        assert "pct_low_income" in column_names

        # Verify data types detected correctly
        schema_dict = {row[0]: row[1] for row in schema_rows}
        assert schema_dict.get("enrollment") == "integer"
        assert schema_dict.get("pct_low_income") == "percentage"
        assert schema_dict.get("graduation_rate_pct") == "percentage"

        # Step 6: Verify entities_master updated
        cursor.execute("SELECT COUNT(*) FROM entities_master")
        entity_count = cursor.fetchone()[0]
        assert entity_count == 3, f"Expected 3 entities, got {entity_count}"

        cursor.execute("""
            SELECT rcdts, name, city, county, entity_type
            FROM entities_master
            ORDER BY rcdts
        """)
        entities = cursor.fetchall()

        assert entities[0][0] == "01-001-0010-26-0001"
        assert entities[0][1] == "Test Elementary School"
        assert entities[0][2] == "Springfield"
        assert entities[0][3] == "Sangamon"
        assert entities[0][4] == "school"

    finally:
        conn.close()

    # Cleanup test database
    os.unlink(db_path)


def test_cli_import_dry_run_previews_without_modifying_database(test_excel_file):
    """
    Test #18: CLI import --dry-run previews without modifying database

    Steps:
    1. Record current database state
    2. Run python -m app.cli.import_data test_file.xlsx --year 2025 --dry-run
    3. Verify output shows what would be imported
    4. Verify no actual database changes made
    5. Verify schools_2025 table not created or unchanged
    """
    import subprocess

    # Use a temporary database for this test
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Create database tables
    from sqlalchemy import create_engine
    from app.models.database import Base
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    # Step 1: Record current database state
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of tables before dry-run
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_before = {row[0] for row in cursor.fetchall()}

    # Get row counts for existing tables
    table_counts_before = {}
    for table in tables_before:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        table_counts_before[table] = cursor.fetchone()[0]

    conn.close()

    # Step 2: Run CLI import command with --dry-run
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    result = subprocess.run(
        [".venv/bin/python", "-m", "app.cli.import_data", test_excel_file, "--year", "2025", "--dry-run"],
        cwd="/Users/kyle.pfister/ReportCardAPI",
        capture_output=True,
        text=True,
        env=env
    )

    # Step 3: Verify output shows what would be imported
    assert result.returncode == 0, f"Dry run failed: {result.stderr}"
    output = result.stdout.lower()
    assert "dry run" in output, "Output should indicate this is a dry run"
    assert "would create" in output or "would import" in output, "Output should show what would be done"
    assert "schools_2025" in output, "Output should mention the table that would be created"
    assert "3" in result.stdout, "Output should show number of rows that would be imported"

    # Step 4 & 5: Verify no actual database changes made
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of tables after dry-run
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_after = {row[0] for row in cursor.fetchall()}

    # Verify no new tables created
    assert tables_before == tables_after, "Dry run should not create any new tables"
    assert "schools_2025" not in tables_after, "schools_2025 table should not be created in dry-run mode"

    # Verify row counts unchanged
    for table in tables_before:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count_after = cursor.fetchone()[0]
        assert table_counts_before[table] == count_after, f"Row count for {table} should not change in dry-run mode"

    # Verify schema_metadata was not populated
    cursor.execute("SELECT COUNT(*) FROM schema_metadata WHERE year = 2025")
    schema_count = cursor.fetchone()[0]
    assert schema_count == 0, "schema_metadata should not be populated in dry-run mode"

    # Verify entities_master was not populated
    cursor.execute("SELECT COUNT(*) FROM entities_master")
    entity_count = cursor.fetchone()[0]
    assert entity_count == 0, "entities_master should not be populated in dry-run mode"

    conn.close()

    # Cleanup test database
    os.unlink(db_path)
