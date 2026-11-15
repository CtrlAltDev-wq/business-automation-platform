from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntegrationEvent(Base):
    """Outbox row for an outbound integration call (Sheets, email or n8n).

    The event is written in the same transaction as the lead, then dispatched by
    the worker. Keeping the payload and the failure state in the database makes
    retries safe across process restarts.
    """

    __tablename__ = "integration_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # One of app.core.constants.INTEGRATION_EVENT_TYPES.
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Snapshot of the lead, so retries always send the same data.
    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    # PENDING / SENT / FAILED.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )

    # Number of delivery attempts that ended with an error.
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Message of the last failure, useful when inspecting retries.
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Earliest moment the worker may retry this event.
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
