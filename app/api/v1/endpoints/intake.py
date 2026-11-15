from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status as http_status,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.intake import FormSubmission, IntakeResponse
from app.services import intake_service, integration_service

router = APIRouter(
    prefix="/intake",
    tags=["intake"],
)


@router.post(
    "/forms",
    response_model=IntakeResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def submit_form(
    submission: FormSubmission,
    response: Response,
    db: Session = Depends(get_db),
):
    """Turn a website form submission into a lead.

    Missing contact details are recovered from the free-text message, a
    submission that matches an existing lead is stored as a follow-up instead of
    a second lead, and the outbound automations (Sheets / email / n8n) are queued
    and attempted right away. Failed deliveries stay in the outbox for the worker.
    """
    source = (submission.source or "website_form").strip() or "website_form"

    try:
        lead, duplicate, extracted_fields = intake_service.submit_form(
            db,
            submission,
            source,
        )
    except intake_service.IntakeValidationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    events_queued = integration_service.enqueue_lead_created(db, lead, source)

    # A duplicate submission returns 200 (already known) instead of 201.
    if duplicate:
        response.status_code = http_status.HTTP_200_OK

    # First delivery attempt happens inline; retries are handled by the worker.
    if events_queued:
        integration_service.process_pending(db, limit=len(events_queued))

    return {
        "lead": lead,
        "duplicate": duplicate,
        "extracted_fields": extracted_fields,
        "events_queued": events_queued,
    }
