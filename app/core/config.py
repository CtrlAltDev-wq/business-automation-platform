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

    # ------------------------------------------------------------------
    # Integrations
    # ------------------------------------------------------------------
    # Master switch for outbound automations (Sheets / email / n8n).
    integrations_enabled: bool = True

    # Retry policy for failed outbound events.
    integration_max_attempts: int = 5
    integration_retry_base_seconds: int = 30

    # n8n: a webhook node URL that receives lead.created events.
    n8n_webhook_url: str | None = None

    # Google Sheets: service-account JSON file and target spreadsheet.
    google_service_account_file: str | None = None
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_range: str = "Leads!A:H"

    # SMTP: when smtp_host is empty the auto-reply is logged instead of sent.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@example.com"
    smtp_use_tls: bool = True
    auto_reply_subject: str = "Thanks for contacting us"
    auto_reply_body: str = (
        "Hi {name},\n\n"
        "thank you for getting in touch. We have received your message "
        "and will reply within one business day.\n\n"
        "Best regards,\nThe team"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
