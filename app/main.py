from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.logging import configure_logging

from app.db.database import engine
from app.db.base import Base

# Import every model so SQLAlchemy registers the tables before create_all() runs.
from app.models.lead import Lead  # noqa: F401
from app.models.lead_follow_up import LeadFollowUp  # noqa: F401
from app.models.webhook_idempotency import WebhookIdempotency  # noqa: F401
from app.models.integration_event import IntegrationEvent  # noqa: F401

configure_logging()

app = FastAPI(
    title="Business Automation Platform",
    description=(
        "Lead intake and CRM automation API: website forms, webhook ingestion, "
        "deduplication, Google Sheets sync, email auto-replies and n8n workflows."
    ),
    version="0.2.0",
)

# Create the database tables on startup. For real deployments, replace this with
# a migration tool such as Alembic.
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    """Return basic service information."""
    return {
        "message": "Business Automation Platform",
        "version": "0.2.0",
    }


@app.get("/health")
def health():
    """Lightweight liveness probe."""
    return {
        "status": "ok",
    }


app.include_router(
    api_router,
    prefix="/api/v1",
)
