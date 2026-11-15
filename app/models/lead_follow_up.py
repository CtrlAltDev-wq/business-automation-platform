from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead


class LeadFollowUp(Base):
    """A single follow-up note attached to a lead."""

    __tablename__ = "lead_follow_ups"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Parent lead this follow-up belongs to.
    lead: Mapped["Lead"] = relationship(
        back_populates="follow_ups",
    )
