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

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
