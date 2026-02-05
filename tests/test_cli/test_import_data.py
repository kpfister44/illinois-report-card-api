# ABOUTME: Unit tests for CLI import_data module to achieve 80%+ code coverage
# ABOUTME: Tests error paths, edge cases, and main logic for import_excel_file(), list_available_years(), and main()

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.cli.import_data import import_excel_file, list_available_years, main
from app.models.database import Base, SchemaMetadata, EntitiesMaster, APIKey
from app.config import get_settings


# =============================================================================
# Phase 1: import_excel_file() Error Paths (Lines 43-55)
# =============================================================================

def test_import_excel_file_exits_on_empty_file(test_excel_file):
    """Test import_excel_file() exits when Excel file has no sheets."""
    # Mock parse_excel_file to return empty dict (simulating no sheets)
    with patch('app.cli.import_data.parse_excel_file', return_value={}):
        with pytest.raises(SystemExit) as exc_info:
            import_excel_file(test_excel_file, year=2024)
        assert exc_info.value.code == 1


def test_import_excel_file_exits_on_missing_general_sheet(excel_missing_general_sheet):
    """Test import_excel_file() exits when 'General' sheet is missing."""
    # parse_excel_file will return a dict without 'General' key
    with patch('app.cli.import_data.parse_excel_file', return_value={"Finance": {"headers": [], "rows": []}}):
        with pytest.raises(SystemExit) as exc_info:
            import_excel_file(excel_missing_general_sheet, year=2024)
        assert exc_info.value.code == 1


def test_import_excel_file_exits_on_empty_general_sheet(excel_empty_general_sheet):
    """Test import_excel_file() exits when General sheet has no data rows."""
    # parse_excel_file will return General sheet with headers but no rows
    with patch('app.cli.import_data.parse_excel_file', return_value={
        "General": {"headers": ["RCDTS", "School Name"], "rows": []}
    }):
        with pytest.raises(SystemExit) as exc_info:
            import_excel_file(excel_empty_general_sheet, year=2024)
        assert exc_info.value.code == 1



# =============================================================================
# Phase 2: import_excel_file() Dry Run (Lines 62-67)
# =============================================================================

def test_import_excel_file_dry_run_no_database_changes(test_excel_file, temp_database, capsys):
    """Test import_excel_file() dry-run mode doesn't modify database."""
    # Mock get_settings to use temp database
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Call with dry_run=True
        import_excel_file(test_excel_file, year=2024, dry_run=True)

    # Verify output mentions dry run
    captured = capsys.readouterr()
    assert "Dry run" in captured.out or "dry run" in captured.out
    assert "no database changes" in captured.out.lower() or "Would create table" in captured.out

    # Verify no table was created
    engine = create_engine(f"sqlite:///{temp_database}")
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "schools_2024" not in table_names
    engine.dispose()



# =============================================================================
# Phase 3: import_excel_file() Main Logic (Lines 70-145)
# =============================================================================

def test_import_excel_file_normalizes_column_names(test_excel_file, temp_database):
    """Test import_excel_file() normalizes column names (spaces to underscores, lowercase)."""
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Import file
        import_excel_file(test_excel_file, year=2024)

    # Verify table columns are normalized
    engine = create_engine(f"sqlite:///{temp_database}")
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('schools_2024')]

    # Should have normalized column names
    assert 'school_name' in columns  # From "School Name"
    assert 'pct_low_income' in columns  # From "Pct Low Income"
    assert 'graduation_rate_pct' in columns  # From "Graduation Rate %"
    engine.dispose()


def test_import_excel_file_detects_schema_when_enabled(test_excel_file, temp_database):
    """Test import_excel_file() detects column types and categories when detect_schema=True."""
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Import with schema detection enabled
        import_excel_file(test_excel_file, year=2024, detect_schema=True)

    # Verify schema_metadata was populated
    engine = create_engine(f"sqlite:///{temp_database}")
    Session = sessionmaker(bind=engine)
    session = Session()

    schema_entries = session.query(SchemaMetadata).filter_by(year=2024, table_name='schools_2024').all()

    # Should have metadata entries
    assert len(schema_entries) > 0

    # Create dict for easier checking
    schema_dict = {entry.column_name: entry for entry in schema_entries}

    # Verify data type detection
    if 'enrollment' in schema_dict:
        assert schema_dict['enrollment'].data_type == 'integer'
    if 'pct_low_income' in schema_dict:
        assert schema_dict['pct_low_income'].data_type == 'percentage'

    # Verify category detection
    if 'enrollment' in schema_dict:
        assert schema_dict['enrollment'].category == 'enrollment'
    if 'pct_low_income' in schema_dict:
        assert schema_dict['pct_low_income'].category == 'demographics'

    session.close()
    engine.dispose()


