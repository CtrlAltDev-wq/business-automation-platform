from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lead import LeadResponse


class FormSubmission(BaseModel):
    """Payload sent by a website form.

    Unknown fields are accepted on purpose: form builders add their own metadata
    and the intake service can still extract contact details from free text.
    """

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=30)
    company: Optional[str] = Field(default=None, max_length=255)
    message: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=50)


class IntakeResponse(BaseModel):
    """Result of a website form submission."""

    lead: LeadResponse
    duplicate: bool
    extracted_fields: list[str]
    events_queued: list[str]
