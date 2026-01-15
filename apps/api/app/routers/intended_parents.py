"""Intended Parents router - CRUD, status, notes for IPs."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_current_session,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import AuditEventType, IntendedParentStatus, EntityType, Role
from app.schemas.intended_parent import (
    IntendedParentCreate,
    IntendedParentUpdate,
    IntendedParentRead,
    IntendedParentListItem,
    IntendedParentStatusUpdate,
    IntendedParentStatusHistoryItem,
    IntendedParentStats,
)
from app.schemas.entity_note import EntityNoteCreate, EntityNoteRead, EntityNoteListItem
from app.services import ip_service, note_service, user_service
from app.utils.normalization import normalize_email

router = APIRouter(
    tags=["Intended Parents"],
    dependencies=[Depends(require_permission(POLICIES["intended_parents"].default))],
)


# =============================================================================
# List / Stats
# =============================================================================


@router.get("", response_model=dict)
def list_intended_parents(
    request: Request,
    status: list[str] = Query(None, description="Filter by status (multi-select)"),
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = Query(None, description="Search name or exact email/phone"),
    owner_id: UUID | None = None,
    include_archived: bool = False,
    created_after: str | None = Query(None, description="Created after (ISO format)"),
    created_before: str | None = Query(None, description="Created before (ISO format)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """List intended parents with filters and pagination."""
    items, total = ip_service.list_intended_parents(
        db,
        org_id=session.org_id,
        status=status,
        state=state,
        budget_min=budget_min,
        budget_max=budget_max,
        q=q,
        owner_id=owner_id,
        include_archived=include_archived,
        created_after=created_after,
        created_before=created_before,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pages = (total + per_page - 1) // per_page  # ceiling division
    from app.services import audit_service

    q_type = None
    if q:
        if "@" in q:
            q_type = "email"
        else:
            digit_count = sum(1 for ch in q if ch.isdigit())
            q_type = "phone" if digit_count >= 7 else "text"

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="intended_parent_list",
        target_id=None,
        request=request,
        details={
            "count": len(items),
            "page": page,
            "per_page": per_page,
            "include_archived": include_archived,
            "status": status,
            "state": state,
            "owner_id": str(owner_id) if owner_id else None,
            "budget_min": str(budget_min) if budget_min is not None else None,
            "budget_max": str(budget_max) if budget_max is not None else None,
            "created_after": created_after,
            "created_before": created_before,
            "q_type": q_type,
        },
    )
    db.commit()
    return {
        "items": [IntendedParentListItem.model_validate(ip) for ip in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/stats", response_model=IntendedParentStats)
def get_stats(
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get IP counts by status."""
    return ip_service.get_ip_stats(db, org_id=session.org_id)


# =============================================================================
# CRUD
# =============================================================================


