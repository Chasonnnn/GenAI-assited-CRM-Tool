"""Matches router - API endpoints for matching surrogates with intended parents."""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.db.enums import CaseActivityType, IntendedParentStatus, MatchStatus
from app.db.models import Case, IntendedParent, Match, IntendedParentStatusHistory
from app.schemas.auth import UserSession
from app.services import workflow_triggers, note_service

router = APIRouter(prefix="/matches", tags=["Matches"], dependencies=[Depends(require_permission(POLICIES["matches"].default))])


# =============================================================================
# Schemas
# =============================================================================

class MatchCreate(BaseModel):
    """Request to propose a match."""
    case_id: UUID
    intended_parent_id: UUID
    compatibility_score: float | None = Field(None, ge=0, le=100)
    notes: str | None = None


class MatchRead(BaseModel):
    """Match response."""
    id: str
    case_id: str
    intended_parent_id: str
    status: str
    compatibility_score: float | None
    proposed_by_user_id: str | None
    proposed_at: str
    reviewed_by_user_id: str | None
    reviewed_at: str | None
    notes: str | None
    rejection_reason: str | None
    created_at: str
    updated_at: str
    # Denormalized for convenience
    case_number: str | None = None
    case_name: str | None = None
    ip_name: str | None = None
    # Case stage info for status sync
    case_stage_id: str | None = None
    case_stage_slug: str | None = None
    case_stage_label: str | None = None


class MatchListItem(BaseModel):
    """Match list item with summary info."""
    id: str
    case_id: str
    case_number: str | None
    case_name: str | None
    intended_parent_id: str
    ip_name: str | None
    status: str
    compatibility_score: float | None
    proposed_at: str
    # Case stage info for status sync
    case_stage_id: str | None = None
    case_stage_slug: str | None = None
    case_stage_label: str | None = None


class MatchListResponse(BaseModel):
    """Paginated match list."""
    items: list[MatchListItem]
    total: int
    page: int
    per_page: int


class MatchStatsResponse(BaseModel):
    """Match stats summary."""
    total: int
    by_status: dict[str, int]


class MatchAcceptRequest(BaseModel):
    """Request to accept a match."""
    notes: str | None = None


class MatchRejectRequest(BaseModel):
    """Request to reject a match."""
    notes: str | None = None
    rejection_reason: str = Field(..., min_length=1)


class MatchUpdateNotesRequest(BaseModel):
    """Request to update match notes."""
    notes: str


# =============================================================================
# Helper Functions
# =============================================================================

def _match_to_read(match: Match, db: Session, org_id: str | None = None) -> MatchRead:
    """Convert Match model to MatchRead schema with org-scoped lookups."""
    from sqlalchemy.orm import joinedload
    # Org-scoped lookups for defense in depth, with eager load for stage
    case_filter = [Case.id == match.case_id]
    ip_filter = [IntendedParent.id == match.intended_parent_id]
    if org_id:
        case_filter.append(Case.organization_id == org_id)
        ip_filter.append(IntendedParent.organization_id == org_id)
    
    case = db.query(Case).options(joinedload(Case.stage)).filter(*case_filter).first()
    ip = db.query(IntendedParent).filter(*ip_filter).first()
    
    return MatchRead(
        id=str(match.id),
        case_id=str(match.case_id),
        intended_parent_id=str(match.intended_parent_id),
        status=match.status,
        compatibility_score=float(match.compatibility_score) if match.compatibility_score else None,
        proposed_by_user_id=str(match.proposed_by_user_id) if match.proposed_by_user_id else None,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else None,
        reviewed_by_user_id=str(match.reviewed_by_user_id) if match.reviewed_by_user_id else None,
        reviewed_at=match.reviewed_at.isoformat() if match.reviewed_at else None,
        notes=match.notes,
        rejection_reason=match.rejection_reason,
        created_at=match.created_at.isoformat(),
        updated_at=match.updated_at.isoformat(),
        case_number=case.case_number if case else None,
        case_name=case.full_name if case else None,
        ip_name=ip.full_name if ip else None,
        case_stage_id=str(case.stage.id) if case and case.stage else None,
        case_stage_slug=case.stage.slug if case and case.stage else None,
        case_stage_label=case.stage.label if case and case.stage else None,
    )


