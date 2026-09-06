"""Matches router - API endpoints for matching surrogates with intended parents."""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import match_service, workflow_triggers

router = APIRouter(
    prefix="/matches",
    tags=["Matches"],
    dependencies=[Depends(require_permission(POLICIES["matches"].default))],
)


# =============================================================================
# Schemas
# =============================================================================


class MatchCreate(BaseModel):
    """Request to propose a match."""

    surrogate_id: UUID | None = None
    donor_id: UUID | None = None
    intended_parent_id: UUID
    notes: str | None = None

    @model_validator(mode="after")
    def validate_participants(self):
        if (self.surrogate_id is None) == (self.donor_id is None):
            raise ValueError("Exactly one surrogate or donor is required")
        return self


class MatchRead(BaseModel):
    """Match response."""

    id: str
    match_number: str
    surrogate_id: str | None
    donor_id: str | None = None
    donor_name: str | None = None
    donor_number: str | None = None
    donor_stage_label: str | None = None
    match_kind: Literal["surrogate", "donor"] = "surrogate"
    closed_at: str | None = None
    closure_reason: str | None = None
    outcome: str | None = None
    intended_parent_id: str
    status: str
    proposed_by_user_id: str | None
    proposed_at: str
    reviewed_by_user_id: str | None
    reviewed_at: str | None
    notes: str | None
    rejection_reason: str | None
    created_at: str
    updated_at: str
    # Denormalized for convenience
    surrogate_number: str | None = None
    surrogate_name: str | None = None
    ip_name: str | None = None
    ip_number: str | None = None
    # Surrogate stage info for status sync
    surrogate_stage_id: str | None = None
    surrogate_stage_slug: str | None = None
    surrogate_stage_label: str | None = None


class MatchListItem(BaseModel):
    """Match list item with summary info."""

    id: str
    match_number: str
    surrogate_id: str | None
    donor_id: str | None = None
    donor_name: str | None = None
    donor_number: str | None = None
    donor_stage_label: str | None = None
    match_kind: Literal["surrogate", "donor"] = "surrogate"
    closed_at: str | None = None
    closure_reason: str | None = None
    outcome: str | None = None
    surrogate_number: str | None
    surrogate_name: str | None
    intended_parent_id: str
    ip_name: str | None
    ip_number: str | None = None
    status: str
    proposed_at: str
    # Surrogate stage info for status sync
    surrogate_stage_id: str | None = None
    surrogate_stage_slug: str | None = None
    surrogate_stage_label: str | None = None


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
    rejection_reason: str = Field(min_length=1)


class MatchCancelRequest(BaseModel):
    """Request to cancel an accepted match (admin approval required)."""

    reason: str | None = None


class MatchUpdateNotesRequest(BaseModel):
    """Request to update match notes."""

    notes: str


# =============================================================================
# Helper Functions
# =============================================================================


def _match_to_read(match: Any, db: Session, org_id: str | None = None) -> MatchRead:
    """Convert Match model to MatchRead schema with org-scoped lookups."""
    # Org-scoped lookups for defense in depth, with eager load for stage
    surrogate = match_service.get_surrogate_with_stage(
        db,
        match.surrogate_id,
        UUID(org_id) if org_id else None,
    )
    ip = match_service.get_intended_parent(
        db,
        match.intended_parent_id,
        UUID(org_id) if org_id else None,
    )

    donor = (
        match_service.get_donor(
            db, match.donor_id, UUID(org_id) if org_id else match.organization_id
        )
        if match.donor_id
        else None
    )
    return MatchRead(
        id=str(match.id),
        match_number=match.match_number,
        surrogate_id=str(match.surrogate_id) if match.surrogate_id else None,
        donor_id=str(match.donor_id) if match.donor_id else None,
        donor_name=donor.full_name if donor else None,
        donor_number=donor.donor_number if donor else None,
        donor_stage_label=donor.stage.label if donor and donor.stage else None,
        match_kind=match.match_kind,
        closed_at=match.closed_at.isoformat() if match.closed_at else None,
        closure_reason=match.closure_reason,
        outcome=match.outcome,
        intended_parent_id=str(match.intended_parent_id),
        status=match.status,
        proposed_by_user_id=str(match.proposed_by_user_id) if match.proposed_by_user_id else None,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else None,
        reviewed_by_user_id=str(match.reviewed_by_user_id) if match.reviewed_by_user_id else None,
        reviewed_at=match.reviewed_at.isoformat() if match.reviewed_at else None,
        notes=match.notes,
        rejection_reason=match.rejection_reason,
        created_at=match.created_at.isoformat(),
        updated_at=match.updated_at.isoformat(),
        surrogate_number=surrogate.surrogate_number if surrogate else None,
        surrogate_name=surrogate.full_name if surrogate else None,
        ip_name=ip.full_name if ip else None,
        ip_number=ip.intended_parent_number if ip else None,
        surrogate_stage_id=str(surrogate.stage.id) if surrogate and surrogate.stage else None,
        surrogate_stage_slug=surrogate.stage.slug if surrogate and surrogate.stage else None,
        surrogate_stage_label=surrogate.stage.label if surrogate and surrogate.stage else None,
    )


