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
    """Create all database tables, FTS5 index, and bootstrap admin key if configured."""
    Base.metadata.create_all(bind=engine)

    # Set up FTS5 full-text search
    from app.services.fts5 import setup_fts5
    setup_fts5(engine)

    # Bootstrap admin key from ADMIN_API_KEY env var if set
    if settings.admin_api_key:
        import hashlib
        from sqlalchemy.orm import sessionmaker as _sessionmaker
        from app.models.database import APIKey
        db = _sessionmaker(bind=engine)()
        try:
            key_hash = hashlib.sha256(settings.admin_api_key.encode()).hexdigest()
            if not db.query(APIKey).filter_by(key_hash=key_hash).first():
                db.add(APIKey(
                    key_hash=key_hash,
                    key_prefix=settings.admin_api_key[:8],
                    owner_name="admin",
                    rate_limit_tier="premium",
                    is_admin=True,
                ))
                db.commit()
        finally:
            db.close()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
