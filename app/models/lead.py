from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead_follow_up import LeadFollowUp


class Lead(Base):
    """A sales lead captured from a customer inquiry."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Current status in the sales pipeline: NEW / CONTACTED / QUALIFIED / CONVERTED / LOST.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="NEW",
    )

    # One lead owns many follow-up notes; deleting the lead deletes them as well.
    follow_ups: Mapped[list["LeadFollowUp"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
