from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUp
from app.schemas.lead import LeadCreate, LeadFollowUpCreate, LeadUpdate

# Allowed status changes for the sales pipeline. Terminal states cannot move further.
ALLOWED_STATUS_TRANSITIONS = {
    "NEW": {"CONTACTED", "LOST"},
    "CONTACTED": {"QUALIFIED", "LOST"},
    "QUALIFIED": {"CONVERTED", "LOST"},
    "CONVERTED": set(),
    "LOST": set(),
}


class InvalidLeadStatusTransition(Exception):
    """Raised when a lead is moved to a status that is not reachable from its current one."""


def create_lead(db: Session, data: LeadCreate):
    """Insert a new lead. Every lead starts in the NEW status."""
    lead = Lead(
        name=data.name,
        phone=data.phone,
        email=data.email,
        company=data.company,
        message=data.message,
        status="NEW",
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return lead


def get_lead_list(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    sort_by: str = "id",
    sort_order: str = "desc",
):
    """Return one page of leads with optional keyword/status filters and sorting."""
    # 1. Build filter conditions.
    conditions = []

    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(
            or_(
                Lead.name.ilike(pattern),
                Lead.phone.ilike(pattern),
                Lead.company.ilike(pattern),
            )
        )

    if status:
        conditions.append(Lead.status == status)

    # 2. Count the total number of matching rows.
    count_statement = (
        select(func.count())
        .select_from(Lead)
        .where(*conditions)
    )
    total = db.scalar(count_statement)

    # 3. Sortable columns whitelist; unknown values fall back to the primary key.
    sort_columns = {
        "id": Lead.id,
        "name": Lead.name,
        "status": Lead.status,
        "company": Lead.company,
    }

    column = sort_columns.get(sort_by, Lead.id)

    order_by = (
        asc(column)
        if sort_order == "asc"
        else desc(column)
    )

    # 4. Fetch the rows for the requested page.
    offset = (page - 1) * page_size

    statement = (
        select(Lead)
        .where(*conditions)
        .order_by(order_by)
        .offset(offset)
        .limit(page_size)
    )

    items = db.scalars(statement).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def get_lead_detail(db: Session, lead_id: int):
    """Return a single lead by id, or None when it does not exist."""
    return db.get(Lead, lead_id)


def update_lead(db: Session, lead_id: int, data: LeadUpdate):
    """Apply a partial update to a lead and return the refreshed row."""
    lead = db.get(Lead, lead_id)

    if lead is None:
        return None

    # Only fields explicitly provided by the client are updated.
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)

    db.commit()
    db.refresh(lead)

    return lead


def delete_lead(db: Session, lead_id: int):
    """Delete a lead (and its follow-ups) by id. Returns False when not found."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        return False

    db.delete(lead)
    db.commit()
    return True


def update_lead_status(
    db: Session,
    lead_id: int,
    new_status: str,
):
    """Move a lead to a new pipeline status, enforcing the transition rules."""
    try:
        # 1. Load the current lead.
        lead = db.get(Lead, lead_id)

        if lead is None:
            return None

        # 2. Look up the statuses reachable from the current one.
        allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(
            lead.status,
            set(),
        )

        # 3. Reject illegal transitions.
        if new_status not in allowed_statuses:
            raise InvalidLeadStatusTransition(
                f"Cannot change status from {lead.status} to {new_status}"
            )

        # 4. Apply the new status.
        lead.status = new_status

        # 5. Persist the change.
        db.commit()

        # 6. Reload the row so the response reflects the database state.
        db.refresh(lead)

        return lead

    except InvalidLeadStatusTransition:
        raise

    except Exception:
        # Roll back on any database error so the session stays usable.
        db.rollback()
        raise


def create_lead_follow_up(
    db: Session,
    lead_id: int,
    data: LeadFollowUpCreate,
):
    """Attach a follow-up note to an existing lead."""
    try:
        # 1. Make sure the parent lead exists.
        lead = db.get(Lead, lead_id)

        if lead is None:
            return None

        # 2. Build the follow-up linked to its lead.
        follow_up = LeadFollowUp(
            lead=lead,
            content=data.content,
        )

        # 3. Register it with the session.
        db.add(follow_up)

        # 4. Commit the transaction.
        db.commit()

        # 5. Reload database-generated fields such as id and created_at.
        db.refresh(follow_up)

        return follow_up

    except Exception:
        db.rollback()
        raise


def get_lead_follow_ups(
    db: Session,
    lead_id: int,
):
    """Return every follow-up of a lead, newest first."""
    # 1. Make sure the parent lead exists.
    lead = db.get(Lead, lead_id)

    if lead is None:
        return None

    # 2. Query the follow-ups of this lead, newest first.
    statement = (
        select(LeadFollowUp)
        .where(LeadFollowUp.lead_id == lead_id)
        .order_by(
            LeadFollowUp.created_at.desc(),
            LeadFollowUp.id.desc(),
        )
    )

    # 3. Return the result list.
    return db.scalars(statement).all()
