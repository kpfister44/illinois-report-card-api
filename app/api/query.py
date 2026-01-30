# ABOUTME: Flexible query endpoint
# ABOUTME: Allows POST requests with field selection, filtering, sorting, and pagination

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.dependencies import verify_api_key, get_db
from app.models.database import APIKey
from app.services.table_manager import get_year_table

router = APIRouter()


class QueryRequest(BaseModel):
    year: int
    entity_type: str
    fields: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0


@router.post("/query")
async def query(
    request: QueryRequest,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Execute a flexible query with field selection, filtering, sorting, and pagination."""
    # Get the year-partitioned table
    entity_table_map = {
        "school": "schools",
        "district": "districts",
        "state": "state"
    }

    table_base = entity_table_map.get(request.entity_type, request.entity_type + "s")
    table = get_year_table(request.year, table_base, db.bind)

    if table is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"No data available for {request.entity_type} in year {request.year}"
            }
        )

    # Build field selection clause
    if request.fields:
        select_clause = ", ".join(request.fields)
    else:
        select_clause = "*"

    table_name = f"{table_base}_{request.year}"

    # Build WHERE clause for filters
    where_conditions = []
    query_params = {"limit": request.limit, "offset": request.offset}

    if request.filters:
        param_counter = 0
        for field, value in request.filters.items():
            # Check if value is a dict with comparison operators
            if isinstance(value, dict):
                # Handle comparison operators: gte, lte, gt, lt, in
                for operator, op_value in value.items():
                    if operator == "in":
                        # Handle IN operator with list of values
                        if not isinstance(op_value, list):
                            continue
                        # Build placeholders for each value in the list
                        placeholders = []
                        for item in op_value:
                            param_name = f"filter_{param_counter}"
                            param_counter += 1
                            placeholders.append(f":{param_name}")
                            query_params[param_name] = item
                        where_conditions.append(f"{field} IN ({', '.join(placeholders)})")
                    else:
                        param_name = f"filter_{param_counter}"
                        param_counter += 1

                        if operator == "gte":
                            where_conditions.append(f"{field} >= :{param_name}")
                            query_params[param_name] = op_value
                        elif operator == "lte":
                            where_conditions.append(f"{field} <= :{param_name}")
                            query_params[param_name] = op_value
                        elif operator == "gt":
                            where_conditions.append(f"{field} > :{param_name}")
                            query_params[param_name] = op_value
                        elif operator == "lt":
                            where_conditions.append(f"{field} < :{param_name}")
                            query_params[param_name] = op_value
            else:
                # Simple equality filter
                where_conditions.append(f"{field} = :{field}")
                query_params[field] = value

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # Get total count with filters
    count_query = text(f"SELECT COUNT(*) as total FROM {table_name} {where_clause}")
    result = db.execute(count_query, query_params)
    total = result.scalar()

    # Get paginated data with field selection and filters
    data_query = text(f"""
        SELECT {select_clause}
        FROM {table_name}
        {where_clause}
        LIMIT :limit OFFSET :offset
    """)
    result = db.execute(data_query, query_params)

    # Convert rows to dictionaries
    rows = result.fetchall()
    columns = result.keys()
    data = [dict(zip(columns, row)) for row in rows]

    return {
        "data": data,
        "meta": {
            "total": total,
            "limit": request.limit,
            "offset": request.offset
        }
    }
