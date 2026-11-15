import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    EVENT_EMAIL_AUTO_REPLY,
    EVENT_FAILED,
    EVENT_N8N_LEAD_CREATED,
    EVENT_PENDING,
    EVENT_SENT,
    EVENT_SHEETS_APPEND,
)
from app.db.database import SessionLocal
from app.models.integration_event import IntegrationEvent
from app.models.lead import Lead
from app.services.integrations import mailer, n8n, sheets

logger = logging.getLogger(__name__)

# Every lead.created event fans out to these adapters, one outbox row per target.
EVENT_HANDLERS = {
    EVENT_SHEETS_APPEND: sheets.append_lead,
    EVENT_EMAIL_AUTO_REPLY: mailer.send_auto_reply,
    EVENT_N8N_LEAD_CREATED: n8n.trigger_lead_created,
}


def _utcnow() -> datetime:
    """Naive UTC timestamp, comparable on both SQLite and PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_lead_payload(lead: Lead, source: str) -> dict:
    """Snapshot the lead so retries always send the same data."""
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "company": lead.company,
        "message": lead.message,
        "status": lead.status,
        "source": source,
    }


def enqueue_lead_created(db: Session, lead: Lead, source: str) -> list[str]:
    """Queue one integration event per target and return the queued event types."""
    if not settings.integrations_enabled:
        logger.info("Integrations are disabled, skipping events for lead %s", lead.id)
        return []

    payload = build_lead_payload(lead, source)

    for event_type in EVENT_HANDLERS:
        db.add(
            IntegrationEvent(
                event_type=event_type,
                payload=payload,
                status=EVENT_PENDING,
            )
        )

    db.commit()

    logger.info(
        "Queued %s integration events for lead %s",
        len(EVENT_HANDLERS),
        lead.id,
    )

    return list(EVENT_HANDLERS)


def _retry_delay_seconds(attempts: int) -> int:
    """Exponential backoff: 30s, 60s, 120s, ... with the configured base delay."""
    return settings.integration_retry_base_seconds * (2 ** max(attempts - 1, 0))


def process_event(db: Session, event: IntegrationEvent) -> str:
    """Attempt one delivery and return the resulting event status."""
    handler = EVENT_HANDLERS.get(event.event_type)

    if handler is None:
        event.status = EVENT_FAILED
        event.last_error = f"No handler for event type {event.event_type}"
        db.commit()
        logger.error("Unknown integration event type %s", event.event_type)
        return event.status

    try:
        detail = handler(event.payload)
    except Exception as exc:
        event.attempts += 1
        event.last_error = f"{type(exc).__name__}: {exc}"

        if event.attempts >= settings.integration_max_attempts:
            event.status = EVENT_FAILED
            event.next_retry_at = None
        else:
            event.status = EVENT_PENDING
            event.next_retry_at = _utcnow() + timedelta(
                seconds=_retry_delay_seconds(event.attempts)
            )

        db.commit()

        logger.warning(
            "Integration %s for lead %s failed on attempt %s: %s",
            event.event_type,
            event.payload.get("id"),
            event.attempts,
            event.last_error,
        )

        return event.status

    event.status = EVENT_SENT
    event.last_error = None
    event.next_retry_at = None
    db.commit()

    logger.info(
        "Integration %s for lead %s delivered: %s",
        event.event_type,
        event.payload.get("id"),
        detail,
    )

    return event.status


def process_pending(db: Session, limit: int = 20) -> dict:
    """Deliver pending events whose retry delay has elapsed."""
    statement = (
        select(IntegrationEvent)
        .where(IntegrationEvent.status == EVENT_PENDING)
        .where(
            or_(
                IntegrationEvent.next_retry_at.is_(None),
                IntegrationEvent.next_retry_at <= _utcnow(),
            )
        )
        .order_by(IntegrationEvent.id.asc())
        .limit(limit)
    )

    events = db.scalars(statement).all()

    sent = retrying = failed = 0

    for event in events:
        status = process_event(db, event)

        if status == EVENT_SENT:
            sent += 1
        elif status == EVENT_FAILED:
            failed += 1
        else:
            retrying += 1

    return {
        "processed": len(events),
        "sent": sent,
        "retrying": retrying,
        "failed": failed,
    }


def run_pending_once(limit: int = 20) -> dict:
    """Open a short-lived session (for background tasks and the worker)."""
    db = SessionLocal()

    try:
        return process_pending(db, limit=limit)
    finally:
        db.close()
