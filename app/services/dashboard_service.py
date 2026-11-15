from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import INTEGRATION_EVENT_STATUSES, LEAD_STATUSES
from app.models.integration_event import IntegrationEvent
from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUp

# Number of recent follow-ups shown on the dashboard.
RECENT_FOLLOW_UP_LIMIT = 5


def get_dashboard_summary(db: Session):
    """Aggregate lead/follow-up counters and the most recent follow-ups."""
    # 1. Count all leads.
    total_leads_statement = (
        select(func.count())
        .select_from(Lead)
    )

    total_leads = db.scalar(total_leads_statement) or 0

    # 2. Count all follow-up notes.
    total_follow_ups_statement = (
        select(func.count())
        .select_from(LeadFollowUp)
    )

    total_follow_ups = db.scalar(total_follow_ups_statement) or 0

    # 3. Count leads per pipeline status.
    status_statement = (
        select(
            Lead.status,
            func.count(Lead.id),
        )
        .group_by(Lead.status)
    )

    status_rows = db.execute(status_statement).all()

    # Pre-fill every status so stages without data still show up as zero.
    status_counts = {
        status: 0
        for status in LEAD_STATUSES
    }

    # Overwrite the counters with the actual database values.
    for lead_status, count in status_rows:
        status_counts[lead_status] = count

    # 4. Fetch the latest follow-ups together with their lead name.
    recent_statement = (
        select(
            LeadFollowUp.id,
            LeadFollowUp.lead_id,
            Lead.name.label("lead_name"),
            LeadFollowUp.content,
            LeadFollowUp.created_at,
        )
        .join(
            Lead,
            LeadFollowUp.lead_id == Lead.id,
        )
        .order_by(
            LeadFollowUp.created_at.desc(),
            LeadFollowUp.id.desc(),
        )
        .limit(RECENT_FOLLOW_UP_LIMIT)
    )

    recent_rows = (
        db.execute(recent_statement)
        .mappings()
        .all()
    )

    # 5. Count outbound integration events per status (delivery health).
    event_statement = (
        select(
            IntegrationEvent.status,
            func.count(IntegrationEvent.id),
        )
        .group_by(IntegrationEvent.status)
    )

    event_rows = db.execute(event_statement).all()

    integration_events = {
        status: 0
        for status in INTEGRATION_EVENT_STATUSES
    }

    for event_status, count in event_rows:
        integration_events[event_status] = count

    # 6. Assemble the dashboard response.
    return {
        "total_leads": total_leads,
        "total_follow_ups": total_follow_ups,
        "status_counts": status_counts,
        "integration_events": integration_events,
        "recent_follow_ups": [
            dict(row)
            for row in recent_rows
        ],
    }