def _match_to_list_item(
    match: Any, surrogate: Any | None, ip: Any | None, donor: Any | None = None
) -> MatchListItem:
    """Convert Match to list item."""
    return MatchListItem(
        id=str(match.id),
        match_number=match.match_number,
        surrogate_id=str(match.surrogate_id) if match.surrogate_id else None,
        donor_id=str(match.donor_id) if match.donor_id else None,
        donor_name=donor.full_name if donor else None,
        donor_number=donor.donor_number if donor else None,
        donor_stage_label=donor.stage.label if donor and donor.stage else None,
        match_kind=match.match_kind,
        closed_at=match.closed_at.isoformat() if match.closed_at else None,
        closure_reason=match.closure_reason,
        outcome=match.outcome,
        surrogate_number=surrogate.surrogate_number if surrogate else None,
        surrogate_name=surrogate.full_name if surrogate else None,
        intended_parent_id=str(match.intended_parent_id),
        ip_name=ip.full_name if ip else None,
        ip_number=ip.intended_parent_number if ip else None,
        status=match.status,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else "",
        surrogate_stage_id=str(surrogate.stage.id) if surrogate and surrogate.stage else None,
        surrogate_stage_slug=surrogate.stage.slug if surrogate and surrogate.stage else None,
        surrogate_stage_label=surrogate.stage.label if surrogate and surrogate.stage else None,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/",
    response_model=MatchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_match(
    data: MatchCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    """
    Propose a new match between a surrogate and intended parent.

    Requires: Manager+ role
    """
    from app.services import record_access_service

    record_access_service.get_record_with_access(
        db, session, "donor" if data.donor_id else "surrogate", data.donor_id or data.surrogate_id
    )
    record_access_service.get_record_with_access(
        db, session, "intended_parent", data.intended_parent_id
    )
    # Verify IP exists and belongs to org
    ip = match_service.get_intended_parent(db, data.intended_parent_id, session.org_id)
    if not ip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intended parent not found"
        )

    # Check if match already exists
    existing = match_service.get_existing_match(
        db=db,
        org_id=session.org_id,
        surrogate_id=data.surrogate_id,
        donor_id=data.donor_id,
        intended_parent_id=data.intended_parent_id,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Match already exists with status: {existing.status}",
        )

    # Check if surrogate already has accepted match
    accepted_match = match_service.get_accepted_match_for_surrogate(
        db=db,
        org_id=session.org_id,
        surrogate_id=data.surrogate_id,
    )
    if data.surrogate_id and accepted_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Surrogate already has an accepted match",
        )

    try:
        match = match_service.create_match(
            db=db,
            org_id=session.org_id,
            surrogate_id=data.surrogate_id,
            donor_id=data.donor_id,
            intended_parent_id=data.intended_parent_id,
            proposed_by_user_id=session.user_id,
            notes=data.notes,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An open match already exists for these participants"
        )

    # Fire workflow trigger for match proposed
    if match.surrogate_id:
        workflow_triggers.trigger_match_proposed(db, match)

    return _match_to_read(match, db, str(session.org_id))


