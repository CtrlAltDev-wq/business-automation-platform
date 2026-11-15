from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_webhook_secret
from app.db.database import get_db
from app.models.integration_event import IntegrationEvent
from app.schemas.integration import (
    IntegrationEventResponse,
    IntegrationProcessResponse,
)
from app.services import integration_service

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    # Operational endpoints, protected with the same shared secret as webhooks.
    dependencies=[Depends(verify_webhook_secret)],
)


@router.post(
    "/process",
    response_model=IntegrationProcessResponse,
)
def process_pending_events(
    db: Session = Depends(get_db),
):
    """Deliver all due integration events now (manual retry trigger)."""
    return integration_service.process_pending(db)


@router.get(
    "/events",
    response_model=list[IntegrationEventResponse],
)
def list_events(
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Inspect recent outbound events, including failures and retry state."""
    statement = (
        select(IntegrationEvent)
        .order_by(IntegrationEvent.id.desc())
        .limit(limit)
    )

    if status:
        statement = statement.where(IntegrationEvent.status == status.upper())

    return db.scalars(statement).all()