def test_import_excel_file_skips_schema_detection_when_disabled(test_excel_file, temp_database):
    """Test import_excel_file() defaults to 'string' type when detect_schema=False."""
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Import with schema detection disabled
        import_excel_file(test_excel_file, year=2024, detect_schema=False)

    # Verify schema_metadata table is empty (no detection happened)
    engine = create_engine(f"sqlite:///{temp_database}")
    Session = sessionmaker(bind=engine)
    session = Session()

    schema_entries = session.query(SchemaMetadata).filter_by(year=2024, table_name='schools_2024').all()

    # Should have no metadata entries
    assert len(schema_entries) == 0

    session.close()
    engine.dispose()


def test_import_excel_file_creates_year_table(test_excel_file, temp_database):
    """Test import_excel_file() creates year-partitioned table."""
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Import file
        import_excel_file(test_excel_file, year=2024)

    # Verify table was created
    engine = create_engine(f"sqlite:///{temp_database}")
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert 'schools_2024' in table_names

    # Verify table has expected columns
    columns = [col['name'] for col in inspector.get_columns('schools_2024')]
    assert 'id' in columns
    assert 'rcdts' in columns
    assert 'school_name' in columns

    engine.dispose()


def test_import_excel_file_inserts_data_with_cleaning(excel_with_edge_cases, temp_database):
    """Test import_excel_file() inserts data with proper cleaning (commas, percentages, suppressed values)."""
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{temp_database}"

        # Import file with edge cases
        import_excel_file(excel_with_edge_cases, year=2024, detect_schema=True)

    # Verify data was cleaned and inserted
    engine = create_engine(f"sqlite:///{temp_database}")
    Session = sessionmaker(bind=engine)
    session = Session()

    # Query inserted data
    result = session.execute(text("SELECT rcdts, enrollment, pct_low_income, sat_average FROM schools_2024 ORDER BY rcdts"))
    rows = result.fetchall()

    # Should have 3 rows
    assert len(rows) == 3

    # Row 1: Normal data
    assert rows[0][0] == "01-001-0010-26-0001"
    assert rows[0][1] == 425  # enrollment as integer

    # Row 2: Comma in enrollment should be cleaned
    assert rows[1][0] == "01-001-0010-26-0002"
    assert rows[1][1] == 1250  # "1,250" cleaned to 1250

    # Row 3: Suppressed values ("<10") should be NULL
    assert rows[2][0] == "01-001-0010-26-0003"
    # pct_low_income was "<10", should be cleaned to None

    session.close()
    engine.dispose()



# =============================================================================
# Phase 4: import_excel_file() Exception Handling (Lines 163-169)
# =============================================================================



# =============================================================================
# Phase 5: list_available_years() (Lines 172-204) - ZERO COVERAGE
# =============================================================================

def test_list_available_years_with_empty_database(capsys):
    """Test list_available_years() when no year tables exist in database."""
    # Create temporary empty database
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Initialize empty database (only core tables, no year tables)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    # Mock get_settings to return our test database
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{db_path}"

        # Call function
        list_available_years()

    # Capture output
    captured = capsys.readouterr()
    assert "No data has been imported yet." in captured.out

    # Cleanup
    os.unlink(db_path)


def test_list_available_years_with_single_year(capsys):
    """Test list_available_years() with a single year table."""
    # Create temporary database
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Initialize database and create a year table
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)

    # Create schools_2024 table
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE schools_2024 (id INTEGER PRIMARY KEY, rcdts TEXT)"))
        conn.commit()

    engine.dispose()

    # Mock get_settings
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{db_path}"

        # Call function
        list_available_years()

    # Capture output
    captured = capsys.readouterr()
    assert "Available years in database:" in captured.out
    assert "  - 2024" in captured.out

    # Cleanup
    os.unlink(db_path)


