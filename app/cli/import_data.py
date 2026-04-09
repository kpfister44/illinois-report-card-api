# ABOUTME: CLI command for importing Excel data files into year-partitioned tables
# ABOUTME: Handles schema detection, data cleaning, and database population

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any

# Maps the "Type" column value to (table_prefix, entities_master entity_type)
ENTITY_TYPE_MAP = {
    "School": ("schools", "school"),
    "District": ("districts", "district"),
    "Statewide": ("state", "state"),
}

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.database import Base, SchemaMetadata, EntitiesMaster
from app.utils.excel_parser import parse_excel_file
from app.utils.schema_detector import detect_column_type, detect_column_category
from app.utils.data_cleaners import (
    clean_percentage,
    clean_enrollment,
    handle_suppressed,
    normalize_column_name
)
from app.services.table_manager import create_year_table


def import_excel_file(file_path: str, year: int, dry_run: bool = False, detect_schema: bool = True) -> None:
    """
    Import Excel file into year-partitioned table.

    Args:
        file_path: Path to Excel file
        year: Year for partitioned table
        dry_run: If True, preview without database changes
        detect_schema: If True, auto-detect column types and categories
    """
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)

    # Parse Excel file
    print(f"Parsing Excel file: {file_path}")
    sheets = parse_excel_file(file_path)

    if not sheets:
        print("Error: No data found in Excel file")
        sys.exit(1)

    # Get General sheet (primary data)
    general_sheet = sheets.get("General")
    if not general_sheet:
        print("Error: No 'General' sheet found in Excel file")
        sys.exit(1)

    if not general_sheet["rows"]:
        print("Error: No data rows found in General sheet")
        sys.exit(1)

    headers = general_sheet["headers"]
    rows = general_sheet["rows"]

    print(f"Found {len(rows)} rows with {len(headers)} columns")

    # Determine entity grouping based on presence of "Type" column
    if "Type" in headers:
        # 2018+ format: split rows by entity type
        entity_groups: Dict[str, List[Dict]] = {}
        for row_dict in rows:
            type_val = row_dict.get("Type", "School")
            if type_val in ENTITY_TYPE_MAP:
                entity_groups.setdefault(type_val, []).append(row_dict)
    else:
        # 2010-2017 format: all rows are schools
        entity_groups = {"School": rows}

    if dry_run:
        tables = [f"{ENTITY_TYPE_MAP[t][0]}_{year}" for t in entity_groups]
        print("\nDry run - no database changes will be made")
        print(f"Would create table: {', '.join(tables)}")
        print(f"Would import {len(rows)} rows")
        print(f"Columns: {', '.join(headers[:10])}...")
        return

    # Normalize column names and detect schema (shared across all entity types)
    normalized_headers = [normalize_column_name(h) for h in headers]

    col_schema: Dict[str, Dict] = {}
    schema_list = []
    for i, header in enumerate(headers):
        normalized_header = normalized_headers[i]
        sample_values = [row.get(header) for row in rows if row.get(header) is not None]
        data_type = detect_column_type(header, sample_values) if detect_schema else "string"
        category = detect_column_category(normalized_header) if detect_schema else "other"

        col_schema[normalized_header] = {
            "data_type": data_type,
            "category": category,
            "source_column_name": header,
        }
        schema_list.append({"column_name": normalized_header, "data_type": data_type})

    # Create all tables before opening a session (avoids SQLite lock contention)
    for type_val in entity_groups:
        table_prefix, _ = ENTITY_TYPE_MAP[type_val]
        table_name = f"{table_prefix}_{year}"
        print(f"Creating table: {table_name}")
        create_year_table(year, table_prefix, schema_list, engine)

    session = Session()
    try:
        for type_val, group_rows in entity_groups.items():
            table_prefix, master_entity_type = ENTITY_TYPE_MAP[type_val]
            table_name = f"{table_prefix}_{year}"


            print(f"Inserting {len(group_rows)} rows into {table_name}...")
            for row_dict in group_rows:
                row_data = {}
                for i, original_header in enumerate(headers):
                    normalized_header = normalized_headers[i]
                    value = row_dict.get(original_header)
                    data_type = col_schema[normalized_header]["data_type"]

                    if data_type == "percentage":
                        row_data[normalized_header] = clean_percentage(value)
                    elif data_type == "integer":
                        cleaned = clean_enrollment(value)
                        row_data[normalized_header] = cleaned if cleaned is not None else handle_suppressed(value)
                    elif data_type == "float":
                        cleaned = clean_percentage(value) if isinstance(value, str) and "%" in value else value
                        row_data[normalized_header] = cleaned if cleaned is not None else handle_suppressed(value)
                    else:
                        row_data[normalized_header] = handle_suppressed(value)

                columns = ", ".join(row_data.keys())
                placeholders = ", ".join([f":{k}" for k in row_data.keys()])
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                session.execute(text(sql), row_data)

                if "rcdts" in row_data and row_data["rcdts"]:
                    entity = session.query(EntitiesMaster).filter_by(rcdts=row_data["rcdts"]).first()
                    if not entity:
                        name = row_data.get("school_name") or row_data.get("district", "")
                        entity = EntitiesMaster(
                            rcdts=row_data["rcdts"],
                            entity_type=master_entity_type,
                            name=name,
                            city=row_data.get("city", ""),
                            county=row_data.get("county", ""),
                        )
                        session.add(entity)

            if detect_schema:
                print("Populating schema metadata...")
                for column_name, column_info in col_schema.items():
                    metadata_entry = SchemaMetadata(
                        year=year,
                        table_name=table_name,
                        column_name=column_name,
                        data_type=column_info["data_type"],
                        category=column_info["category"],
                        source_column_name=column_info["source_column_name"],
                    )
                    session.add(metadata_entry)

        session.commit()
        total = sum(len(g) for g in entity_groups.values())
        print(f"Import completed successfully! Imported {total} rows")

    except Exception as e:
        session.rollback()
        print(f"Error during import: {e}")
        raise
    finally:
        session.close()
        engine.dispose()


