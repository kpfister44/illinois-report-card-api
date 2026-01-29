# ABOUTME: Schema metadata endpoints
# ABOUTME: Returns field metadata and documentation for year-partitioned tables

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey, SchemaMetadata

router = APIRouter()


@router.get("/schema/{year}")
async def get_schema_for_year(
    year: int,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Returns field metadata for a specific year."""
    # Query schema_metadata for the given year
    metadata_entries = db.query(SchemaMetadata).filter(
        SchemaMetadata.year == year
    ).all()

    if not metadata_entries:
        raise HTTPException(
            status_code=404,
            detail=f"No schema metadata found for year {year}"
        )

    # Convert to response format
    data = []
    for entry in metadata_entries:
        data.append({
            "column_name": entry.column_name,
            "data_type": entry.data_type,
            "category": entry.category,
            "description": entry.description,
            "source_column_name": entry.source_column_name,
            "is_suppressed_indicator": entry.is_suppressed_indicator
        })

    return {
        "data": data,
        "meta": {
            "year": year,
            "count": len(data)
        }
    }
