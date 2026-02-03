# ABOUTME: Admin API endpoints
# ABOUTME: Provides administrative functions like key management and data imports

import secrets
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.dependencies import verify_api_key
from app.models.database import APIKey as APIKeyModel, ImportJob, SchemaMetadata, EntitiesMaster
from app.utils.excel_parser import parse_excel_file
from app.utils.schema_detector import detect_column_type, detect_column_category
from app.utils.data_cleaners import clean_percentage, clean_enrollment, handle_suppressed, normalize_column_name
from app.services.table_manager import create_year_table

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateAPIKeyRequest(BaseModel):
    """Request body for creating a new API key."""
    owner_email: str
    owner_name: str
    rate_limit_tier: str = "free"
    is_admin: bool = False


class CreateAPIKeyResponse(BaseModel):
    """Response containing the newly created API key."""
    api_key: str
    key_prefix: str
    owner_email: str
    owner_name: str
    rate_limit_tier: str
    is_admin: bool


def verify_admin_api_key(
    api_key: APIKeyModel = Depends(verify_api_key)
) -> APIKeyModel:
    """Verify that the API key has admin privileges."""
    if not api_key.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Admin privileges required"}
        )
    return api_key


@router.post("/keys", status_code=201, response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db),
    admin_key: APIKeyModel = Depends(verify_admin_api_key)
):
    """
    Create a new API key (admin only).

    The API key is generated securely and returned only once.
    Only the SHA-256 hash is stored in the database.
    """
    # Generate a secure random API key
    # Format: rcapi_<32 random hex characters>
    plaintext_key = f"rcapi_{secrets.token_hex(32)}"

    # Hash the key for storage
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    key_prefix = plaintext_key[:8]

    # Create the API key in the database
    new_api_key = APIKeyModel(
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner_email=request.owner_email,
        owner_name=request.owner_name,
        rate_limit_tier=request.rate_limit_tier,
        is_admin=request.is_admin
    )

    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)

    # Return the plaintext key (only time it's visible)
    return CreateAPIKeyResponse(
        api_key=plaintext_key,
        key_prefix=key_prefix,
        owner_email=new_api_key.owner_email,
        owner_name=new_api_key.owner_name,
        rate_limit_tier=new_api_key.rate_limit_tier,
        is_admin=new_api_key.is_admin
    )


