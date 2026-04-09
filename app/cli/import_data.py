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

# Sheets with no data content — skip entirely
SKIP_SHEETS = {
    "Revision History",
    "Important Notes",
    "Notes",
    "Value Table for Growth Model",
    "Growth Model Results",
}

# Maps sheet name → table suffix ("" = General, no suffix)
SHEET_SUFFIX_MAP = {
    "General": "",
    "General (2)": "general2",
    "Financial": "finance",
    "Finance": "finance",
    "ELA and Math": "elamathscience",
    "ELA Math Science": "elamathscience",
    "ELAMathScience": "elamathscience",
    "PARCC": "parcc",
    "SAT": "sat",
    "IAR": "iar",
    "IAR (2)": "iar2",
    "ISA": "isa",
    "DLM": "dlm",
    "DLM-AA": "dlm",
    "DLM-AA (2)": "dlm2",
    "CTE": "cte",
    "Discipline": "discipline",
    "TeacherOF": "teacher",
    "TeacherOutofField": "teacher",
    "KIDS": "kids",
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

    # Prepare all recognized sheets for import
    prepared_sheets = []
    total_rows = 0
    for sheet_name, sheet_data in sheets.items():
        if sheet_name in SKIP_SHEETS or sheet_name not in SHEET_SUFFIX_MAP:
            continue
        if not sheet_data["rows"]:
            continue
        sheet_suffix = SHEET_SUFFIX_MAP[sheet_name]
        prepared_sheets.append((sheet_name, sheet_suffix, sheet_data))
        total_rows += len(sheet_data["rows"])

    print(f"Found {len(general_sheet['rows'])} rows in General sheet, {len(prepared_sheets)} sheets to import")

    if dry_run:
        dry_tables = []
        for sheet_name, suffix, sheet_data in prepared_sheets:
            headers_tmp = sheet_data["headers"]
            entity_vals = set()
            if "Type" in headers_tmp:
                for r in sheet_data["rows"]:
                    tv = r.get("Type", "School")
                    if tv in ENTITY_TYPE_MAP:
                        entity_vals.add(tv)
            else:
                entity_vals = {"School"}
            for tv in entity_vals:
                tp = ENTITY_TYPE_MAP[tv][0]
                tname = f"{tp}_{year}" if not suffix else f"{tp}_{suffix}_{year}"
                dry_tables.append(tname)
        print("\nDry run - no database changes will be made")
        print(f"Would create table: {', '.join(dry_tables)}")
        print(f"Would import {total_rows} rows")
        return

    # Pass 1: build schema and entity groups per sheet, then create all tables
    # (all table creation must happen before the session opens to avoid lock contention)
    sheet_plans = []  # (sheet_name, suffix, headers, normalized_headers, col_schema, entity_groups, is_general)
    for sheet_name, sheet_suffix, sheet_data in prepared_sheets:
        headers = sheet_data["headers"]
        rows = sheet_data["rows"]
        is_general = sheet_suffix == ""

        if "Type" in headers:
            entity_groups: Dict[str, List[Dict]] = {}
            for row_dict in rows:
                type_val = row_dict.get("Type", "School")
                if type_val in ENTITY_TYPE_MAP:
                    entity_groups.setdefault(type_val, []).append(row_dict)
        else:
            entity_groups = {"School": rows}

        normalized_headers = [normalize_column_name(h) for h in headers]
        col_schema: Dict[str, Dict] = {}
        schema_list = []
        for i, header in enumerate(headers):
            norm = normalized_headers[i]
            sample_values = [r.get(header) for r in rows if r.get(header) is not None]
            data_type = detect_column_type(header, sample_values) if detect_schema else "string"
            category = detect_column_category(norm) if detect_schema else "other"
            col_schema[norm] = {"data_type": data_type, "category": category, "source_column_name": header}
            schema_list.append({"column_name": norm, "data_type": data_type})

        for type_val in entity_groups:
            table_prefix, _ = ENTITY_TYPE_MAP[type_val]
            table_name = f"{table_prefix}_{year}" if not sheet_suffix else f"{table_prefix}_{sheet_suffix}_{year}"
            print(f"Creating table: {table_name}")
            create_year_table(year, table_prefix, schema_list, engine, sheet_suffix=sheet_suffix)

        sheet_plans.append((sheet_name, sheet_suffix, headers, normalized_headers, col_schema, entity_groups, is_general))

    # Pass 2: insert data
    session = Session()
    try:
        for sheet_name, sheet_suffix, headers, normalized_headers, col_schema, entity_groups, is_general in sheet_plans:
            for type_val, group_rows in entity_groups.items():
                table_prefix, master_entity_type = ENTITY_TYPE_MAP[type_val]
                table_name = f"{table_prefix}_{year}" if not sheet_suffix else f"{table_prefix}_{sheet_suffix}_{year}"

                print(f"Inserting {len(group_rows)} rows into {table_name}...")
                for row_dict in group_rows:
                    row_data = {}
                    for i, original_header in enumerate(headers):
                        norm = normalized_headers[i]
                        value = row_dict.get(original_header)
                        data_type = col_schema[norm]["data_type"]

                        if data_type == "percentage":
                            row_data[norm] = clean_percentage(value)
                        elif data_type == "integer":
                            cleaned = clean_enrollment(value)
                            row_data[norm] = cleaned if cleaned is not None else handle_suppressed(value)
                        elif data_type == "float":
                            cleaned = clean_percentage(value) if isinstance(value, str) and "%" in value else value
                            row_data[norm] = cleaned if cleaned is not None else handle_suppressed(value)
                        else:
                            row_data[norm] = handle_suppressed(value)

                    columns = ", ".join(row_data.keys())
                    placeholders = ", ".join([f":{k}" for k in row_data.keys()])
                    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                    session.execute(text(sql), row_data)

                    # Only populate entities_master from the General sheet
                    if is_general and "rcdts" in row_data and row_data["rcdts"]:
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
                    for column_name, column_info in col_schema.items():
                        session.add(SchemaMetadata(
                            year=year,
                            table_name=table_name,
                            column_name=column_name,
                            data_type=column_info["data_type"],
                            category=column_info["category"],
                            source_column_name=column_info["source_column_name"],
                        ))

        session.commit()
        print(f"Import completed successfully! Imported {total_rows} rows")

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
