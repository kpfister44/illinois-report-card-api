# ABOUTME: Tests for database initialization and session management
# ABOUTME: Validates database setup, table creation, and session handling

import pytest
from sqlalchemy import create_engine, text, inspect
from app.database import init_db, get_db


def test_init_db_creates_tables_and_fts5():
    """Test init_db creates all tables including FTS5 index."""
    # Create a temporary in-memory database for this test
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # Temporarily replace the engine in the module
    import app.database
    original_engine = app.database.engine
    app.database.engine = test_engine

    try:
        # Run init_db
        init_db()

        # Verify tables were created
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        # Check for core tables
        assert "api_keys" in tables
        assert "entities_master" in tables
        assert "schema_metadata" in tables
        assert "usage_logs" in tables
        assert "import_jobs" in tables

        # Check for FTS5 virtual table
        with test_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities_fts'"
            ))
            fts_table = result.fetchone()
            assert fts_table is not None, "FTS5 virtual table should be created"

    finally:
        # Restore original engine
        app.database.engine = original_engine


def test_get_db_yields_session():
    """Test get_db dependency yields a database session and closes it."""
    # Get the generator
    db_gen = get_db()

    # Get the session
    db = next(db_gen)

    # Verify we got a session
    from sqlalchemy.orm import Session
    assert isinstance(db, Session)

    # Verify session is usable
    from app.models.database import APIKey
    result = db.query(APIKey).count()  # Should not raise an error
    assert result >= 0

    # Close the generator (simulates finally block)
    try:
        next(db_gen)
    except StopIteration:
        pass  # Expected

    # Session should be closed
    # Note: SQLAlchemy sessions don't have a simple "is_closed" check,
    # but the generator cleanup should have run


def test_app_startup_calls_init_db():
    """App lifespan calls init_db() on startup."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from app.main import app

    with patch("app.main.init_db") as mock_init_db:
        with TestClient(app):
            mock_init_db.assert_called_once()


class TestAdminKeyBootstrap:
    """Tests for ADMIN_API_KEY bootstrap behavior in init_db()."""

    def _run_init_db_with_settings(self, test_engine, mock_settings):
        """Helper: run init_db() with a patched engine and settings."""
        import app.database
        original_engine = app.database.engine
        original_settings = app.database.settings
        app.database.engine = test_engine
        app.database.settings = mock_settings
        try:
            init_db()
        finally:
            app.database.engine = original_engine
            app.database.settings = original_settings

    def _make_engine(self):
        from sqlalchemy import create_engine as _ce
        return _ce("sqlite:///:memory:", connect_args={"check_same_thread": False})

    def _make_settings(self, admin_api_key=None):
        from app.config import Settings
        return Settings(admin_api_key=admin_api_key, database_url="sqlite:///:memory:")

    def test_bootstrap_inserts_admin_key_when_env_set(self):
        """init_db() inserts an admin APIKey row when ADMIN_API_KEY is set."""
        import hashlib
        from sqlalchemy.orm import sessionmaker
        from app.models.database import APIKey

        engine = self._make_engine()
        settings = self._make_settings(admin_api_key="rcadmin_testkey123")
        self._run_init_db_with_settings(engine, settings)

        Session = sessionmaker(bind=engine)
        db = Session()
        keys = db.query(APIKey).all()
        db.close()

        assert len(keys) == 1
        key = keys[0]
        assert key.is_admin is True
        assert key.rate_limit_tier == "premium"
        assert key.is_active is True
        assert key.key_prefix == "rcadmin_"
        expected_hash = hashlib.sha256("rcadmin_testkey123".encode()).hexdigest()
        assert key.key_hash == expected_hash

    def test_bootstrap_is_idempotent(self):
        """Calling init_db() twice with the same ADMIN_API_KEY does not create duplicate rows."""
        from sqlalchemy.orm import sessionmaker
        from app.models.database import APIKey

        engine = self._make_engine()
        settings = self._make_settings(admin_api_key="rcadmin_testkey123")
        self._run_init_db_with_settings(engine, settings)
        self._run_init_db_with_settings(engine, settings)

        Session = sessionmaker(bind=engine)
        db = Session()
        count = db.query(APIKey).count()
        db.close()

        assert count == 1

    def test_no_bootstrap_when_admin_api_key_unset(self):
        """init_db() does not insert any APIKey row when ADMIN_API_KEY is not set."""
        from sqlalchemy.orm import sessionmaker
        from app.models.database import APIKey

        engine = self._make_engine()
        settings = self._make_settings(admin_api_key=None)
        self._run_init_db_with_settings(engine, settings)

        Session = sessionmaker(bind=engine)
        db = Session()
        count = db.query(APIKey).count()
        db.close()

        assert count == 0
