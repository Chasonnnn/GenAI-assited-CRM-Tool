"""Cases router - API endpoints for case management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access, can_modify_case
from app.core.deps import (
    CSRF_HEADER,
    can_archive,
    can_assign,
    can_hard_delete,
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
    require_roles,
)
from app.db.enums import CaseSource, CaseStatus, Role, ROLES_CAN_ARCHIVE
from app.db.models import User
from app.schemas.auth import UserSession
from app.schemas.case import (
    CaseAssign,
    CaseCreate,
    CaseHandoffDeny,
    CaseListItem,
    CaseListResponse,
    CaseRead,
    CaseStats,
    CaseStatusChange,
    CaseStatusHistoryRead,
    CaseUpdate,
)
from app.services import case_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter()


def _case_to_read(case, db: Session) -> CaseRead:
    """Convert Case model to CaseRead schema with joined user names."""
    assigned_to_name = None
    if case.assigned_to_user_id:
        user = db.query(User).filter(User.id == case.assigned_to_user_id).first()
        assigned_to_name = user.display_name if user else None
    
    return CaseRead(
        id=case.id,
        case_number=case.case_number,
        status=CaseStatus(case.status),
        source=CaseSource(case.source),
        assigned_to_user_id=case.assigned_to_user_id,
        assigned_to_name=assigned_to_name,
        created_by_user_id=case.created_by_user_id,
        full_name=case.full_name,
        email=case.email,
        phone=case.phone,
        state=case.state,
        date_of_birth=case.date_of_birth,
        race=case.race,
        height_ft=case.height_ft,
        weight_lb=case.weight_lb,
        is_age_eligible=case.is_age_eligible,
        is_citizen_or_pr=case.is_citizen_or_pr,
        has_child=case.has_child,
        is_non_smoker=case.is_non_smoker,
        has_surrogate_experience=case.has_surrogate_experience,
        num_deliveries=case.num_deliveries,
        num_csections=case.num_csections,
        is_archived=case.is_archived,
        archived_at=case.archived_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _case_to_list_item(case, db: Session) -> CaseListItem:
    """Convert Case model to CaseListItem schema."""
    assigned_to_name = None
    if case.assigned_to_user_id:
        user = db.query(User).filter(User.id == case.assigned_to_user_id).first()
        assigned_to_name = user.display_name if user else None
    
    return CaseListItem(
        id=case.id,
        case_number=case.case_number,
        status=CaseStatus(case.status),
        source=CaseSource(case.source),
        full_name=case.full_name,
        email=case.email,
        phone=case.phone,
        state=case.state,
        assigned_to_name=assigned_to_name,
        is_archived=case.is_archived,
        created_at=case.created_at,
    )


@router.get("/stats", response_model=CaseStats)
def get_case_stats(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get aggregated case statistics for dashboard."""
    from app.services import task_service
    
    stats = case_service.get_case_stats(db, session.org_id)
    
    # Add pending tasks count (cross-module)
    pending_tasks = task_service.count_pending_tasks(db, session.org_id)
    
    return CaseStats(
        total=stats["total"],
        by_status=stats["by_status"],
        this_week=stats["this_week"],
        this_month=stats["this_month"],
        pending_tasks=pending_tasks,
    )


