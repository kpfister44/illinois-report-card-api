# ABOUTME: Year-partitioned table management service
# ABOUTME: Creates and manages dynamic SQLAlchemy tables for different report card years

from sqlalchemy import (
    Table, Column, Integer, String, Float, Text, DateTime,
    MetaData, inspect
)
from sqlalchemy.sql import func
from typing import List, Dict, Optional


# Map data types from schema to SQLAlchemy types
TYPE_MAPPING = {
    "integer": Integer,
    "float": Float,
    "percentage": Float,  # Percentages stored as floats
    "string": Text,
}


def create_year_table(
    year: int,
    entity_type: str,
    schema: List[Dict[str, str]],
    engine
) -> Table:
    """
    Create a year-partitioned table for storing entity data.

    Args:
        year: The year for this table (e.g., 2024)
        entity_type: Type of entity (e.g., "schools", "districts", "state")
        schema: List of column definitions with column_name and data_type
        engine: SQLAlchemy engine

    Returns:
        The created SQLAlchemy Table object
    """
    table_name = f"{entity_type}_{year}"
    metadata = MetaData()

    # Define columns
    columns = [
        Column("id", Integer, primary_key=True, autoincrement=True),
    ]

    # Add schema-defined columns
    for col_def in schema:
        col_name = col_def["column_name"]
        data_type = col_def["data_type"]

        # Map to SQLAlchemy type
        sa_type = TYPE_MAPPING.get(data_type, Text)

        # Create column
        columns.append(Column(col_name, sa_type, nullable=True))

    # Add timestamp column
    columns.append(
        Column("imported_at", DateTime, server_default=func.now(), nullable=False)
    )

    # Create table object
    table = Table(table_name, metadata, *columns)

    # Create the table in the database
    metadata.create_all(engine)

    return table


def get_year_table(year: int, entity_type: str, engine) -> Optional[Table]:
    """
    Retrieve an existing year-partitioned table.

    Args:
        year: The year for the table
        entity_type: Type of entity (e.g., "schools", "districts")
        engine: SQLAlchemy engine

    Returns:
        The SQLAlchemy Table object if it exists, None otherwise
    """
    table_name = f"{entity_type}_{year}"

    if not table_exists(table_name, engine):
        return None

    # Reflect the existing table
    metadata = MetaData()
    metadata.reflect(bind=engine, only=[table_name])

    return metadata.tables.get(table_name)


def table_exists(table_name: str, engine) -> bool:
    """
    Check if a table exists in the database.

    Args:
        table_name: Name of the table to check
        engine: SQLAlchemy engine

    Returns:
        True if table exists, False otherwise
    """
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()
