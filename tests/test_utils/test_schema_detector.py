# ABOUTME: Tests for schema detection utilities
# ABOUTME: Validates automatic column type and category detection from Excel data

import pytest
from app.utils.schema_detector import detect_column_type, detect_column_category


def test_detect_integer_columns():
    """Test that integer columns are correctly identified."""
    # Integer values
    values = [100, 200, 300, None, 400]
    assert detect_column_type("enrollment", values) == "integer"


def test_detect_float_columns():
    """Test that float columns are correctly identified."""
    # Float values
    values = [75.5, 82.3, 91.0, None, 88.7]
    assert detect_column_type("gpa", values) == "float"


def test_detect_percentage_columns():
    """Test that percentage columns are correctly identified."""
    # Percentage values (cleaned)
    values = [75.5, 82.3, 91.0, None, 88.7]
    # Column name indicates percentage
    assert detect_column_type("attendance_rate_pct", values) == "percentage"
    assert detect_column_type("percent_proficient", values) == "percentage"


def test_detect_string_columns():
    """Test that string columns are correctly identified."""
    # String values
    values = ["Chicago", "Springfield", "Evanston", None, "Oak Park"]
    assert detect_column_type("city", values) == "string"


def test_detect_demographics_category():
    """Test that demographic columns are correctly categorized."""
    assert detect_column_category("white_pct") == "demographics"
    assert detect_column_category("black_pct") == "demographics"
    assert detect_column_category("hispanic_pct") == "demographics"
    assert detect_column_category("asian_pct") == "demographics"
    assert detect_column_category("economically_disadvantaged_pct") == "demographics"
    assert detect_column_category("iep_pct") == "demographics"
    assert detect_column_category("ell_pct") == "demographics"


def test_detect_assessment_category():
    """Test that assessment columns are correctly categorized."""
    assert detect_column_category("act_composite") == "assessment"
    assert detect_column_category("sat_total") == "assessment"
    assert detect_column_category("iar_ela_proficient_pct") == "assessment"
    assert detect_column_category("iar_math_proficient_pct") == "assessment"
    assert detect_column_category("proficiency_rate") == "assessment"


def test_detect_enrollment_category():
    """Test that enrollment columns are correctly categorized."""
    assert detect_column_category("enrollment") == "enrollment"
    assert detect_column_category("total_enrollment") == "enrollment"
    assert detect_column_category("student_count") == "enrollment"


def test_detect_attendance_category():
    """Test that attendance columns are correctly categorized."""
    assert detect_column_category("attendance_rate") == "attendance"
    assert detect_column_category("chronic_truancy_pct") == "attendance"


def test_detect_graduation_category():
    """Test that graduation columns are correctly categorized."""
    assert detect_column_category("graduation_rate") == "graduation"
    assert detect_column_category("four_year_cohort_graduation_rate") == "graduation"
    assert detect_column_category("dropout_rate") == "graduation"


def test_detect_other_category():
    """Test that unknown columns default to 'other' category."""
    assert detect_column_category("random_field_xyz") == "other"
    assert detect_column_category("unknown") == "other"
