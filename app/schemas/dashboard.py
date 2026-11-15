from datetime import datetime

from pydantic import BaseModel


class RecentFollowUpResponse(BaseModel):
    """A follow-up note enriched with the name of its lead."""

    id: int
    lead_id: int
    lead_name: str
    content: str
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    """Aggregated metrics shown on the dashboard."""

    total_leads: int
    total_follow_ups: int
    status_counts: dict[str, int]
    integration_events: dict[str, int]
    recent_follow_ups: list[RecentFollowUpResponse]
