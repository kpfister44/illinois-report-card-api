# ABOUTME: Tests for GET /state/{year} endpoint
# ABOUTME: Validates state-level aggregate data retrieval functionality

import pytest
import hashlib
from sqlalchemy import text
from app.models.database import APIKey
from app.services.table_manager import create_year_table


def test_get_state_returns_aggregate_data(client):
    """Test #43: GET /state/{year} returns state-level aggregate data."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_state_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=test_key[:8],
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()

        # Step 1: Import state-level data for year 2025
        schema = [
            {"column_name": "entity_type", "data_type": "string"},
            {"column_name": "total_enrollment", "data_type": "integer"},
            {"column_name": "avg_act_composite", "data_type": "float"},
            {"column_name": "graduation_rate", "data_type": "float"}
        ]

        create_year_table(2025, "state", schema, engine)

        table_name = "state_2025"
        state_data = {
            "entity_type": "state",
            "total_enrollment": 1950000,
            "avg_act_composite": 21.4,
            "graduation_rate": 87.5
        }

        columns = ", ".join(state_data.keys())
        placeholders = ", ".join([f":{k}" for k in state_data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), state_data)
        db.commit()

    finally:
        db.close()

    # Step 2: Send authenticated GET request to /state/2025
    response = client.get(
        "/state/2025",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 3: Verify response status code is 200
    assert response.status_code == 200

    # Step 4: Verify response has data object with state aggregates
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], dict)

    # Step 5: Verify state-level metrics are present
    state = data["data"]
    assert state["entity_type"] == "state"
    assert state["total_enrollment"] == 1950000
    assert state["avg_act_composite"] == 21.4
    assert state["graduation_rate"] == 87.5


def test_get_state_supports_field_selection(client):
    """Test #44: GET /state/{year} supports field selection."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_state_fields_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=test_key[:8],
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()

        # Import state-level data
        schema = [
            {"column_name": "entity_type", "data_type": "string"},
            {"column_name": "total_enrollment", "data_type": "integer"},
            {"column_name": "avg_act_composite", "data_type": "float"},
            {"column_name": "graduation_rate", "data_type": "float"}
        ]

        create_year_table(2025, "state", schema, engine)

        table_name = "state_2025"
        state_data = {
            "entity_type": "state",
            "total_enrollment": 1950000,
            "avg_act_composite": 21.4,
            "graduation_rate": 87.5
        }

        columns = ", ".join(state_data.keys())
        placeholders = ", ".join([f":{k}" for k in state_data.keys()])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        db.execute(text(sql), state_data)
        db.commit()

    finally:
        db.close()

    # Step 1: Send authenticated GET request with fields parameter
    response = client.get(
        "/state/2025?fields=total_enrollment,avg_act_composite",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 200
    assert response.status_code == 200

    # Step 3: Verify only requested fields are present
    data = response.json()
    state = data["data"]
    assert "total_enrollment" in state
    assert "avg_act_composite" in state
    assert "graduation_rate" not in state
    assert "entity_type" not in state
    assert len(state.keys()) == 2


def test_get_state_returns_400_for_invalid_year(client):
    """Test #45: GET /state/{year} returns 400 for invalid year."""
    from tests.conftest import TestingSessionLocal, engine

    db = TestingSessionLocal()
    try:
        # Create test API key
        test_key = "rcapi_test_state_invalid_year_key"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=test_key[:8],
            owner_email="test@example.com",
            owner_name="Test User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()

    finally:
        db.close()

    # Step 1: Send authenticated GET request to /state/2030 (non-existent year)
    response = client.get(
        "/state/2030",
        headers={"Authorization": f"Bearer {test_key}"}
    )

    # Step 2: Verify response status code is 400
    assert response.status_code == 400

    # Step 3: Verify error response has code INVALID_PARAMETER
    data = response.json()
    assert "code" in data
    assert data["code"] == "INVALID_PARAMETER"

    # Step 4: Verify error message indicates available years
    assert "message" in data
    assert "2030" in data["message"]
