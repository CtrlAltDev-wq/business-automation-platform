from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status as http_status,
)
from sqlalchemy.orm import Session

from app.core.security import verify_webhook_secret
from app.db.database import get_db
from app.schemas.lead import LeadCreate, LeadResponse
from app.services import lead_service

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=http_status.HTTP_201_CREATED,
    dependencies=[Depends(verify_webhook_secret)],
)
def receive_lead_webhook(
    data: LeadCreate,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
    ),
    db: Session = Depends(get_db),
):
    """Create a lead from an external webhook call.

    The X-Webhook-Secret header authenticates the caller and the Idempotency-Key
    header makes retries safe: a repeated key returns the original lead with
    200 instead of creating a duplicate.
    """
    try:
        lead, created = lead_service.create_lead_from_webhook(
            db=db,
            data=data,
            idempotency_key=idempotency_key,
        )
    except lead_service.IdempotencyConflict as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # A duplicate request returns 200 (already exists) instead of 201 (created).
    if not created:
        response.status_code = http_status.HTTP_200_OK

    return lead
