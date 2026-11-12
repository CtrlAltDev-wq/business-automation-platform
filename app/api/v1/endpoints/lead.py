from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.lead import (
    LeadCreate,
    LeadFollowUpCreate,
    LeadFollowUpResponse,
    LeadPageResponse,
    LeadResponse,
    LeadStatusUpdate,
    LeadUpdate,
)
from app.services import lead_service

router = APIRouter(
    prefix="/leads",
    tags=["leads"],
)


@router.post(
    "",
    response_model=LeadResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_lead(data: LeadCreate, db: Session = Depends(get_db)):
    """Create a new lead."""
    return lead_service.create_lead(db, data)


@router.get("", response_model=LeadPageResponse)
def get_lead_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
    sort_by: str = "id",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    """List leads with pagination, keyword search, status filter and sorting."""
    return lead_service.get_lead_list(
        db=db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead_detail(lead_id: int, db: Session = Depends(get_db)):
    """Return a single lead by id."""
    lead = lead_service.get_lead_detail(db, lead_id)

    if lead is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db)):
    """Partially update an existing lead."""
    lead = lead_service.update_lead(db, lead_id, data)

    if lead is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return lead


@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    """Delete a lead together with its follow-ups."""
    success = lead_service.delete_lead(db, lead_id)

    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return {"message": "Lead deleted successfully"}


@router.patch("/{lead_id}/status", response_model=LeadResponse)
def update_lead_status(
    lead_id: int,
    data: LeadStatusUpdate,
    db: Session = Depends(get_db),
):
    """Move a lead to another pipeline status."""
    try:
        lead = lead_service.update_lead_status(
            db=db,
            lead_id=lead_id,
            new_status=data.status,
        )
    except lead_service.InvalidLeadStatusTransition as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if lead is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return lead


@router.post(
    "/{lead_id}/follow-ups",
    response_model=LeadFollowUpResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_lead_follow_up(
    lead_id: int,
    data: LeadFollowUpCreate,
    db: Session = Depends(get_db),
):
    """Add a follow-up note to a lead."""
    follow_up = lead_service.create_lead_follow_up(
        db=db,
        lead_id=lead_id,
        data=data,
    )

    if follow_up is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return follow_up


@router.get(
    "/{lead_id}/follow-ups",
    response_model=list[LeadFollowUpResponse],
)
def get_lead_follow_ups(
    lead_id: int,
    db: Session = Depends(get_db),
):
    """List all follow-up notes of a lead, newest first."""
    follow_ups = lead_service.get_lead_follow_ups(
        db=db,
        lead_id=lead_id,
    )

    if follow_ups is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return follow_ups