def list_available_years() -> None:
    """List all years that have been imported into the database."""
    from sqlalchemy import inspect

    settings = get_settings()
    engine = create_engine(settings.database_url)

    try:
        # Query database for all year-partitioned tables
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # Extract years from table names (format: schools_YYYY, districts_YYYY)
        years = set()
        for table_name in table_names:
            if '_' in table_name:
                parts = table_name.split('_')
                if len(parts) == 2:
                    try:
                        year = int(parts[1])
                        years.add(year)
                    except ValueError:
                        continue

        if not years:
            print("No data has been imported yet.")
        else:
            print("Available years in database:")
            for year in sorted(years):
                print(f"  - {year}")

    finally:
        engine.dispose()


def main():
    """CLI entry point for import command."""
    parser = argparse.ArgumentParser(description="Import Illinois Report Card data")
    parser.add_argument("file_path", nargs='?', help="Path to Excel file")
    parser.add_argument("--year", type=int, help="Year for data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without importing")
    parser.add_argument("--detect-schema", action="store_true", default=True,
                        help="Auto-detect column types and categories")
    parser.add_argument("--list-years", action="store_true", help="List available years in database")

    args = parser.parse_args()

    # Handle --list-years flag
    if args.list_years:
        list_available_years()
        return

    # For import operations, file_path and year are required
    if not args.file_path:
        parser.error("file_path is required for import operations")
    if not args.year:
        parser.error("--year is required for import operations")

    # Validate file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File not found: {args.file_path}")
        sys.exit(1)

    import_excel_file(
        file_path=str(file_path),
        year=args.year,
        dry_run=args.dry_run,
        detect_schema=args.detect_schema
    )


if __name__ == "__main__":
    main()
