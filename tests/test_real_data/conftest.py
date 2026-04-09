# ABOUTME: Fixtures for real-data integration tests
# ABOUTME: Points at data/reportcard.db and skips all tests if the DB is absent or empty

import hashlib
import os
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.database import APIKey

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
REAL_DB_PATH = os.path.join(PROJECT_ROOT, "data", "reportcard.db")
REAL_DB_URL = f"sqlite:///{REAL_DB_PATH}"

_real_engine = None
_RealSessionLocal = None


def _get_real_engine():
    global _real_engine, _RealSessionLocal
    if _real_engine is None:
        _real_engine = create_engine(REAL_DB_URL, connect_args={"check_same_thread": False})
        _RealSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_real_engine)
    return _real_engine, _RealSessionLocal


def _db_is_populated():
    """Return True if the real DB exists and has schools_2024 data."""
    if not os.path.exists(REAL_DB_PATH):
        return False
    try:
        engine, _ = _get_real_engine()
        tables = inspect(engine).get_table_names()
        if "schools_2024" not in tables:
            return False
        with engine.connect() as conn:
            from sqlalchemy import text
            count = conn.execute(text("SELECT COUNT(*) FROM schools_2024")).scalar()
            return count > 0
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_real_db():
    """Skip the entire module if the real database is absent or unpopulated."""
    if not _db_is_populated():
        pytest.skip(
            "Real database not available — run the import pipeline first "
            "(data/reportcard.db must exist and contain schools_2024 data)"
        )


@pytest.fixture(scope="session")
def real_client(require_real_db):
    """FastAPI TestClient wired to the real database."""
    _, RealSessionLocal = _get_real_engine()

    def override_get_db():
        db = RealSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="session")
def auth_header(require_real_db):
    """
    Creates a temporary premium API key in the real DB for the test session.
    Deletes it on teardown.
    """
    _, RealSessionLocal = _get_real_engine()
    raw_key = f"real_data_test_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db = RealSessionLocal()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix="real_dat",
        owner_name="real_data_test_suite",
        rate_limit_tier="premium",
        is_active=True,
        is_admin=False,
    )
    db.add(api_key)
    db.commit()
    key_id = api_key.id
    db.close()

    yield {"Authorization": f"Bearer {raw_key}"}

    # Cleanup
    db = RealSessionLocal()
    db.query(APIKey).filter(APIKey.id == key_id).delete()
    db.commit()
    db.close()
