from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.v1.router import api_router
from app.core.logging import configure_logging

configure_logging()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Business Automation Platform",
    description=(
        "Lead intake and CRM automation API: website forms, webhook ingestion, "
        "deduplication, Google Sheets sync, email auto-replies and n8n workflows."
    ),
    version="0.2.0",
)

# Database schema is managed by Alembic: run "alembic upgrade head" before
# starting the app (the Docker Compose stack does this automatically).


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


@app.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    """Serve the static lead intake demo page."""
    return FileResponse(STATIC_DIR / "demo.html", media_type="text/html")


app.include_router(
    api_router,
    prefix="/api/v1",
)
