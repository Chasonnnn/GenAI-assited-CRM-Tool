"""Matches router - API endpoints for matching surrogates with intended parents."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_roles
from app.db.enums import CaseActivityType, MatchStatus, Role
from app.db.models import Case, IntendedParent, Match, User
from app.schemas.auth import UserSession

router = APIRouter(prefix="/matches", tags=["Matches"])


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


class MatchListResponse(BaseModel):
    """Paginated match list."""
    items: list[MatchListItem]
    total: int
    page: int
    per_page: int


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
    # Org-scoped lookups for defense in depth
    case_filter = [Case.id == match.case_id]
    ip_filter = [IntendedParent.id == match.intended_parent_id]
    if org_id:
        case_filter.append(Case.organization_id == org_id)
        ip_filter.append(IntendedParent.organization_id == org_id)
    
    case = db.query(Case).filter(*case_filter).first()
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
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/", response_model=MatchRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf_header)])
def create_match(
    data: MatchCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    match = Match(
        organization_id=session.org_id,
        case_id=data.case_id,
        intended_parent_id=data.intended_parent_id,
        status=MatchStatus.PROPOSED.value,
        compatibility_score=data.compatibility_score,
        proposed_by_user_id=session.user_id,
        notes=data.notes,
    )
    db.add(match)
    db.flush()
    
    # Log activity
    activity_service.log_case_activity(
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
    
    return _match_to_read(match, db, str(session.org_id))


@router.get("/", response_model=MatchListResponse)
def list_matches(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    case_id: UUID | None = Query(None, description="Filter by case ID"),
    intended_parent_id: UUID | None = Query(None, description="Filter by intended parent ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> MatchListResponse:
    """
    List matches with optional filters.
    
    Requires: Manager+ role
    """
    query = db.query(Match).filter(Match.organization_id == session.org_id)
    
    if status_filter:
        query = query.filter(Match.status == status_filter)
    if case_id:
        query = query.filter(Match.case_id == case_id)
    if intended_parent_id:
        query = query.filter(Match.intended_parent_id == intended_parent_id)
    
    total = query.count()
    matches = query.order_by(Match.proposed_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    # Batch load cases and IPs (org-scoped)
    case_ids = {m.case_id for m in matches}
    ip_ids = {m.intended_parent_id for m in matches}
    
    cases = {c.id: c for c in db.query(Case).filter(
        Case.organization_id == session.org_id,
        Case.id.in_(case_ids)
    ).all()} if case_ids else {}
    ips = {i.id: i for i in db.query(IntendedParent).filter(
        IntendedParent.organization_id == session.org_id,
        IntendedParent.id.in_(ip_ids)
    ).all()} if ip_ids else {}
    
    items = [_match_to_list_item(m, cases.get(m.case_id), ips.get(m.intended_parent_id)) for m in matches]
    
    return MatchListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{match_id}", response_model=MatchRead)
def get_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> MatchRead:
    """Get match details. Auto-transitions to 'reviewing' on first view by non-proposer."""
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
        match.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.put("/{match_id}/accept", response_model=MatchRead, dependencies=[Depends(require_csrf_header)])
def accept_match(
    match_id: UUID,
    data: MatchAcceptRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> MatchRead:
    """
    Accept a match.
    
    This will:
    - Set match status to accepted
    - Cancel all other pending matches for this case
    - Log activity
    
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
            detail=f"Cannot accept match with status: {match.status}"
        )
    
    # Accept this match
    match.status = MatchStatus.ACCEPTED.value
    match.reviewed_by_user_id = session.user_id
    match.reviewed_at = datetime.now(timezone.utc)
    if data.notes:
        match.notes = (match.notes or "") + "\n\n" + data.notes
    match.updated_at = datetime.now(timezone.utc)
    
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
    activity_service.log_case_activity(
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
    
    db.commit()
    db.refresh(match)
    
    return _match_to_read(match, db, str(session.org_id))


@router.put("/{match_id}/reject", response_model=MatchRead, dependencies=[Depends(require_csrf_header)])
def reject_match(
    match_id: UUID,
    data: MatchRejectRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
        match.notes = (match.notes or "") + "\n\n" + data.notes
    match.updated_at = datetime.now(timezone.utc)
    
    # Log activity
    activity_service.log_case_activity(
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
    
    return _match_to_read(match, db, str(session.org_id))


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_header)])
def cancel_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    activity_service.log_case_activity(
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> MatchRead:
    """Update match notes. Requires: Manager+ role."""
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.organization_id == session.org_id,
    ).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    
    match.notes = data.notes
    match.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(match)
    
    return _match_to_read(match, db, str(session.org_id))
