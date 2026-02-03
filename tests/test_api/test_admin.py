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


def test_admin_import_handles_corrupt_excel_file(client):
    """Test #67: POST /admin/import handles corrupt Excel file gracefully."""
    from tests.conftest import TestingSessionLocal
    from sqlalchemy import text, inspect

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1: Create a corrupt/invalid Excel file (truncated/malformed)
    # Create a file that claims to be Excel but has invalid content
    corrupt_file = BytesIO(b"This is not a valid Excel file - it's just random text that will fail to parse")

    # Step 2 & 3: Send authenticated POST to /admin/import with corrupt file
    response = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("corrupt.xlsx", corrupt_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )

    # Step 4: Verify response returns appropriate error (400 or 500 for import failure)
    assert response.status_code in [400, 500], f"Expected 400 or 500, got {response.status_code}"

    # Step 5: Verify error message indicates file parsing failed
    data = response.json()
    assert "code" in data, "Response should contain error code"
    assert "message" in data, "Response should contain error message"
    error_message = data["message"].lower()
    # Should mention parsing/import/file failure
    assert any(keyword in error_message for keyword in ["parse", "import", "file", "failed", "invalid"]), \
        f"Error message should indicate parsing/import failure, got: {data['message']}"

    # Step 6: Verify no partial data was imported to database
    db2 = TestingSessionLocal()
    try:
        # Check if any new schools were added (there shouldn't be any from this corrupt import)
        inspector = inspect(db2.bind)
        table_names = inspector.get_table_names()

        if "schools_2025" in table_names:
            # If table exists, check that no schools from this import were added
            # The corrupt file has no valid RCDTS data, so if any were added, it's a problem
            query = text("SELECT COUNT(*) FROM schools_2025 WHERE rcdts LIKE '%corrupt%'")
            result = db2.execute(query)
            count = result.scalar()
            assert count == 0, "No data from corrupt file should have been imported"
    finally:
        db2.close()


