import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Keep the test suite on SQLite even when .env points the app at PostgreSQL.
os.environ["DATABASE_URL"] = "sqlite://"

# Force every integration into dry-run mode. Real environment variables take
# priority over .env, and tests must never call n8n / Google Sheets / SMTP even
# when the developer exported those credentials in the current shell.
os.environ.update(
    {
        "N8N_WEBHOOK_URL": "",
        "GOOGLE_SERVICE_ACCOUNT_FILE": "",
        "GOOGLE_SHEETS_SPREADSHEET_ID": "",
        "SMTP_HOST": "",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
    }
)

from app.db.base import Base  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.main import app  # noqa: E402

# In-memory test database shared across connections by StaticPool.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture
def client():
    """Provide a TestClient wired to a fresh in-memory database for each test."""
    # Create tables before the test and drop them afterwards.
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Replace the production database dependency with the test one.
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up data and dependency overrides.
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