@router.get("", response_model=CaseListResponse)
def list_cases(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    status: CaseStatus | None = None,
    source: CaseSource | None = None,
    assigned_to: UUID | None = None,
    q: str | None = Query(None, max_length=100),
    include_archived: bool = False,
):
    """
    List cases with filters and pagination.
    
    - Default excludes archived cases
    - Search (q) searches name, email, phone, case_number
    - Intake specialists only see Stage A statuses
    """
    cases, total = case_service.list_cases(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
        status=status,
        source=source,
        assigned_to=assigned_to,
        q=q,
        include_archived=include_archived,
        role_filter=session.role,  # Filter by user role
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return CaseListResponse(
        items=[_case_to_list_item(c, db) for c in cases],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("", response_model=CaseRead, status_code=201, dependencies=[Depends(require_csrf_header)])
def create_case(
    data: CaseCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new case."""
    try:
        case = case_service.create_case(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
        )
    except Exception as e:
        # Handle unique constraint violations
        if "uq_case_email_active" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="A case with this email already exists")
        raise
    
    return _case_to_read(case, db)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case by ID (respects role-based access)."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't view case_manager_only statuses
    check_case_access(case, session.role)
    
    return _case_to_read(case, db)


@router.patch("/{case_id}", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def update_case(
    case_id: UUID,
    data: CaseUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Update case fields.
    
    Requires: creator or manager+ (blocked after handoff for intake)
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role)
    
    # Permission check: must be able to modify
    if not can_modify_case(case, str(session.user_id), session.role):
        raise HTTPException(status_code=403, detail="Not authorized to update this case")
    
    try:
        case = case_service.update_case(db, case, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    return _case_to_read(case, db)


@router.patch("/{case_id}/status", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def change_status(
    case_id: UUID,
    data: CaseStatusChange,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Change case status (records history, respects access control)."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role)
    
    if case.is_archived:
        raise HTTPException(status_code=400, detail="Cannot change status of archived case")
    
    case = case_service.change_status(
        db=db,
        case=case,
        new_status=data.status,
        user_id=session.user_id,
        reason=data.reason,
    )
    return _case_to_read(case, db)


@router.patch("/{case_id}/assign", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def assign_case(
    case_id: UUID,
    data: CaseAssign,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Assign case to a user (or unassign with null).
    
    Requires: manager+ role
    """
    if not can_assign(session):
        raise HTTPException(status_code=403, detail="Only managers can assign cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Verify assignee exists and is in same org
    if data.user_id:
        from app.db.models import Membership
        membership = db.query(Membership).filter(
            Membership.user_id == data.user_id,
            Membership.organization_id == session.org_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    
    case = case_service.assign_case(db, case, data.user_id, session.user_id)
    return _case_to_read(case, db)


@router.post("/{case_id}/archive", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def archive_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Soft-delete (archive) a case.
    
    Requires: manager+ role
    """
    if not can_archive(session):
        raise HTTPException(status_code=403, detail="Only managers can archive cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = case_service.archive_case(db, case, session.user_id)
    return _case_to_read(case, db)


@router.post("/{case_id}/restore", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def restore_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Restore an archived case.
    
    Requires: manager+ role
    Fails if email is now used by another active case.
    """
    if not can_archive(session):
        raise HTTPException(status_code=403, detail="Only managers can restore cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.restore_case(db, case, session.user_id)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)


@router.delete("/{case_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a case.
    
    Requires: manager+ role AND case must be archived first.
    """
    if not can_hard_delete(session):
        raise HTTPException(status_code=403, detail="Only managers can delete cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if not case.is_archived:
        raise HTTPException(
            status_code=400, 
            detail="Case must be archived before permanent deletion"
        )
    
    case_service.hard_delete_case(db, case)
    return None


@router.get("/{case_id}/history", response_model=list[CaseStatusHistoryRead])
def get_case_history(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get status change history for a case."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    history = case_service.get_status_history(db, case_id, session.org_id)
    
    result = []
    for h in history:
        changed_by_name = None
        if h.changed_by_user_id:
            user = db.query(User).filter(User.id == h.changed_by_user_id).first()
            changed_by_name = user.display_name if user else None
        
        result.append(CaseStatusHistoryRead(
            id=h.id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_by_user_id=h.changed_by_user_id,
            changed_by_name=changed_by_name,
            reason=h.reason,
            changed_at=h.changed_at,
        ))
    
    return result


# =============================================================================
# Handoff Workflow Endpoints (Case Manager+ only)
# =============================================================================

@router.get("/handoff-queue", response_model=CaseListResponse)
def list_handoff_queue(
    session: UserSession = Depends(require_roles([Role.CASE_MANAGER, Role.MANAGER, Role.DEVELOPER])),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """
    List cases awaiting case manager review (status=pending_handoff).
    
    Requires: case_manager+ role
    """
    cases, total = case_service.list_handoff_queue(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return CaseListResponse(
        items=[_case_to_list_item(c, db) for c in cases],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("/{case_id}/accept", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def accept_handoff(
    case_id: UUID,
    session: UserSession = Depends(require_roles([Role.CASE_MANAGER, Role.MANAGER, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """
    Accept a pending_handoff case and transition to pending_match.
    
    Requires: case_manager+ role
    Returns 409 if case is not in pending_handoff status.
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.accept_handoff(db, case, session.user_id)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)


@router.post("/{case_id}/deny", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def deny_handoff(
    case_id: UUID,
    data: CaseHandoffDeny,
    session: UserSession = Depends(require_roles([Role.CASE_MANAGER, Role.MANAGER, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """
    Deny a pending_handoff case and revert to under_review.
    
    Requires: case_manager+ role
    Reason is optional but stored in status history.
    Returns 409 if case is not in pending_handoff status.
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.deny_handoff(db, case, session.user_id, data.reason)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)
