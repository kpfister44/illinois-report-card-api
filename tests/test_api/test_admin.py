# ABOUTME: Admin API endpoint tests
# ABOUTME: Verifies admin functionality for key management and imports

import pytest
import hashlib
import tempfile
from pathlib import Path
from io import BytesIO
import openpyxl
from app.models.database import APIKey, UsageLog


def create_admin_api_key(db_session):
    """Helper to create an admin API key for testing admin endpoints."""
    key = "admin_key_12345"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key[:8],
        owner_email="admin@example.com",
        owner_name="Admin User",
        is_active=True,
        rate_limit_tier="premium",
        is_admin=True
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return key  # Return plaintext key for auth


def test_admin_create_api_key_with_hashing(client):
    """Test #7: Admin endpoint creates API key with proper hashing."""
    # Create admin API key
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Create new API key via admin endpoint
    response = client.post(
        "/admin/keys",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={
            "owner_email": "newuser@example.com",
            "owner_name": "New User",
            "rate_limit_tier": "standard",
            "is_admin": False
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert "api_key" in data
    assert "key_prefix" in data

    plaintext_key = data["api_key"]

    # Step 2: Query api_keys table directly
    db2 = TestingSessionLocal()
    try:
        api_key = db2.query(APIKey).filter(APIKey.key_prefix == plaintext_key[:8]).first()
        assert api_key is not None

        # Step 3: Verify key_hash column contains SHA-256 hash (not plaintext)
        expected_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        assert api_key.key_hash == expected_hash
        assert api_key.key_hash != plaintext_key  # Ensure it's not storing plaintext

        # Step 4: Verify key_prefix column contains first 8 characters
        assert api_key.key_prefix == plaintext_key[:8]

    finally:
        db2.close()

    # Step 5: Verify authentication works by hashing provided key and comparing
    response = client.get("/years", headers={"Authorization": f"Bearer {plaintext_key}"})
    assert response.status_code == 200


def test_usage_logging_captures_all_requests(client):
    """Test #8: Usage logging captures all requests accurately."""
    from tests.conftest import TestingSessionLocal

    # Create a test API key
    db = TestingSessionLocal()
    try:
        key = "usage_test_key_123"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key[:8],
            owner_email="usage@example.com",
            owner_name="Usage Test",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        api_key_id = api_key.id
    finally:
        db.close()

    # Step 1: Make authenticated request to any endpoint
    response = client.get("/years", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200

    # Step 2: Query usage_logs table
    db2 = TestingSessionLocal()
    try:
        usage_log = db2.query(UsageLog).filter(UsageLog.api_key_id == api_key_id).first()
        assert usage_log is not None

        # Step 3: Verify entry contains api_key_id, endpoint, method
        assert usage_log.api_key_id == api_key_id
        assert usage_log.endpoint == "/years"
        assert usage_log.method == "GET"

        # Step 4: Verify entry contains status_code, response_time_ms, timestamp
        assert usage_log.status_code == 200
        assert usage_log.response_time_ms is not None
        assert usage_log.response_time_ms >= 0
        assert usage_log.timestamp is not None

        # Step 5: Verify ip_address captured
        assert usage_log.ip_address is not None
    finally:
        db2.close()


def create_test_excel_file() -> BytesIO:
    """Helper to create a minimal test Excel file with school data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "General"

    # Add headers
    headers = ["RCDTS", "School Name", "City", "County", "Student Enrollment"]
    ws.append(headers)

    # Add sample data rows
    ws.append(["01-016-0001-17-0001", "Test Import School 1", "Chicago", "Cook", "500"])
    ws.append(["02-016-0002-17-0002", "Test Import School 2", "Springfield", "Sangamon", "300"])
    ws.append(["03-016-0003-17-0003", "Test Import School 3", "Naperville", "DuPage", "450"])

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def test_admin_import_uploads_and_processes_excel_file(client):
    """Test #63: Admin endpoint POST /admin/import uploads and processes Excel file."""
    from tests.conftest import TestingSessionLocal
    from sqlalchemy import text, inspect
    from app.models.database import SchemaMetadata, EntitiesMaster
    import time

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Create test Excel file with sample school data
    excel_file = create_test_excel_file()

    # Step 2 & 3: Send authenticated POST to /admin/import with multipart/form-data
    response = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("test_schools.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )

    # Step 4: Verify response status code is 201
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()

    # Step 5: Verify response has import_id and status: processing
    assert "import_id" in data, "Response should contain import_id"
    assert "status" in data, "Response should contain status"
    import_id = data["import_id"]
    assert data["status"] in ["processing", "completed"], f"Expected status processing/completed, got {data['status']}"

    # Step 6: Poll /admin/import/status/{import_id} until complete
    max_attempts = 10
    poll_interval = 0.5  # seconds
    final_status = None

    for attempt in range(max_attempts):
        status_response = client.get(
            f"/admin/import/status/{import_id}",
            headers={"Authorization": f"Bearer {admin_key}"}
        )
        assert status_response.status_code == 200, f"Status check failed: {status_response.text}"
        status_data = status_response.json()

        if status_data["status"] == "completed":
            final_status = status_data
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Import failed: {status_data.get('error', 'Unknown error')}")

        time.sleep(poll_interval)

    assert final_status is not None, "Import did not complete within expected time"

    # Step 7: Verify final status shows records_imported count
    assert "records_imported" in final_status, "Final status should contain records_imported"
    assert final_status["records_imported"] == 3, f"Expected 3 records imported, got {final_status['records_imported']}"

    # Step 8: Verify schools_2025 table contains imported data
    db2 = TestingSessionLocal()
    try:
        # Check table exists
        inspector = inspect(db2.bind)
        table_names = inspector.get_table_names()
        assert "schools_2025" in table_names, "schools_2025 table should exist"

        # Query data from schools_2025
        query = text("SELECT rcdts, school_name, city, county, student_enrollment FROM schools_2025")
        result = db2.execute(query)
        rows = result.fetchall()

        # Verify 3 schools imported
        assert len(rows) >= 3, f"Expected at least 3 schools, found {len(rows)}"

        # Verify specific test data
        rcdts_list = [row[0] for row in rows]
        assert "01-016-0001-17-0001" in rcdts_list, "First test school should be imported"
        assert "02-016-0002-17-0002" in rcdts_list, "Second test school should be imported"
        assert "03-016-0003-17-0003" in rcdts_list, "Third test school should be imported"

        # Step 9: Verify schema_metadata populated with column info
        metadata_entries = db2.query(SchemaMetadata).filter(
            SchemaMetadata.year == 2025,
            SchemaMetadata.table_name == "schools_2025"
        ).all()

        assert len(metadata_entries) > 0, "Schema metadata should be populated"

        # Verify some expected columns are documented
        column_names = [entry.column_name for entry in metadata_entries]
        assert "rcdts" in column_names, "RCDTS column should be in schema metadata"
        assert "school_name" in column_names, "School Name column should be in schema metadata"

        # Step 10: Verify entities_master updated with new entities
        entities = db2.query(EntitiesMaster).filter(
            EntitiesMaster.rcdts.in_([
                "01-016-0001-17-0001",
                "02-016-0002-17-0002",
                "03-016-0003-17-0003"
            ])
        ).all()

        assert len(entities) == 3, f"Expected 3 entities in entities_master, found {len(entities)}"

        # Verify entity details
        entity_names = {e.name for e in entities}
        assert "Test Import School 1" in entity_names, "First school should be in entities_master"
        assert "Test Import School 2" in entity_names, "Second school should be in entities_master"
        assert "Test Import School 3" in entity_names, "Third school should be in entities_master"

    finally:
        db2.close()


def test_admin_import_requires_admin_key(client):
    """Test #64: Admin endpoint /admin/import requires admin API key."""
    from tests.conftest import TestingSessionLocal

    # Create NON-admin API key
    db = TestingSessionLocal()
    try:
        key = "regular_user_key_123"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key[:8],
            owner_email="regular@example.com",
            owner_name="Regular User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False  # NOT an admin
        )
        db.add(api_key)
        db.commit()
    finally:
        db.close()

    # Create test Excel file
    excel_file = create_test_excel_file()

    # Step 1: Send POST to /admin/import with non-admin API key
    response = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {key}"},
        files={"file": ("test.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )

    # Step 2: Verify response status code is 403
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    # Step 3 & 4: Verify error code and message
    data = response.json()
    assert "code" in data, "Response should contain error code"
    assert "message" in data, "Response should contain error message"
    assert data["code"] == "FORBIDDEN", f"Expected FORBIDDEN code, got {data['code']}"
    assert "admin" in data["message"].lower(), "Error message should mention admin requirement"


def test_admin_import_rejects_invalid_file_types(client):
    """Test #66: POST /admin/import rejects invalid file types with 400 error."""
    from tests.conftest import TestingSessionLocal

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Create a text file (not Excel)
    text_file = BytesIO(b"This is a text file, not an Excel file")

    # Step 2 & 3: Send POST to /admin/import with non-Excel file
    response = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("test.txt", text_file, "text/plain")},
        data={"year": "2025"}
    )

    # Step 4: Verify response status code is 400
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    # Step 5 & 6: Verify error code and message
    data = response.json()
    assert "code" in data, "Response should contain error code"
    assert "message" in data, "Response should contain error message"
    assert data["code"] == "INVALID_FILE_TYPE", f"Expected INVALID_FILE_TYPE, got {data['code']}"
    assert "excel" in data["message"].lower() or ".xlsx" in data["message"].lower(), \
        "Error message should mention Excel file requirement"


def test_admin_import_status_returns_import_progress(client):
    """Test #65: Admin endpoint GET /admin/import/status/{id} returns import progress."""
    from tests.conftest import TestingSessionLocal
    import time

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Start an import via POST /admin/import
    excel_file = create_test_excel_file()
    response = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("test.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )
    assert response.status_code == 201, f"Import start failed: {response.text}"
    data = response.json()
    import_id = data["import_id"]

    # Step 2: Immediately GET /admin/import/status/{import_id}
    status_response = client.get(
        f"/admin/import/status/{import_id}",
        headers={"Authorization": f"Bearer {admin_key}"}
    )

    # Step 3: Verify status shows processing or completed
    assert status_response.status_code == 200, f"Status check failed: {status_response.text}"
    status_data = status_response.json()
    assert "status" in status_data, "Response should contain status field"
    assert status_data["status"] in ["processing", "completed", "failed"], \
        f"Status should be processing/completed/failed, got: {status_data['status']}"

    # Step 4: Wait for completion
    max_attempts = 10
    poll_interval = 0.5
    final_status = None

    for attempt in range(max_attempts):
        status_response = client.get(
            f"/admin/import/status/{import_id}",
            headers={"Authorization": f"Bearer {admin_key}"}
        )
        assert status_response.status_code == 200, f"Status check failed: {status_response.text}"
        status_data = status_response.json()

        if status_data["status"] == "completed":
            final_status = status_data
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Import failed: {status_data.get('error', 'Unknown error')}")

        time.sleep(poll_interval)

    assert final_status is not None, "Import did not complete within expected time"

    # Step 5: Verify final status shows completed with record count
    assert final_status["status"] == "completed", f"Expected completed status, got {final_status['status']}"
    assert "records_imported" in final_status, "Final status should contain records_imported"
    assert final_status["records_imported"] > 0, "Should have imported at least 1 record"
    assert "import_id" in final_status, "Status should include import_id"
    assert final_status["import_id"] == import_id, "Import ID should match"


def test_admin_import_status_returns_404_for_nonexistent_id(client):
    """Test #68: GET /admin/import/status returns 404 for non-existent import_id."""
    from tests.conftest import TestingSessionLocal

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Send GET to /admin/import/status with non-existent import_id
    nonexistent_id = "nonexistent_import_12345"
    response = client.get(
        f"/admin/import/status/{nonexistent_id}",
        headers={"Authorization": f"Bearer {admin_key}"}
    )

    # Step 2: Verify response status code is 404
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    # Step 3 & 4: Verify error code and message includes the import_id
    data = response.json()
    assert "code" in data, "Response should contain error code"
    assert "message" in data, "Response should contain error message"
    assert data["code"] == "NOT_FOUND", f"Expected NOT_FOUND, got {data['code']}"
    assert nonexistent_id in data["message"], "Error message should include the requested import_id"