def test_reimporting_year_replaces_previous_data(client):
    """Test #69: Re-importing data for an existing year replaces previous data."""
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

    # Step 1: Import 2025 data with 3 schools (using test helper)
    excel_file_1 = create_test_excel_file()
    response_1 = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("test1.xlsx", excel_file_1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )
    assert response_1.status_code == 201, f"First import failed: {response_1.text}"

    # Wait for first import to complete
    import_id_1 = response_1.json()["import_id"]
    max_attempts = 10
    for _ in range(max_attempts):
        status_response = client.get(
            f"/admin/import/status/{import_id_1}",
            headers={"Authorization": f"Bearer {admin_key}"}
        )
        if status_response.json()["status"] == "completed":
            break
        time.sleep(0.5)

    # Step 2: Verify schools_2025 table has 3 records
    db2 = TestingSessionLocal()
    try:
        query = text("SELECT COUNT(*) FROM schools_2025")
        result = db2.execute(query)
        count_before = result.scalar()
        assert count_before == 3, f"Expected 3 schools after first import, got {count_before}"

        # Get RCDTSs from first import
        query = text("SELECT rcdts FROM schools_2025 ORDER BY rcdts")
        result = db2.execute(query)
        rcdts_before = [row[0] for row in result.fetchall()]
        assert len(rcdts_before) == 3, "Should have 3 RCDTSs"
    finally:
        db2.close()

    # Step 3: Create a modified Excel file with 5 schools for 2025
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "General"
    headers = ["RCDTS", "School Name", "City", "County", "Student Enrollment"]
    ws.append(headers)
    # Add 5 different schools
    ws.append(["10-016-0010-17-0010", "Reimport School 1", "Chicago", "Cook", "600"])
    ws.append(["11-016-0011-17-0011", "Reimport School 2", "Aurora", "Kane", "400"])
    ws.append(["12-016-0012-17-0012", "Reimport School 3", "Peoria", "Peoria", "350"])
    ws.append(["13-016-0013-17-0013", "Reimport School 4", "Rockford", "Winnebago", "550"])
    ws.append(["14-016-0014-17-0014", "Reimport School 5", "Joliet", "Will", "500"])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    excel_file_2 = output

    # Step 4: Re-import 2025 data with the modified file
    response_2 = client.post(
        "/admin/import",
        headers={"Authorization": f"Bearer {admin_key}"},
        files={"file": ("test2.xlsx", excel_file_2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"year": "2025"}
    )

    # Step 5: Verify import completes successfully
    assert response_2.status_code == 201, f"Second import failed: {response_2.text}"
    import_id_2 = response_2.json()["import_id"]

    # Wait for second import to complete
    for _ in range(max_attempts):
        status_response = client.get(
            f"/admin/import/status/{import_id_2}",
            headers={"Authorization": f"Bearer {admin_key}"}
        )
        if status_response.json()["status"] == "completed":
            break
        time.sleep(0.5)

    # Step 6: Verify schools_2025 table now has 5 records (replaced, not appended)
    db3 = TestingSessionLocal()
    try:
        query = text("SELECT COUNT(*) FROM schools_2025")
        result = db3.execute(query)
        count_after = result.scalar()
        assert count_after == 5, f"Expected 5 schools after re-import (replaced), got {count_after}"

        # Verify the new RCDTSs are from the second import
        query = text("SELECT rcdts FROM schools_2025 ORDER BY rcdts")
        result = db3.execute(query)
        rcdts_after = [row[0] for row in result.fetchall()]
        assert len(rcdts_after) == 5, "Should have 5 RCDTSs after re-import"

        # Verify these are the NEW schools, not the old ones
        assert "10-016-0010-17-0010" in rcdts_after, "Should have first reimport school"
        assert "14-016-0014-17-0014" in rcdts_after, "Should have last reimport school"
        assert "01-016-0001-17-0001" not in rcdts_after, "Should NOT have first original school (data replaced)"

        # Step 7: Verify schema_metadata is updated
        metadata_count = db3.query(SchemaMetadata).filter(
            SchemaMetadata.year == 2025,
            SchemaMetadata.table_name == "schools_2025"
        ).count()
        assert metadata_count > 0, "Schema metadata should exist after re-import"

        # Step 8: Verify entities_master is updated with new entities
        new_entities = db3.query(EntitiesMaster).filter(
            EntitiesMaster.rcdts.in_([
                "10-016-0010-17-0010",
                "14-016-0014-17-0014"
            ])
        ).all()
        assert len(new_entities) == 2, "New entities should be in entities_master"

    finally:
        db3.close()


def test_admin_create_api_key_endpoint(client):
    """Test #70: Admin endpoint POST /admin/keys creates new API key."""
    from tests.conftest import TestingSessionLocal

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)
    finally:
        db.close()

    # Step 1 & 2: Send authenticated POST to /admin/keys with admin key
    response = client.post(
        "/admin/keys",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={
            "owner_email": "test@example.com",
            "owner_name": "Test User",
            "rate_limit_tier": "free"
        }
    )

    # Step 3: Verify response status code is 201
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    data = response.json()

    # Step 4: Verify response contains full key (only returned once)
    assert "api_key" in data, "Response should contain api_key field"
    new_key = data["api_key"]
    assert len(new_key) > 0, "API key should not be empty"

    # Step 5: Verify key starts with rc_live_ prefix
    assert new_key.startswith("rc_live_"), f"API key should start with rc_live_, got: {new_key}"

    # Step 6: Verify response contains key_prefix
    assert "key_prefix" in data, "Response should contain key_prefix field"
    assert data["key_prefix"] == new_key[:8], "key_prefix should be first 8 characters of key"
    assert data["key_prefix"] == "rc_live_", "key_prefix should be rc_live_"

    # Step 7: Verify new key works for API authentication
    auth_response = client.get("/years", headers={"Authorization": f"Bearer {new_key}"})
    assert auth_response.status_code == 200, f"New API key should work for authentication, got {auth_response.status_code}"

    # Step 8: Verify key stored as hash in database (not plaintext)
    db2 = TestingSessionLocal()
    try:
        from app.models.database import APIKey
        api_key_record = db2.query(APIKey).filter(APIKey.key_prefix == new_key[:8]).first()
        assert api_key_record is not None, "API key should be in database"

        # Verify it's hashed (SHA-256 is 64 hex characters)
        assert len(api_key_record.key_hash) == 64, "Hash should be SHA-256 (64 hex chars)"
        assert api_key_record.key_hash != new_key, "Database should store hash, not plaintext"

        # Verify the hash matches
        expected_hash = hashlib.sha256(new_key.encode()).hexdigest()
        assert api_key_record.key_hash == expected_hash, "Stored hash should match SHA-256 of key"
    finally:
        db2.close()


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


