from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebhookIdempotency(Base):
    """Record of a processed webhook event, keyed by the caller's Idempotency-Key."""

    __tablename__ = "webhook_idempotency"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # Supplied by the caller; unique so the same event can never be processed twice.
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    # SHA-256 of the original payload, used to detect key reuse with different content.
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # Lead created by the first request carrying this key.
    lead_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
