# ABOUTME: Integration tests for schema detection during import
# ABOUTME: Validates that schema_metadata is correctly populated from Excel data

import pytest
import tempfile
import openpyxl
from sqlalchemy import text
from app.utils.schema_detector import detect_column_type, detect_column_category
from app.utils.excel_parser import parse_excel_file
from app.models.database import SchemaMetadata


@pytest.fixture
def test_excel_with_varied_columns(tmp_path):
    """Create a test Excel file with columns of different types and categories."""
    file_path = tmp_path / "test_schema_detection.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "General"

    # Create headers with different types and categories
    headers = [
        "RCDTS",                          # string
        "School Name",                    # string
        "City",                           # string
        "Total Enrollment",               # integer, enrollment category
        "White Pct",                      # percentage, demographics category
        "Black Pct",                      # percentage, demographics category
        "Hispanic Pct",                   # percentage, demographics category
        "IEP Pct",                        # percentage, demographics category
        "ACT Composite",                  # float, assessment category
        "IAR ELA Proficient Pct",         # percentage, assessment category
        "IAR Math Proficient Pct",        # percentage, assessment category
        "Attendance Rate",                # percentage, attendance category
        "Graduation Rate",                # percentage, graduation category
    ]
    ws.append(headers)

    # Add sample data rows
    ws.append([
        "05-016-2140-17-0001",
        "Lincoln Elementary",
        "Springfield",
        425,        # enrollment
        45.5,       # white %
        20.3,       # black %
        30.2,       # hispanic %
        12.5,       # IEP %
        22.3,       # ACT
        75.5,       # IAR ELA %
        68.7,       # IAR Math %
        94.2,       # attendance %
        None,       # graduation (N/A for elementary)
    ])

    ws.append([
        "05-016-2140-17-0002",
        "Washington High",
        "Chicago",
        1250,       # enrollment
        35.0,       # white %
        40.5,       # black %
        20.5,       # hispanic %
        15.2,       # IEP %
        24.5,       # ACT
        82.3,       # IAR ELA %
        79.1,       # IAR Math %
        91.5,       # attendance %
        88.3,       # graduation %
    ])

    wb.save(file_path)
    return file_path


def test_schema_detection_identifies_column_types_and_categories(
    test_excel_with_varied_columns, db_session
):
    """
    Test #15: Schema detection correctly identifies column types and categories.

    This test validates all 10 steps:
    1. Create Excel file with columns of different types ✓
    2. Include columns from different categories ✓
    3. Parse and detect schema ✓
    4-10. Verify schema_metadata populated correctly ✓
    """
    # Step 1-2: Test Excel file created with varied columns (fixture)

    # Step 3: Parse Excel file
    sheets_data = parse_excel_file(str(test_excel_with_varied_columns))
    assert "General" in sheets_data
    general_sheet = sheets_data["General"]

    # Get column names (headers)
    headers = general_sheet["headers"]
    rows = general_sheet["rows"]

    # Create schema_metadata entries for each column
    year = 2025
    for col_name in headers:
        # Normalize column name
        normalized_name = col_name.lower().replace(" ", "_")

        # Get sample values for this column
        column_values = [row.get(col_name) for row in rows]

        # Detect type and category
        data_type = detect_column_type(normalized_name, column_values)
        category = detect_column_category(normalized_name)

        # Create schema metadata entry
        metadata_entry = SchemaMetadata(
            year=year,
            table_name=f"schools_{year}",
            column_name=normalized_name,
            data_type=data_type,
            category=category,
            description=None,
            source_column_name=col_name,
            is_suppressed_indicator=False,
        )
        db_session.add(metadata_entry)

    db_session.commit()

    # Step 4: Verify integer columns have data_type 'integer'
    enrollment_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="total_enrollment", year=year)
        .first()
    )
    assert enrollment_meta is not None
    assert enrollment_meta.data_type == "integer"

    # Step 5: Verify float columns have data_type 'float'
    act_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="act_composite", year=year)
        .first()
    )
    assert act_meta is not None
    assert act_meta.data_type == "float"

    # Step 6: Verify percentage columns have data_type 'percentage'
    white_pct_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="white_pct", year=year)
        .first()
    )
    assert white_pct_meta is not None
    assert white_pct_meta.data_type == "percentage"

    # Step 7: Verify string columns have data_type 'string'
    city_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="city", year=year)
        .first()
    )
    assert city_meta is not None
    assert city_meta.data_type == "string"

    # Step 8: Verify demographic columns categorized as 'demographics'
    demo_columns = (
        db_session.query(SchemaMetadata)
        .filter_by(category="demographics", year=year)
        .all()
    )
    demo_column_names = {m.column_name for m in demo_columns}
    assert "white_pct" in demo_column_names
    assert "black_pct" in demo_column_names
    assert "hispanic_pct" in demo_column_names
    assert "iep_pct" in demo_column_names

    # Step 9: Verify assessment columns categorized as 'assessment'
    assessment_columns = (
        db_session.query(SchemaMetadata)
        .filter_by(category="assessment", year=year)
        .all()
    )
    assessment_column_names = {m.column_name for m in assessment_columns}
    assert "act_composite" in assessment_column_names
    assert "iar_ela_proficient_pct" in assessment_column_names
    assert "iar_math_proficient_pct" in assessment_column_names

    # Step 10: Verify enrollment columns categorized as 'enrollment'
    enrollment_columns = (
        db_session.query(SchemaMetadata)
        .filter_by(category="enrollment", year=year)
        .all()
    )
    enrollment_column_names = {m.column_name for m in enrollment_columns}
    assert "total_enrollment" in enrollment_column_names

    # Additional verification: attendance and graduation categories
    attendance_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="attendance_rate", year=year)
        .first()
    )
    assert attendance_meta is not None
    assert attendance_meta.category == "attendance"

    graduation_meta = (
        db_session.query(SchemaMetadata)
        .filter_by(column_name="graduation_rate", year=year)
        .first()
    )
    assert graduation_meta is not None
    assert graduation_meta.category == "graduation"

    # Verify source_column_name is preserved
    assert white_pct_meta.source_column_name == "White Pct"
    assert enrollment_meta.source_column_name == "Total Enrollment"