@router.post(
    "",
    response_model=IntendedParentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_intended_parent(
    data: IntendedParentCreate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Create a new intended parent."""
    # Check for duplicate email
    existing = ip_service.get_ip_by_email(db, data.email, session.org_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intended parent with email '{data.email}' already exists",
        )

    ip = ip_service.create_intended_parent(
        db,
        org_id=session.org_id,
        user_id=session.user_id,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        state=data.state,
        budget=data.budget,
        notes_internal=data.notes_internal,
        owner_type=data.owner_type,
        owner_id=data.owner_id,
    )
    return ip


@router.get("/{ip_id}", response_model=IntendedParentRead)
def get_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get an intended parent by ID."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="intended_parent",
        target_id=ip.id,
        details={"view": "intended_parent_detail"},
    )
    db.commit()
    return ip


@router.patch(
    "/{ip_id}",
    response_model=IntendedParentRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_intended_parent(
    ip_id: UUID,
    data: IntendedParentUpdate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Update an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    # Check for duplicate email if changing
    if data.email:
        normalized_email = normalize_email(data.email)
        if normalized_email != ip.email:
            existing = ip_service.get_ip_by_email(db, data.email, session.org_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Intended parent with email '{data.email}' already exists",
                )

    updated = ip_service.update_intended_parent(
        db,
        ip,
        user_id=session.user_id,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        state=data.state,
        budget=data.budget,
        notes_internal=data.notes_internal,
        owner_type=data.owner_type,
        owner_id=data.owner_id,
    )
    return updated


# =============================================================================
# Status / Archive / Restore / Delete
# =============================================================================


@router.patch(
    "/{ip_id}/status",
    response_model=IntendedParentRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_status(
    ip_id: UUID,
    data: IntendedParentStatusUpdate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Change status of an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    # Validate status
    valid_statuses = [
        s.value
        for s in IntendedParentStatus
        if s not in (IntendedParentStatus.ARCHIVED, IntendedParentStatus.RESTORED)
    ]
    if data.status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    updated = ip_service.update_ip_status(db, ip, data.status, session.user_id, data.reason)
    return updated


@router.post(
    "/{ip_id}/archive",
    response_model=IntendedParentRead,
    dependencies=[Depends(require_csrf_header)],
)
def archive_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Archive (soft delete) an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    if ip.is_archived:
        raise HTTPException(status_code=400, detail="Already archived")

    return ip_service.archive_intended_parent(db, ip, session.user_id)


@router.post(
    "/{ip_id}/restore",
    response_model=IntendedParentRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Restore an archived intended parent (admin only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    if not ip.is_archived:
        raise HTTPException(status_code=400, detail="Not archived")

    # Check for duplicate email (another active IP might have same email now)
    existing = ip_service.get_ip_by_email(db, ip.email, session.org_id)
    if existing and existing.id != ip.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot restore: another active intended parent with email '{ip.email}' already exists",
        )

    return ip_service.restore_intended_parent(db, ip, session.user_id)


@router.delete(
    "/{ip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Hard delete an archived intended parent (admin only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    if not ip.is_archived:
        raise HTTPException(status_code=400, detail="Must archive before deleting")

    ip_service.delete_intended_parent(db, ip)


# =============================================================================
# Status History
# =============================================================================


@router.get("/{ip_id}/history", response_model=list[IntendedParentStatusHistoryItem])
def get_status_history(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get status history for an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    history = ip_service.get_ip_status_history(db, ip_id)

    # Resolve user names
    result = []
    for h in history:
        changed_by_name = None
        if h.changed_by_user_id:
            user = user_service.get_user_by_id(db, h.changed_by_user_id)
            changed_by_name = user.display_name if user else None

        result.append(
            IntendedParentStatusHistoryItem(
                id=h.id,
                old_status=h.old_status,
                new_status=h.new_status,
                reason=h.reason,
                changed_by_user_id=h.changed_by_user_id,
                changed_by_name=changed_by_name,
                changed_at=h.changed_at,
            )
        )

    return result


# =============================================================================
# Notes (polymorphic)
# =============================================================================


@router.get("/{ip_id}/notes", response_model=list[EntityNoteListItem])
def list_notes(
    ip_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """List notes for an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    notes = note_service.list_notes(db, session.org_id, EntityType.INTENDED_PARENT, ip_id)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_VIEW_NOTE,
        actor_user_id=session.user_id,
        target_type="intended_parent",
        target_id=ip_id,
        details={"notes_count": len(notes)},
        request=request,
    )
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="intended_parent",
        target_id=ip_id,
        request=request,
        details={"view": "notes", "notes_count": len(notes)},
    )
    db.commit()

    return notes


@router.post(
    "/{ip_id}/notes",
    response_model=EntityNoteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_note(
    ip_id: UUID,
    data: EntityNoteCreate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Add a note to an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    note = note_service.create_note(
        db=db,
        org_id=session.org_id,
        entity_type=EntityType.INTENDED_PARENT,
        entity_id=ip_id,
        author_id=session.user_id,
        content=data.content,
    )

    # Bump last_activity
    ip.last_activity = note.created_at
    db.commit()

    return note


@router.delete(
    "/{ip_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_note(
    ip_id: UUID,
    note_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_permission(POLICIES["intended_parents"].actions["edit"])),
):
    """Delete a note (author or admin only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")

    note = note_service.get_note(db, note_id, session.org_id)
    if not note or note.entity_id != ip_id:
        raise HTTPException(status_code=404, detail="Note not found")

    # Check permission: author or admin+
    if note.author_id != session.user_id and session.role not in (
        Role.ADMIN,
        Role.DEVELOPER,
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")

    note_service.delete_note(db, note)