def _match_to_list_item(match: Match, case: Case | None, ip: IntendedParent | None) -> MatchListItem:
    """Convert Match to list item."""
    return MatchListItem(
        id=str(match.id),
        case_id=str(match.case_id),
        case_number=case.case_number if case else None,
        case_name=case.full_name if case else None,
        intended_parent_id=str(match.intended_parent_id),
        ip_name=ip.full_name if ip else None,
        status=match.status,
        compatibility_score=float(match.compatibility_score) if match.compatibility_score else None,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else "",
        case_stage_id=str(case.stage.id) if case and case.stage else None,
        case_stage_slug=case.stage.slug if case and case.stage else None,
        case_stage_label=case.stage.label if case and case.stage else None,
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/", response_model=MatchRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf_header)])
def create_match(
    data: MatchCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchRead:
    """
    Propose a new match between a surrogate (case) and intended parent.
    
    Requires: Manager+ role
    """
    from app.services import activity_service
    
    # Verify case exists and belongs to org
    case = db.query(Case).filter(
        Case.id == data.case_id,
        Case.organization_id == session.org_id,
    ).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    
    # Verify IP exists and belongs to org
    ip = db.query(IntendedParent).filter(
        IntendedParent.id == data.intended_parent_id,
        IntendedParent.organization_id == session.org_id,
    ).first()
    if not ip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intended parent not found")
    
    # Check if match already exists
    existing = db.query(Match).filter(
        Match.organization_id == session.org_id,
        Match.case_id == data.case_id,
        Match.intended_parent_id == data.intended_parent_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Match already exists with status: {existing.status}"
        )
    
    # Check if case already has accepted match
    accepted_match = db.query(Match).filter(
        Match.case_id == data.case_id,
        Match.status == MatchStatus.ACCEPTED.value,
    ).first()
    if accepted_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case already has an accepted match"
        )
    
    # Create match
    clean_notes = note_service.sanitize_html(data.notes) if data.notes else None

    match = Match(
        organization_id=session.org_id,
        case_id=data.case_id,
        intended_parent_id=data.intended_parent_id,
        status=MatchStatus.PROPOSED.value,
        compatibility_score=data.compatibility_score,
        proposed_by_user_id=session.user_id,
        notes=clean_notes,
    )
    db.add(match)
    db.flush()
    
    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=data.case_id,
        organization_id=session.org_id,
        activity_type=CaseActivityType.MATCH_PROPOSED,
        actor_user_id=session.user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(data.intended_parent_id),
            "compatibility_score": data.compatibility_score,
        }
    )
    
    db.commit()
    db.refresh(match)
    
    # Fire workflow trigger for match proposed
    workflow_triggers.trigger_match_proposed(db, match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.get("/", response_model=MatchListResponse)
def list_matches(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    case_id: UUID | None = Query(None, description="Filter by case ID"),
    intended_parent_id: UUID | None = Query(None, description="Filter by intended parent ID"),
    q: str | None = Query(None, max_length=100, description="Search case/IP names"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MatchListResponse:
    """
    List matches with optional filters.
    
    Requires: Manager+ role
    """
    from sqlalchemy import asc, desc, or_
    from sqlalchemy.orm import joinedload
    
    query = db.query(Match).filter(Match.organization_id == session.org_id)
    
    if status_filter:
        query = query.filter(Match.status == status_filter)
    if case_id:
        query = query.filter(Match.case_id == case_id)
    if intended_parent_id:
        query = query.filter(Match.intended_parent_id == intended_parent_id)
    
    # Search by case or IP name (requires join)
    if q:
        search_term = f"%{q}%"
        query = query.join(Case, Match.case_id == Case.id, isouter=True).join(
            IntendedParent, Match.intended_parent_id == IntendedParent.id, isouter=True
        ).filter(
            or_(
                Case.full_name.ilike(search_term),
                Case.case_number.ilike(search_term),
                IntendedParent.full_name.ilike(search_term),
            )
        )
    
    total = query.count()
    
    # Dynamic sorting
    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "status": Match.status,
        "compatibility_score": Match.compatibility_score,
        "proposed_at": Match.proposed_at,
        "created_at": Match.created_at,
    }
    
    if sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        query = query.order_by(Match.proposed_at.desc())
    
    matches = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Batch load cases and IPs (org-scoped), with eager load for case stage
    case_ids = {m.case_id for m in matches}
    ip_ids = {m.intended_parent_id for m in matches}
    
    cases = {c.id: c for c in db.query(Case).options(joinedload(Case.stage)).filter(
        Case.organization_id == session.org_id,
        Case.id.in_(case_ids)
    ).all()} if case_ids else {}
    ips = {i.id: i for i in db.query(IntendedParent).filter(
        IntendedParent.organization_id == session.org_id,
        IntendedParent.id.in_(ip_ids)
    ).all()} if ip_ids else {}
    
    items = [_match_to_list_item(m, cases.get(m.case_id), ips.get(m.intended_parent_id)) for m in matches]
    
    return MatchListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/stats", response_model=MatchStatsResponse)
def get_match_stats(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MatchStatsResponse:
    """Get match counts by status for the org."""
    total = db.query(Match).filter(Match.organization_id == session.org_id).count()
    
    counts = {status.value: 0 for status in MatchStatus}
    rows = db.query(Match.status, func.count(Match.id)).filter(
        Match.organization_id == session.org_id
    ).group_by(Match.status).all()
    
    for status, count in rows:
        counts[status] = count
    
    return MatchStatsResponse(total=total, by_status=counts)


@router.get("/{match_id}", response_model=MatchRead)
def get_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MatchRead:
    """Get match details. Auto-transitions to 'reviewing' on first view by non-proposer."""
    from app.services import activity_service
    
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    # Auto-transition to reviewing on first view by someone other than proposer
    if (
        match.status == MatchStatus.PROPOSED.value
        and match.proposed_by_user_id != session.user_id
    ):
        match.status = MatchStatus.REVIEWING.value
        match.reviewed_by_user_id = session.user_id
        match.reviewed_at = datetime.now(timezone.utc)
        match.updated_at = datetime.now(timezone.utc)
        
        # Log review start
        activity_service.log_activity(
            db=db,
            case_id=match.case_id,
            organization_id=session.org_id,
            activity_type=CaseActivityType.MATCH_REVIEWING,
            actor_user_id=session.user_id,
            details={
                "match_id": str(match.id),
                "intended_parent_id": str(match.intended_parent_id),
            }
        )
        
        db.commit()
        db.refresh(match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.put("/{match_id}/accept", response_model=MatchRead, dependencies=[Depends(require_csrf_header)])
def accept_match(
    match_id: UUID,
    data: MatchAcceptRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchRead:
    """
    Accept a match.
    
    This will:
    - Set match status to accepted
    - Cancel all other pending matches for this case
    - Log activity
    
    Requires: Manager+ role
    """
    from app.services import activity_service, case_service, pipeline_service
    
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept match with status: {match.status}"
        )

    # Update case stage to matched if configured
    case = db.query(Case).filter(
        Case.id == match.case_id,
        Case.organization_id == session.org_id,
    ).first()
    if case:
        current_stage = case.stage
        pipeline_id = current_stage.pipeline_id if current_stage else None
        if not pipeline_id:
            pipeline_id = pipeline_service.get_or_create_default_pipeline(
                db,
                session.org_id,
                session.user_id,
            ).id
        matched_stage = pipeline_service.get_stage_by_slug(db, pipeline_id, "matched")
        if matched_stage:
            case_service.change_status(
                db=db,
                case=case,
                new_stage_id=matched_stage.id,
                user_id=session.user_id,
                user_role=session.role,
                reason="Match accepted",
            )
    
    # Accept this match
    match.status = MatchStatus.ACCEPTED.value
    match.reviewed_by_user_id = session.user_id
    match.reviewed_at = datetime.now(timezone.utc)
    if data.notes:
        clean_notes = note_service.sanitize_html(data.notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(timezone.utc)

    # Update intended parent status to matched (if not already)
    ip = db.query(IntendedParent).filter(
        IntendedParent.id == match.intended_parent_id,
        IntendedParent.organization_id == session.org_id,
    ).first()
    if ip and ip.status != IntendedParentStatus.MATCHED.value:
        old_status = ip.status
        ip.status = IntendedParentStatus.MATCHED.value
        ip.last_activity = datetime.now(timezone.utc)
        ip.updated_at = datetime.now(timezone.utc)
        db.add(IntendedParentStatusHistory(
            intended_parent_id=ip.id,
            changed_by_user_id=session.user_id,
            old_status=old_status,
            new_status=IntendedParentStatus.MATCHED.value,
            reason="Match accepted",
        ))
    
    # Cancel all other pending matches for this case
    other_matches = db.query(Match).filter(
        Match.case_id == match.case_id,
        Match.id != match.id,
        Match.status.in_([MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]),
    ).all()
    
    for other in other_matches:
        other.status = MatchStatus.CANCELLED.value
        other.updated_at = datetime.now(timezone.utc)
    
    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=match.case_id,
        organization_id=session.org_id,
        activity_type=CaseActivityType.MATCH_ACCEPTED,
        actor_user_id=session.user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
            "cancelled_matches": len(other_matches),
        }
    )
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has an accepted match (concurrent accept detected)"
        )
    
    db.refresh(match)
    
    # Fire workflow trigger for match accepted
    workflow_triggers.trigger_match_accepted(db, match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.put("/{match_id}/reject", response_model=MatchRead, dependencies=[Depends(require_csrf_header)])
def reject_match(
    match_id: UUID,
    data: MatchRejectRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchRead:
    """
    Reject a match with reason.
    
    Requires: Manager+ role
    """
    from app.services import activity_service
    
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject match with status: {match.status}"
        )
    
    # Reject
    match.status = MatchStatus.REJECTED.value
    match.reviewed_by_user_id = session.user_id
    match.reviewed_at = datetime.now(timezone.utc)
    match.rejection_reason = data.rejection_reason
    if data.notes:
        clean_notes = note_service.sanitize_html(data.notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(timezone.utc)
    
    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=match.case_id,
        organization_id=session.org_id,
        activity_type=CaseActivityType.MATCH_REJECTED,
        actor_user_id=session.user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
            "rejection_reason": data.rejection_reason,
        }
    )
    
    db.commit()
    db.refresh(match)
    
    # Fire workflow trigger for match rejected
    workflow_triggers.trigger_match_rejected(db, match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_header)])
