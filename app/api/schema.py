# ABOUTME: Schema metadata endpoints
# ABOUTME: Returns field metadata and documentation for year-partitioned tables

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey, SchemaMetadata
from app.models.errors import AUTH_REQUIRED, NOT_FOUND

router = APIRouter()

_SCHEMA_EXAMPLE = {
    "data": [
        {"column_name": "school_name", "data_type": "string", "category": "demographics",
         "description": None, "source_column_name": "School Name", "is_suppressed_indicator": False},
        {"column_name": "total_students", "data_type": "integer", "category": "enrollment",
         "description": None, "source_column_name": "Total Students", "is_suppressed_indicator": False},
    ],
    "meta": {"year": 2024, "count": 2}
}


@router.get("/schema/{year}", responses={
    200: {"description": "Schema fields for the year", "content": {"application/json": {"example": _SCHEMA_EXAMPLE}}},
    **AUTH_REQUIRED, **NOT_FOUND,
})
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


@router.get("/schema/{year}/{category}", responses={
    200: {"description": "Schema fields filtered by category", "content": {"application/json": {"example": {
        "data": [{"column_name": "total_students", "data_type": "integer", "category": "enrollment",
                 "description": None, "source_column_name": "Total Students", "is_suppressed_indicator": False}],
        "meta": {"year": 2024, "category": "enrollment", "count": 1}
    }}}},
    **AUTH_REQUIRED,
})
async def get_schema_for_year_and_category(
    year: int,
    category: str,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Returns field metadata for a specific year filtered by category."""
    # Query schema_metadata for the given year and category
    metadata_entries = db.query(SchemaMetadata).filter(
        SchemaMetadata.year == year,
        SchemaMetadata.category == category
    ).all()

    # Convert to response format (empty array if no matches)
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
            "category": category,
            "count": len(data)
        }
    }
