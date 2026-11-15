from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IntegrationEventResponse(BaseModel):
    """Outbox row returned by the integrations API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime


class IntegrationProcessResponse(BaseModel):
    """Summary of one dispatcher run."""

    processed: int
    sent: int
    retrying: int
    failed: int
