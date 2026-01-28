# ABOUTME: Schema detection utilities for automatic column type and category identification
# ABOUTME: Analyzes column names and data to determine appropriate database types and groupings


def detect_column_type(column_name: str, values: list) -> str:
    """
    Detect the data type of a column based on its name and sample values.

    Args:
        column_name: The normalized column name
        values: List of sample values from the column (may include None)

    Returns:
        One of: 'integer', 'float', 'percentage', 'string'
    """
    # Check if column name indicates percentage
    percentage_indicators = ['pct', 'percent', 'rate']
    if any(indicator in column_name.lower() for indicator in percentage_indicators):
        return "percentage"

    # Filter out None values for type detection
    non_null_values = [v for v in values if v is not None]

    if not non_null_values:
        return "string"  # Default for empty columns

    # Check if all non-null values are integers
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null_values):
        return "integer"

    # Check if all non-null values are numeric (int or float)
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null_values):
        return "float"

    # Default to string
    return "string"


def detect_column_category(column_name: str) -> str:
    """
    Detect the category of a column based on its name.

    Args:
        column_name: The normalized column name

    Returns:
        One of: 'demographics', 'assessment', 'enrollment', 'attendance', 'graduation', 'other'
    """
    name_lower = column_name.lower()

    # Demographics keywords
    demographics_keywords = [
        'white', 'black', 'hispanic', 'asian', 'race', 'ethnicity',
        'economically_disadvantaged', 'low_income', 'poverty',
        'iep', 'special_education', 'disability',
        'ell', 'english_learner', 'lep', 'limited_english',
        'gender', 'male', 'female'
    ]
    if any(keyword in name_lower for keyword in demographics_keywords):
        return "demographics"

    # Assessment keywords
    assessment_keywords = [
        'act', 'sat', 'iar', 'parcc', 'psat',
        'proficient', 'proficiency', 'test', 'exam', 'assessment',
        'score', 'ela', 'math', 'reading', 'writing', 'science'
    ]
    if any(keyword in name_lower for keyword in assessment_keywords):
        return "assessment"

    # Enrollment keywords
    enrollment_keywords = [
        'enrollment', 'student_count', 'students'
    ]
    if any(keyword in name_lower for keyword in enrollment_keywords):
        return "enrollment"

    # Attendance keywords
    attendance_keywords = [
        'attendance', 'truancy', 'absent', 'present'
    ]
    if any(keyword in name_lower for keyword in attendance_keywords):
        return "attendance"

    # Graduation keywords
    graduation_keywords = [
        'graduation', 'graduate', 'dropout', 'cohort'
    ]
    if any(keyword in name_lower for keyword in graduation_keywords):
        return "graduation"

    # Default to other
    return "other"
