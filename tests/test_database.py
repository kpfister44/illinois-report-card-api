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