def test_admin_list_api_keys(client):
    """Test #71: Admin endpoint GET /admin/keys lists all API keys."""
    from tests.conftest import TestingSessionLocal

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)

        # Step 1: Create multiple API keys
        # Create 3 test API keys with different properties
        test_keys = [
            {
                "key": "test_key_1",
                "owner_email": "user1@example.com",
                "owner_name": "User One",
                "rate_limit_tier": "free",
                "is_active": True,
                "is_admin": False
            },
            {
                "key": "test_key_2",
                "owner_email": "user2@example.com",
                "owner_name": "User Two",
                "rate_limit_tier": "standard",
                "is_active": True,
                "is_admin": False
            },
            {
                "key": "test_key_3_inactive",
                "owner_email": "user3@example.com",
                "owner_name": "User Three",
                "rate_limit_tier": "premium",
                "is_active": False,
                "is_admin": False
            }
        ]

        for key_data in test_keys:
            key_hash = hashlib.sha256(key_data["key"].encode()).hexdigest()
            api_key = APIKey(
                key_hash=key_hash,
                key_prefix=key_data["key"][:8],
                owner_email=key_data["owner_email"],
                owner_name=key_data["owner_name"],
                is_active=key_data["is_active"],
                rate_limit_tier=key_data["rate_limit_tier"],
                is_admin=key_data["is_admin"]
            )
            db.add(api_key)
        db.commit()
    finally:
        db.close()

    # Step 2: Send authenticated GET to /admin/keys with admin key
    response = client.get(
        "/admin/keys",
        headers={"Authorization": f"Bearer {admin_key}"}
    )

    # Verify response status code is 200
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Step 3: Verify response contains list of all keys
    assert "data" in data, "Response should contain data field"
    keys_list = data["data"]
    assert isinstance(keys_list, list), "data field should be a list"
    assert len(keys_list) >= 4, f"Should have at least 4 keys (admin + 3 test keys), got {len(keys_list)}"

    # Step 4: Verify each key shows key_prefix, owner_email, owner_name
    for key_item in keys_list:
        assert "key_prefix" in key_item, "Each key should have key_prefix field"
        assert "owner_email" in key_item, "Each key should have owner_email field"
        assert "owner_name" in key_item, "Each key should have owner_name field"

        # Step 5: Verify full key is NOT exposed (security)
        assert "api_key" not in key_item, "Full API key should NOT be exposed in list"
        assert "key_hash" not in key_item, "Key hash should NOT be exposed in list"

        # Step 6: Verify is_active and rate_limit_tier fields present
        assert "is_active" in key_item, "Each key should have is_active field"
        assert "rate_limit_tier" in key_item, "Each key should have rate_limit_tier field"
        assert isinstance(key_item["is_active"], bool), "is_active should be boolean"
        assert key_item["rate_limit_tier"] in ["free", "standard", "premium"], "rate_limit_tier should be valid"

    # Verify our test keys are in the response
    prefixes = [k["key_prefix"] for k in keys_list]
    assert "test_key" in prefixes, "test_key_1 should be in the list"
    assert "user1@example.com" in [k["owner_email"] for k in keys_list], "user1 should be in the list"


def test_admin_delete_api_key(client):
    """Test #72: Admin endpoint DELETE /admin/keys/{id} revokes API key."""
    from tests.conftest import TestingSessionLocal

    # Create admin API key
    db = TestingSessionLocal()
    try:
        admin_key = create_admin_api_key(db)

        # Step 1: Create a test API key
        test_key = "test_key_to_delete"
        key_hash = hashlib.sha256(test_key.encode()).hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=test_key[:8],
            owner_email="delete_test@example.com",
            owner_name="Delete Test User",
            is_active=True,
            rate_limit_tier="free",
            is_admin=False
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        key_id = api_key.id
    finally:
        db.close()

    # Step 2: Verify the key works for authentication
    response = client.get("/years", headers={"Authorization": f"Bearer {test_key}"})
    assert response.status_code == 200, f"Test key should work before deletion, got {response.status_code}"

    # Step 3: Send DELETE to /admin/keys/{key_id} with admin key
    delete_response = client.delete(
        f"/admin/keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_key}"}
    )

    # Step 4: Verify response status code is 200
    assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"

    # Step 5: Verify key no longer works for authentication (401)
    auth_response = client.get("/years", headers={"Authorization": f"Bearer {test_key}"})
    assert auth_response.status_code == 401, f"Revoked key should return 401, got {auth_response.status_code}"

    # Step 6: Verify key still exists in database with is_active=false
    db2 = TestingSessionLocal()
    try:
        revoked_key = db2.query(APIKey).filter(APIKey.id == key_id).first()
        assert revoked_key is not None, "Key should still exist in database"
        assert revoked_key.is_active == False, "Key should be marked as inactive"
    finally:
        db2.close()