@router.get("/", response_model=MatchListResponse)
def list_matches(
    request: Request,
    status_filter: Annotated[str | None, "fastapi_param"] = Query(
        None, alias="status", description="Filter by status"
    ),
    surrogate_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by surrogate ID"
    ),
    intended_parent_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by intended parent ID"
    ),
    donor_id: Annotated[UUID | None, "fastapi_param"] = Query(None),
    match_kind: Annotated[Literal["surrogate", "donor"] | None, "fastapi_param"] = Query(None),
    q: Annotated[str | None, "fastapi_param"] = Query(
        None, max_length=100, description="Search surrogate/IP names"
    ),
    page: Annotated[int, "fastapi_param"] = Query(1, ge=1),
    per_page: Annotated[int, "fastapi_param"] = Query(20, ge=1, le=100),
    sort_by: Annotated[str | None, "fastapi_param"] = Query(None, description="Column to sort by"),
    sort_order: Annotated[str, "fastapi_param"] = Query(
        "desc", pattern="^(asc|desc)$", description="Sort direction"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchListResponse:
    """
    List matches with optional filters.

    Requires: Manager+ role
    """
    matches, total = match_service.list_matches(
        db=db,
        org_id=session.org_id,
        status_filter=status_filter,
        donor_id=donor_id,
        match_kind=match_kind,
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        q=q,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
        session=session,
    )

    # Batch load surrogates and IPs (org-scoped), with eager load for stage
    surrogate_ids = {m.surrogate_id for m in matches}
    ip_ids = {m.intended_parent_id for m in matches}

    surrogates = match_service.get_surrogates_with_stage_by_ids(
        db=db,
        org_id=session.org_id,
        surrogate_ids=surrogate_ids,
    )
    ips = match_service.get_intended_parents_by_ids(
        db=db,
        org_id=session.org_id,
        intended_parent_ids=ip_ids,
    )

    donor_ids = {m.donor_id for m in matches if m.donor_id}
    donors = match_service.get_donors_by_ids(db, session.org_id, donor_ids)
    items = [
        _match_to_list_item(
            m,
            surrogates.get(m.surrogate_id),
            ips.get(m.intended_parent_id),
            donors.get(m.donor_id),
        )
        for m in matches
    ]

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="match_list",
        target_id=None,
        request=request,
        details={
            "count": len(matches),
            "page": page,
            "per_page": per_page,
            "status": status_filter,
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "intended_parent_id": str(intended_parent_id) if intended_parent_id else None,
            "q_type": "text" if q else None,
        },
    )
    db.commit()

    return MatchListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/stats", response_model=MatchStatsResponse)
def get_match_stats(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchStatsResponse:
    """Get match counts by status for the org."""
    total, counts = match_service.get_match_stats(db, session.org_id, session=session)
    return MatchStatsResponse(total=total, by_status=counts)


@router.get("/{match_id}", response_model=MatchRead)
def get_match(
    match_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchRead:
    """Get match details. Auto-transitions to 'reviewing' on first view by non-proposer."""
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    # Auto-transition to reviewing on first view by someone other than proposer
    match = match_service.mark_match_reviewing_if_needed(
        db,
        match,
        actor_user_id=session.user_id,
        org_id=session.org_id,
    )

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id),
        },
    )
    db.commit()

    return _match_to_read(match, db, str(session.org_id))


