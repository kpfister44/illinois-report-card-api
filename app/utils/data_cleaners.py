# ABOUTME: Data cleaning utilities for Excel import
# ABOUTME: Handles percentages, enrollment numbers, suppressed values, and column names

import re


def clean_percentage(value):
    """
    Convert percentage strings to floats.

    Examples:
        "75.5%" -> 75.5
        "100%" -> 100.0
        "*" -> None (suppressed)
        None -> None
    """
    if value is None or value == "":
        return None

    # Already a number
    if isinstance(value, (int, float)):
        return float(value)

    # Convert to string and clean
    value_str = str(value).strip()

    # Handle suppressed values
    if value_str == "*":
        return None

    # Remove % sign and convert
    if value_str.endswith("%"):
        value_str = value_str[:-1]

    try:
        return float(value_str)
    except ValueError:
        return None


def clean_enrollment(value):
    """
    Convert enrollment strings (possibly with commas) to integers.

    Examples:
        "1,250" -> 1250
        "10,500" -> 10500
        "*" -> None (suppressed)
    """
    if value is None or value == "":
        return None

    # Already a number
    if isinstance(value, (int, float)):
        return int(value)

    # Convert to string and clean
    value_str = str(value).strip()

    # Handle suppressed values
    if "*" in value_str:
        return None

    # Remove commas
    value_str = value_str.replace(",", "")

    try:
        return int(float(value_str))
    except ValueError:
        return None


def handle_suppressed(value):
    """
    Convert suppressed values (asterisks) to None.

    Examples:
        "*" -> None
        " * " -> None
        "75.5" -> "75.5" (passthrough)
    """
    if value is None:
        return None

    value_str = str(value).strip()

    # Check if it's a suppressed value (contains asterisk)
    if "*" in value_str:
        return None

    return value


def normalize_column_name(name):
    """
    Normalize column names to snake_case.

    Examples:
        "School Name" -> "school_name"
        "Total Enrollment" -> "total_enrollment"
        "Low-Income %" -> "low_income_pct"
    """
    # Convert to lowercase
    name = name.lower()

    # Replace % with pct
    name = name.replace("%", "pct")

    # Replace special characters with underscores
    name = re.sub(r'[/\-\s]+', '_', name)

    # Remove any remaining non-alphanumeric characters
    name = re.sub(r'[^a-z0-9_]', '', name)

    # Replace multiple underscores with single
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    return name
