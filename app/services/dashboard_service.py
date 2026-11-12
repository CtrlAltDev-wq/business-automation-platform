from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import LEAD_STATUSES
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

    # 5. Assemble the dashboard response.
    return {
        "total_leads": total_leads,
        "total_follow_ups": total_follow_ups,
        "status_counts": status_counts,
        "recent_follow_ups": [
            dict(row)
            for row in recent_rows
        ],
    }
