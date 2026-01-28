# ABOUTME: SQLAlchemy database models
# ABOUTME: Defines tables for api_keys, usage_logs, entities_master, and schema_metadata

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class APIKey(Base):
    """API key for authentication and rate limiting."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key_hash = Column(Text, unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    owner_email = Column(Text)
    owner_name = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    rate_limit_tier = Column(String(20), default="free")
    is_admin = Column(Boolean, default=False)
    notes = Column(Text)

    usage_logs = relationship("UsageLog", back_populates="api_key")


class UsageLog(Base):
    """Log of API requests for rate limiting and analytics."""
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(45))

    api_key = relationship("APIKey", back_populates="usage_logs")


class EntitiesMaster(Base):
    """Master table of stable entity identifiers (schools, districts, state)."""
    __tablename__ = "entities_master"

    id = Column(Integer, primary_key=True)
    rcdts = Column(Text, unique=True, nullable=False, index=True)
    entity_type = Column(Text, nullable=False, index=True)  # school | district | state | region
    name = Column(Text)
    city = Column(Text)
    county = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchemaMetadata(Base):
    """Metadata about columns in year-partitioned tables."""
    __tablename__ = "schema_metadata"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, index=True)
    table_name = Column(Text, nullable=False)  # schools_2025, districts_2025, etc.
    column_name = Column(Text, nullable=False)
    data_type = Column(Text)  # string | integer | float | percentage
    category = Column(Text, index=True)  # demographics | assessment | enrollment | attendance | etc.
    description = Column(Text)
    source_column_name = Column(Text)  # Original Excel column name
    is_suppressed_indicator = Column(Boolean, default=False)  # Marks columns that use * for privacy