@router.put(
    "/{match_id}/accept",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def accept_match(
    match_id: UUID,
    data: MatchAcceptRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    """
    Accept a match.

    This will:
    - Set match status to accepted
    - Cancel all other pending matches for this surrogate
    - Log activity

    Requires: Manager+ role
    """
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    try:
        match = match_service.accept_match(
            db=db,
            match=match,
            actor_user_id=session.user_id,
            actor_role=session.role,
            org_id=session.org_id,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This surrogate already has an accepted match (concurrent accept detected)",
        )

    # Fire workflow trigger for match accepted
    if match.surrogate_id:
        workflow_triggers.trigger_match_accepted(db, match)

    return _match_to_read(match, db, str(session.org_id))


@router.put(
    "/{match_id}/reject",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def reject_match(
    match_id: UUID,
    data: MatchRejectRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    """
    Reject a match with reason.

    Requires: Manager+ role
    """
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    try:
        match = match_service.reject_match(
            db=db,
            match=match,
            actor_user_id=session.user_id,
            org_id=session.org_id,
            rejection_reason=data.rejection_reason,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Fire workflow trigger for match rejected
    if match.surrogate_id:
        workflow_triggers.trigger_match_rejected(db, match)

    return _match_to_read(match, db, str(session.org_id))


@router.post(
    "/{match_id}/cancel-request",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def request_cancel_match(
    match_id: UUID,
    data: MatchCancelRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    """
    Request cancellation of an accepted match (requires admin approval).

    This will:
    - Create a pending status change request tied to the match
    - Mark the match as cancel_pending
    """
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    try:
        match = match_service.request_cancel_match(
            db=db,
            match=match,
            actor_user_id=session.user_id,
            org_id=session.org_id,
            reason=data.reason,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT if "pending cancellation request" in str(exc) else 400
        )
        raise HTTPException(status_code=status_code, detail=str(exc))

    return _match_to_read(match, db, str(session.org_id))


@router.delete(
    "/{match_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def cancel_match(
    match_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> Response:
    """
    Cancel a proposed match.

    Only proposed/reviewing matches can be cancelled.
    Requires: Manager+ role
    """
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    try:
        match_service.cancel_match(
            db=db,
            match=match,
            actor_user_id=session.user_id,
            org_id=session.org_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch(
    "/{match_id}/notes",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_match_notes(
    match_id: UUID,
    data: MatchUpdateNotesRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    """Update match notes. Requires: Manager+ role."""
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    match = match_service.update_match_notes(db, match=match, notes=data.notes)

    return _match_to_read(match, db, str(session.org_id))


# =============================================================================
# Match Events (Calendar) Endpoints
# =============================================================================


class MatchEventCreate(BaseModel):
    """Request to create a match event."""

    person_type: str = Field(pattern="^(surrogate|donor|ip)$")
    event_type: str = Field(pattern="^(medication|medical_exam|legal|delivery|custom)$")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str = "America/Los_Angeles"
    all_day: bool = False
    start_date: str | None = None  # YYYY-MM-DD for all-day events
    end_date: str | None = None


class MatchEventUpdate(BaseModel):
    """Request to update a match event."""

    person_type: str | None = Field(None, pattern="^(surrogate|donor|ip)$")
    event_type: str | None = Field(
        None, pattern="^(medication|medical_exam|legal|delivery|custom)$"
    )
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


def _event_to_read(event: Any) -> MatchEventRead:
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
    from_date: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter events from this date (YYYY-MM-DD)"
    ),
    to_date: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter events until this date (YYYY-MM-DD)"
    ),
    person_type: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter by person type (surrogate/ip)"
    ),
    event_type: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter by event type"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> list[MatchEventRead]:
    """
    List events for a match.

    Requires: Case Manager+ role
    """
    # Verify match exists and belongs to org
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    from_dt = None
    to_dt = None
    from_day = None
    to_day = None

    # Date filtering (timed events + overlapping all-day events)
    if from_date or to_date:
        try:
            from_dt = datetime.fromisoformat(from_date).replace(tzinfo=UTC) if from_date else None
            to_dt = (
                datetime.fromisoformat(to_date).replace(tzinfo=UTC) + timedelta(days=1)
                if to_date
                else None
            )
            from_day = date_type.fromisoformat(from_date) if from_date else None
            to_day = date_type.fromisoformat(to_date) if to_date else None
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    events = match_service.list_match_events(
        db=db,
        match_id=match_id,
        person_type=person_type,
        event_type=event_type,
        from_dt=from_dt,
        to_dt=to_dt,
        from_day=from_day,
        to_day=to_day,
    )

    return [_event_to_read(e) for e in events]


@router.post(
    "/{match_id}/events",
    response_model=MatchEventRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_match_event(
    match_id: UUID,
    data: MatchEventCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchEventRead:
    """
    Create an event for a match.

    Requires: Case Manager+ role
    """
    # Verify match exists and belongs to org
    match = match_service.get_match_with_access(db, session, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if data.person_type not in (match.match_kind, "ip"):
        raise HTTPException(status_code=400, detail="Event participant is not in this case")
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

    event = match_service.create_match_event(
        db=db,
        org_id=session.org_id,
        match_id=match_id,
        created_by_user_id=session.user_id,
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
    )

    return _event_to_read(event)


@router.get("/{match_id}/events/{event_id}", response_model=MatchEventRead)
def get_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchEventRead:
    """
    Get a specific match event.

    Requires: Case Manager+ role
    """
    match_service.get_match_with_access(db, session, match_id)
    event = match_service.get_match_event(
        db=db,
        match_id=match_id,
        event_id=event_id,
        org_id=session.org_id,
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    return _event_to_read(event)


@router.put(
    "/{match_id}/events/{event_id}",
    response_model=MatchEventRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_match_event(
    match_id: UUID,
    event_id: UUID,
    data: MatchEventUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchEventRead:
    """
    Update a match event.

    Requires: Case Manager+ role
    """
    match = match_service.get_match_with_access(db, session, match_id)
    event = match_service.get_match_event(
        db=db,
        match_id=match_id,
        event_id=event_id,
        org_id=session.org_id,
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if data.person_type is not None and data.person_type not in (match.match_kind, "ip"):
        raise HTTPException(status_code=400, detail="Event participant is not in this case")
    next_all_day = data.all_day if data.all_day is not None else event.all_day
    next_start_date = None
    next_end_date = None
    next_starts_at = None
    next_ends_at = None
    if next_all_day:
        next_start_date = (
            date_type.fromisoformat(data.start_date)
            if data.start_date is not None
            else event.start_date
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

    event = match_service.update_match_event(
        db=db,
        event=event,
        person_type=data.person_type,
        event_type=data.event_type,
        title=data.title,
        description=data.description,
        tz_name=data.timezone,
        all_day=next_all_day,
        start_date=next_start_date,
        end_date=next_end_date,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
    )

    return _event_to_read(event)


@router.delete(
    "/{match_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> Response:
    """
    Delete a match event.

    Requires: Case Manager+ role
    """
    match_service.get_match_with_access(db, session, match_id)
    event = match_service.get_match_event(
        db=db,
        match_id=match_id,
        event_id=event_id,
        org_id=session.org_id,
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    match_service.delete_match_event(db, event)


class MatchCompleteRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=2000)
    reason: str | None = Field(None, max_length=2000)


class AttemptCreate(BaseModel):
    attempt_type: Literal["embryo_transfer", "retrieval", "collection", "other"]
    status: Literal["planned", "in_progress", "completed", "cancelled"] = "planned"
    started_at: date_type | None = None
    ended_at: date_type | None = None
    outcome: str | None = Field(None, max_length=2000)


class AttemptUpdate(BaseModel):
    attempt_type: Literal["embryo_transfer", "retrieval", "collection", "other"] | None = None
    status: Literal["planned", "in_progress", "completed", "cancelled"] | None = None
    started_at: date_type | None = None
    ended_at: date_type | None = None
    outcome: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required(self):
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in ("attempt_type", "status")
        ):
            raise ValueError("Attempt type and status cannot be null")
        return self


class AttemptRead(AttemptCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    match_id: UUID
    sequence: int
    created_at: datetime
    updated_at: datetime


@router.put(
    "/{match_id}/complete", response_model=MatchRead, dependencies=[Depends(require_csrf_header)]
)
def complete_match(
    match_id: UUID,
    data: MatchCompleteRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
) -> MatchRead:
    match = match_service.get_match_with_access(db, session, match_id, write=True)
    try:
        match = match_service.complete_match(
            db, match, actor_user_id=session.user_id, org_id=session.org_id, **data.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _match_to_read(match, db, str(session.org_id))


@router.get("/{match_id}/attempts", response_model=list[AttemptRead])
def list_attempts(
    match_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    match = match_service.get_match_with_access(db, session, match_id)
    return match_service.list_attempts(db, match)


@router.post(
    "/{match_id}/attempts",
    response_model=AttemptRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_attempt(
    match_id: UUID,
    data: AttemptCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
):
    match = match_service.get_match_with_access(db, session, match_id, write=True)
    try:
        return match_service.save_attempt(
            db, match, actor_user_id=session.user_id, values=data.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch(
    "/{match_id}/attempts/{attempt_id}",
    response_model=AttemptRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_attempt(
    match_id: UUID,
    attempt_id: UUID,
    data: AttemptUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["matches"].actions["propose"])
    ),
):
    match = match_service.get_match_with_access(db, session, match_id, write=True)
    try:
        return match_service.save_attempt(
            db,
            match,
            actor_user_id=session.user_id,
            values=data.model_dump(exclude_unset=True),
            attempt_id=attempt_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
