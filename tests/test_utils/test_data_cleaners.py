# ABOUTME: Tests for data cleaning utilities
# ABOUTME: Validates percentage, enrollment, and suppressed value cleaning

import pytest


def test_clean_percentage_converts_string_to_float():
    """Percentage strings like '75.5%' should be converted to float 75.5."""
    from app.utils.data_cleaners import clean_percentage

    # Step 1: Test basic percentage
    assert clean_percentage("75.5%") == 75.5

    # Test edge cases
    assert clean_percentage("100.0%") == 100.0
    assert clean_percentage("0.0%") == 0.0
    assert clean_percentage("50%") == 50.0

    # Test already float/int
    assert clean_percentage(75.5) == 75.5
    assert clean_percentage(100) == 100.0

    # Test None and empty
    assert clean_percentage(None) is None
    assert clean_percentage("") is None

    # Test suppressed value
    assert clean_percentage("*") is None


def test_clean_enrollment_converts_comma_strings_to_int():
    """Enrollment strings like '1,250' should be converted to int 1250."""
    from app.utils.data_cleaners import clean_enrollment

    # Test basic enrollment with commas
    assert clean_enrollment("1,250") == 1250
    assert clean_enrollment("10,500") == 10500
    assert clean_enrollment("125") == 125

    # Test already int/float
    assert clean_enrollment(1250) == 1250
    assert clean_enrollment(1250.0) == 1250

    # Test None and empty
    assert clean_enrollment(None) is None
    assert clean_enrollment("") is None

    # Test suppressed value
    assert clean_enrollment("*") is None


def test_handle_suppressed_returns_none():
    """Asterisk values (*) should be converted to None."""
    from app.utils.data_cleaners import handle_suppressed

    assert handle_suppressed("*") is None
    assert handle_suppressed(" * ") is None
    assert handle_suppressed("**") is None

    # Non-suppressed values pass through
    assert handle_suppressed("75.5") == "75.5"
    assert handle_suppressed(100) == 100
    assert handle_suppressed(None) is None


def test_normalize_column_name():
    """Column names should be normalized to snake_case."""
    from app.utils.data_cleaners import normalize_column_name

    assert normalize_column_name("School Name") == "school_name"
    assert normalize_column_name("Total Enrollment") == "total_enrollment"
    assert normalize_column_name("ACT Composite") == "act_composite"
    assert normalize_column_name("District ID") == "district_id"

    # Handle multiple spaces
    assert normalize_column_name("School  Name") == "school_name"

    # Handle special characters
    assert normalize_column_name("Student/Teacher Ratio") == "student_teacher_ratio"
    assert normalize_column_name("Low-Income %") == "low_income_pct"

    # Already lowercase
    assert normalize_column_name("rcdts") == "rcdts"