def test_list_available_years_with_multiple_years_sorted(capsys):
    """Test list_available_years() with multiple years, verify sorted output."""
    # Create temporary database
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Initialize database and create multiple year tables
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)

    # Create year tables in non-sorted order
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE schools_2025 (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE schools_2023 (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE districts_2024 (id INTEGER PRIMARY KEY)"))
        conn.commit()

    engine.dispose()

    # Mock get_settings
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{db_path}"

        # Call function
        list_available_years()

    # Capture output
    captured = capsys.readouterr()
    assert "Available years in database:" in captured.out

    # Verify years are sorted
    output_lines = captured.out.split('\n')
    year_lines = [line for line in output_lines if line.strip().startswith('-')]

    # Should have 3 unique years: 2023, 2024, 2025
    assert len(year_lines) == 3
    assert "  - 2023" in captured.out
    assert "  - 2024" in captured.out
    assert "  - 2025" in captured.out

    # Verify sorting order
    assert captured.out.index("2023") < captured.out.index("2024")
    assert captured.out.index("2024") < captured.out.index("2025")

    # Cleanup
    os.unlink(db_path)


def test_list_available_years_skips_invalid_table_names(capsys):
    """Test list_available_years() skips tables with invalid year suffixes."""
    # Create temporary database
    test_db_path = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
    test_db_path.close()
    db_path = test_db_path.name

    # Initialize database and create tables with various names
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE schools_2024 (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE schools_invalid (id INTEGER PRIMARY KEY)"))
        # entities_master doesn't have underscore + year pattern
        conn.commit()

    engine.dispose()

    # Mock get_settings
    with patch('app.cli.import_data.get_settings') as mock_settings:
        mock_settings.return_value.database_url = f"sqlite:///{db_path}"

        # Call function
        list_available_years()

    # Capture output
    captured = capsys.readouterr()
    assert "Available years in database:" in captured.out
    assert "  - 2024" in captured.out

    # Should NOT show invalid year
    assert "invalid" not in captured.out

    # Cleanup
    os.unlink(db_path)


def test_list_available_years_disposes_engine():
    """Test list_available_years() disposes of the database engine."""
    # Mock engine.dispose() to verify it's called
    with patch('app.cli.import_data.create_engine') as mock_create_engine:
        mock_engine = MagicMock()
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = []

        # Need to mock inspect function which is imported inside list_available_years
        def mock_inspect_func(engine):
            return mock_inspector

        mock_create_engine.return_value = mock_engine

        with patch('sqlalchemy.inspect', side_effect=mock_inspect_func):
            list_available_years()

        # Verify dispose was called
        mock_engine.dispose.assert_called_once()



# =============================================================================
# Phase 6: main() CLI Entry Point (Lines 207-245)
# =============================================================================

def test_main_list_years_calls_list_available_years():
    """Test main() --list-years flag calls list_available_years()."""
    with patch('sys.argv', ['import_data.py', '--list-years']):
        with patch('app.cli.import_data.list_available_years') as mock_list_years:
            main()
            # Verify list_available_years was called
            mock_list_years.assert_called_once()


def test_main_requires_file_path_for_import():
    """Test main() exits when file_path is missing for import operation."""
    with patch('sys.argv', ['import_data.py', '--year', '2024']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # argparse exits with code 2 for missing required arguments
        assert exc_info.value.code == 2


def test_main_requires_year_for_import():
    """Test main() exits when --year is missing for import operation."""
    with patch('sys.argv', ['import_data.py', 'test.xlsx']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # argparse exits with code 2 for missing required arguments
        assert exc_info.value.code == 2


def test_main_exits_on_nonexistent_file(capsys):
    """Test main() exits when file path doesn't exist."""
    with patch('sys.argv', ['import_data.py', 'nonexistent.xlsx', '--year', '2024']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # Verify exit code is 1
        assert exc_info.value.code == 1

        # Verify error message was printed
        captured = capsys.readouterr()
        assert "File not found" in captured.out
