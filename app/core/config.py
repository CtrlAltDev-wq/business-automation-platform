from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory (two levels above app/core).
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env file."""

    # Shared secret expected in the X-Webhook-Secret header.
    # The default only allows the app and the test suite to start without a .env file;
    # always override it in real deployments.
    webhook_secret: str = "dev-secret-change-me"

    # SQLAlchemy database URL. SQLite by default; point it at PostgreSQL when needed,
    # e.g. postgresql+psycopg://app_user:password@127.0.0.1:5432/business_automation
    database_url: str = "sqlite:///./business.db"

    # Log every SQL statement when true.
    sql_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