def cancel_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> None:
    """
    Cancel a proposed match.
    
    Only proposed/reviewing matches can be cancelled.
    Requires: Manager+ role
    """
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel match with status: {match.status}"
        )
    
    match.status = MatchStatus.CANCELLED.value
    match.updated_at = datetime.now(timezone.utc)
    
    # Log activity
    from app.services import activity_service
    activity_service.log_activity(
        db=db,
        case_id=match.case_id,
        organization_id=session.org_id,
        activity_type=CaseActivityType.MATCH_CANCELLED,
        actor_user_id=session.user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
        }
    )
    
    db.commit()


@router.patch("/{match_id}/notes", response_model=MatchRead, dependencies=[Depends(require_csrf_header)])
def update_match_notes(
    match_id: UUID,
    data: MatchUpdateNotesRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchRead:
    """Update match notes. Requires: Manager+ role."""
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    match.notes = note_service.sanitize_html(data.notes)
    match.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(match)
    
    return _match_to_read(match, db, str(session.org_id))


# =============================================================================
# Match Events (Calendar) Endpoints
# =============================================================================

class MatchEventCreate(BaseModel):
    """Request to create a match event."""
    person_type: str = Field(..., pattern="^(surrogate|ip)$")
    event_type: str = Field(..., pattern="^(medication|medical_exam|legal|delivery|custom)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str = "America/Los_Angeles"
    all_day: bool = False
    start_date: str | None = None  # YYYY-MM-DD for all-day events
    end_date: str | None = None


class MatchEventUpdate(BaseModel):
    """Request to update a match event."""
    person_type: str | None = Field(None, pattern="^(surrogate|ip)$")
    event_type: str | None = Field(None, pattern="^(medication|medical_exam|legal|delivery|custom)$")
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    all_day: bool | None = None
    start_date: str | None = None
    end_date: str | None = None


class MatchEventRead(BaseModel):
    """Match event response."""
    id: str
    match_id: str
    person_type: str
    event_type: str
    title: str
    description: str | None
    starts_at: str | None
    ends_at: str | None
    timezone: str
    all_day: bool
    start_date: str | None
    end_date: str | None
    created_by_user_id: str | None
    created_at: str
    updated_at: str


from app.db.models import MatchEvent
from datetime import date as date_type


def _event_to_read(event: MatchEvent) -> MatchEventRead:
    """Convert MatchEvent model to read schema."""
    return MatchEventRead(
        id=str(event.id),
        match_id=str(event.match_id),
        person_type=event.person_type,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        starts_at=event.starts_at.isoformat() if event.starts_at else None,
        ends_at=event.ends_at.isoformat() if event.ends_at else None,
        timezone=event.timezone,
        all_day=event.all_day,
        start_date=event.start_date.isoformat() if event.start_date else None,
        end_date=event.end_date.isoformat() if event.end_date else None,
        created_by_user_id=str(event.created_by_user_id) if event.created_by_user_id else None,
        created_at=event.created_at.isoformat(),
        updated_at=event.updated_at.isoformat(),
    )


@router.get("/{match_id}/events", response_model=list[MatchEventRead])
def list_match_events(
    match_id: UUID,
    from_date: str | None = Query(None, description="Filter events from this date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="Filter events until this date (YYYY-MM-DD)"),
    person_type: str | None = Query(None, description="Filter by person type (surrogate/ip)"),
    event_type: str | None = Query(None, description="Filter by event type"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> list[MatchEventRead]:
    """
    List events for a match.
    
    Requires: Case Manager+ role
    """
    # Verify match exists and belongs to org
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    query = db.query(MatchEvent).filter(MatchEvent.match_id == match_id)
    
    if person_type:
        query = query.filter(MatchEvent.person_type == person_type)
    if event_type:
        query = query.filter(MatchEvent.event_type == event_type)
    
    # Date filtering (timed events + overlapping all-day events)
    if from_date or to_date:
        try:
            from_dt = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc) if from_date else None
            to_dt = (
                datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
                if to_date
                else None
            )
            from_day = date_type.fromisoformat(from_date) if from_date else None
            to_day = date_type.fromisoformat(to_date) if to_date else None
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        date_filters = []

        timed_filters = []
        if from_dt:
            timed_filters.append(MatchEvent.starts_at >= from_dt)
        if to_dt:
            timed_filters.append(MatchEvent.starts_at < to_dt)
        if timed_filters:
            date_filters.append(and_(MatchEvent.starts_at.isnot(None), *timed_filters))

        all_day_filters = [MatchEvent.all_day.is_(True), MatchEvent.start_date.isnot(None)]
        if to_day:
            all_day_filters.append(MatchEvent.start_date <= to_day)
        if from_day:
            all_day_filters.append(func.coalesce(MatchEvent.end_date, MatchEvent.start_date) >= from_day)
        date_filters.append(and_(*all_day_filters))

        query = query.filter(or_(*date_filters))
    
    events = query.order_by(MatchEvent.starts_at, MatchEvent.start_date).all()
    
    return [_event_to_read(e) for e in events]


@router.post("/{match_id}/events", response_model=MatchEventRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf_header)])
def create_match_event(
    match_id: UUID,
    data: MatchEventCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchEventRead:
    """
    Create an event for a match.
    
    Requires: Case Manager+ role
    """
    # Verify match exists and belongs to org
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    if data.all_day:
        if not data.start_date:
            raise HTTPException(status_code=400, detail="start_date is required for all-day events")
        start_date = date_type.fromisoformat(data.start_date)
        end_date = date_type.fromisoformat(data.end_date) if data.end_date else None
        if end_date and end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
        starts_at = None
        ends_at = None
    else:
        if not data.starts_at:
            raise HTTPException(status_code=400, detail="starts_at is required for timed events")
        if data.ends_at and data.ends_at < data.starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be on or after starts_at")
        start_date = None
        end_date = None
        starts_at = data.starts_at
        ends_at = data.ends_at
    
    event = MatchEvent(
        organization_id=session.org_id,
        match_id=match_id,
        person_type=data.person_type,
        event_type=data.event_type,
        title=data.title,
        description=data.description,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=data.timezone,
        all_day=data.all_day,
        start_date=start_date,
        end_date=end_date,
        created_by_user_id=session.user_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return _event_to_read(event)


@router.get("/{match_id}/events/{event_id}", response_model=MatchEventRead)
def get_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MatchEventRead:
    """
    Get a specific match event.
    
    Requires: Case Manager+ role
    """
    event = db.query(MatchEvent).filter(
        MatchEvent.id == event_id,
        MatchEvent.match_id == match_id,
        MatchEvent.organization_id == session.org_id,
    ).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    return _event_to_read(event)


@router.put("/{match_id}/events/{event_id}", response_model=MatchEventRead, dependencies=[Depends(require_csrf_header)])
def update_match_event(
    match_id: UUID,
    event_id: UUID,
    data: MatchEventUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> MatchEventRead:
    """
    Update a match event.
    
    Requires: Case Manager+ role
    """
    event = db.query(MatchEvent).filter(
        MatchEvent.id == event_id,
        MatchEvent.match_id == match_id,
        MatchEvent.organization_id == session.org_id,
    ).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    next_all_day = data.all_day if data.all_day is not None else event.all_day
    if next_all_day:
        next_start_date = (
            date_type.fromisoformat(data.start_date) if data.start_date is not None else event.start_date
        )
        next_end_date = (
            date_type.fromisoformat(data.end_date) if data.end_date is not None else event.end_date
        )
        if not next_start_date:
            raise HTTPException(status_code=400, detail="start_date is required for all-day events")
        if next_end_date and next_end_date < next_start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    else:
        next_starts_at = data.starts_at if data.starts_at is not None else event.starts_at
        next_ends_at = data.ends_at if data.ends_at is not None else event.ends_at
        if not next_starts_at:
            raise HTTPException(status_code=400, detail="starts_at is required for timed events")
        if next_ends_at and next_ends_at < next_starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be on or after starts_at")

    # Update fields
    if data.person_type is not None:
        event.person_type = data.person_type
    if data.event_type is not None:
        event.event_type = data.event_type
    if data.title is not None:
        event.title = data.title
    if data.description is not None:
        event.description = data.description
    if data.timezone is not None:
        event.timezone = data.timezone
    event.all_day = next_all_day
    if next_all_day:
        event.start_date = next_start_date
        event.end_date = next_end_date
        event.starts_at = None
        event.ends_at = None
    else:
        event.start_date = None
        event.end_date = None
        event.starts_at = next_starts_at
        event.ends_at = next_ends_at
    
    event.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(event)
    
    return _event_to_read(event)


@router.delete("/{match_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_header)])
def delete_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["matches"].actions["propose"])),
) -> None:
    """
    Delete a match event.
    
    Requires: Case Manager+ role
    """
    event = db.query(MatchEvent).filter(
        MatchEvent.id == event_id,
        MatchEvent.match_id == match_id,
        MatchEvent.organization_id == session.org_id,
    ).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    db.delete(event)
    db.commit()
