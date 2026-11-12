from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import LeadStatus


class LeadCreate(BaseModel):
    """Payload for creating a new lead."""

    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    message: Optional[str] = None


class LeadStatusUpdate(BaseModel):
    """Payload for moving a lead to another pipeline stage."""

    status: LeadStatus


class LeadUpdate(BaseModel):
    """Payload for updating lead fields; omitted fields stay unchanged."""

    name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    message: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    status: str


class LeadPageResponse(BaseModel):
    """Paginated lead list."""

    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    pages: int


class LeadFollowUpCreate(BaseModel):
    """Payload for adding a follow-up note to a lead."""

    content: str = Field(min_length=1, max_length=2000)


class LeadFollowUpResponse(BaseModel):
    """Follow-up note returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    content: str
    created_at: datetime
