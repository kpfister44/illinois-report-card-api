# ABOUTME: Application configuration and settings
# ABOUTME: Loads settings from environment variables using pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(env_file=".env")

    environment: str = "development"
    database_url: str = "sqlite:///./data/reportcard.db"
    admin_api_key: str | None = None
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