@router.post("/import", status_code=201)
async def import_excel_file(
    file: UploadFile = File(...),
    year: int = Form(...),
    db: Session = Depends(get_db),
    admin_key: APIKeyModel = Depends(verify_admin_api_key)
):
    """
    Upload and import Excel file (admin only).

    Accepts multipart/form-data with:
    - file: Excel file
    - year: Year for the data

    Returns import_id and status for tracking.
    """
    # Validate file is Excel
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": "Only Excel files (.xlsx, .xls) are supported"}
        )

    # Generate import_id
    import_id = f"imp_{secrets.token_hex(8)}"

    # Create import job record
    import_job = ImportJob(
        import_id=import_id,
        year=year,
        filename=file.filename,
        status="processing",
        api_key_id=admin_key.id
    )
    db.add(import_job)
    db.commit()

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Parse Excel file
        sheets = parse_excel_file(tmp_file_path)

        if not sheets:
            raise ValueError("No data found in Excel file")

        # Get General sheet
        general_sheet = sheets.get("General")
        if not general_sheet:
            raise ValueError("No 'General' sheet found in Excel file")

        headers = general_sheet["headers"]
        rows = general_sheet["rows"]

        if not rows:
            raise ValueError("No data rows found in General sheet")

        # Normalize column names
        normalized_headers = [normalize_column_name(h) for h in headers]

        # Detect schema
        schema_metadata = {}
        schema_list = []
        for i, header in enumerate(headers):
            normalized_header = normalized_headers[i]
            sample_values = [row.get(header) for row in rows if row.get(header) is not None]
            data_type = detect_column_type(header, sample_values)
            category = detect_column_category(normalized_header)

            schema_metadata[normalized_header] = {
                "data_type": data_type,
                "category": category,
                "source_column_name": header
            }

            schema_list.append({
                "column_name": normalized_header,
                "data_type": data_type
            })

        # Create year-partitioned table
        table_name = f"schools_{year}"
        create_year_table(year, "schools", schema_list, db.bind)

        # Insert data
        records_imported = 0
        for row_dict in rows:
            row_data = {}
            for i, original_header in enumerate(headers):
                normalized_header = normalized_headers[i]
                value = row_dict.get(original_header)
                data_type = schema_metadata[normalized_header]["data_type"]

                # Apply data cleaning
                if data_type == "percentage":
                    row_data[normalized_header] = clean_percentage(value)
                elif data_type == "integer":
                    cleaned = clean_enrollment(value)
                    row_data[normalized_header] = cleaned if cleaned is not None else handle_suppressed(value)
                elif data_type == "float":
                    cleaned = clean_percentage(value) if isinstance(value, str) and "%" in str(value) else value
                    row_data[normalized_header] = cleaned if cleaned is not None else handle_suppressed(value)
                else:
                    row_data[normalized_header] = handle_suppressed(value)

            # Insert row
            columns = ", ".join(row_data.keys())
            placeholders = ", ".join([f":{k}" for k in row_data.keys()])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            db.execute(text(sql), row_data)

            # Update entities_master
            if "rcdts" in row_data and row_data["rcdts"]:
                entity = db.query(EntitiesMaster).filter_by(rcdts=row_data["rcdts"]).first()
                if not entity:
                    entity = EntitiesMaster(
                        rcdts=row_data["rcdts"],
                        name=row_data.get("school_name", ""),
                        city=row_data.get("city", ""),
                        county=row_data.get("county", ""),
                        entity_type="school"
                    )
                    db.add(entity)

            records_imported += 1

        # Populate schema_metadata
        for column_name, column_info in schema_metadata.items():
            metadata_entry = SchemaMetadata(
                year=year,
                table_name=table_name,
                column_name=column_name,
                data_type=column_info["data_type"],
                category=column_info["category"],
                source_column_name=column_info["source_column_name"]
            )
            db.add(metadata_entry)

        # Update import job as completed
        import_job.status = "completed"
        import_job.records_imported = records_imported
        import_job.completed_at = datetime.utcnow()
        db.commit()

        # Clean up temp file
        Path(tmp_file_path).unlink()

        return {
            "import_id": import_id,
            "status": "completed",
            "year": year,
            "records_imported": records_imported
        }

    except Exception as e:
        # Mark import as failed
        import_job.status = "failed"
        import_job.error_message = str(e)
        import_job.completed_at = datetime.utcnow()
        db.commit()

        raise HTTPException(
            status_code=500,
            detail={"code": "IMPORT_FAILED", "message": f"Import failed: {str(e)}"}
        )


@router.get("/import/status/{import_id}")
async def get_import_status(
    import_id: str,
    db: Session = Depends(get_db),
    admin_key: APIKeyModel = Depends(verify_admin_api_key)
):
    """
    Get the status of an import job (admin only).

    Returns current status, records_imported count, and any error messages.
    """
    import_job = db.query(ImportJob).filter_by(import_id=import_id).first()

    if not import_job:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Import job not found: {import_id}"}
        )

    response = {
        "import_id": import_job.import_id,
        "status": import_job.status,
        "year": import_job.year,
        "filename": import_job.filename,
        "started_at": import_job.started_at.isoformat() if import_job.started_at else None
    }

    if import_job.status == "completed":
        response["records_imported"] = import_job.records_imported
        response["completed_at"] = import_job.completed_at.isoformat() if import_job.completed_at else None
    elif import_job.status == "failed":
        response["error"] = import_job.error_message
        response["completed_at"] = import_job.completed_at.isoformat() if import_job.completed_at else None

    return response
