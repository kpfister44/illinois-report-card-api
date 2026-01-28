# ABOUTME: Tests for Excel file parsing
# ABOUTME: Validates reading Report Card Excel files with multiple sheets

import pytest
from pathlib import Path


def test_parse_excel_file_returns_sheets():
    """Excel parser should read file and return dict of sheet data."""
    from app.utils.excel_parser import parse_excel_file

    # Use actual 2024 report card file
    file_path = "data/report-cards/24-RC-Pub-Data-Set.xlsx"

    # Parse the file (limit to first 2 sheets for speed)
    result = parse_excel_file(file_path, sheets=['General'])

    # Verify result structure
    assert isinstance(result, dict)
    assert 'General' in result

    # Verify General sheet data
    general_data = result['General']
    assert 'headers' in general_data
    assert 'rows' in general_data

    # Check headers
    headers = general_data['headers']
    assert isinstance(headers, list)
    assert len(headers) > 0
    assert 'RCDTS' in headers
    assert 'School Name' in headers or 'District' in headers

    # Check rows
    rows = general_data['rows']
    assert isinstance(rows, list)
    assert len(rows) > 0  # Should have at least one row of data

    # Each row should be a dict with column names as keys
    first_row = rows[0]
    assert isinstance(first_row, dict)
    assert 'RCDTS' in first_row


def test_parse_excel_handles_multiple_sheets():
    """Parser should handle multiple sheets."""
    from app.utils.excel_parser import parse_excel_file

    file_path = "data/report-cards/24-RC-Pub-Data-Set.xlsx"

    # Parse multiple sheets
    result = parse_excel_file(file_path, sheets=['General', 'Finance'])

    assert 'General' in result
    assert 'Finance' in result

    # Both should have data
    assert len(result['General']['rows']) > 0
    assert len(result['Finance']['rows']) > 0


def test_parse_excel_handles_empty_cells():
    """Empty cells should be converted to None."""
    from app.utils.excel_parser import parse_excel_file

    file_path = "data/report-cards/24-RC-Pub-Data-Set.xlsx"
    result = parse_excel_file(file_path, sheets=['General'], max_rows=10)

    # Check that at least some values are None (empty cells)
    general_rows = result['General']['rows']

    # Check a district row (should have None for School Name)
    district_row = None
    for row in general_rows:
        if row.get('Type') == 'District':
            district_row = row
            break

    assert district_row is not None, "Should have at least one district row"
    # District rows should have None for School Name
    assert district_row.get('School Name') is None
