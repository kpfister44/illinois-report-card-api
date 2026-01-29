# ABOUTME: Database connection and session management
# ABOUTME: Provides SQLAlchemy engine, session factory, and database initialization

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models.database import Base

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all database tables and FTS5 index."""
    Base.metadata.create_all(bind=engine)

    # Set up FTS5 full-text search
    from app.services.fts5 import setup_fts5
    setup_fts5(engine)


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
