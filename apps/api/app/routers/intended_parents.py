"""Intended Parents router - CRUD, status, notes for IPs."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_session, require_role
from app.db.enums import Role, IntendedParentStatus, EntityType
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
from app.services import ip_service, note_service

router = APIRouter(tags=["Intended Parents"])


# =============================================================================
# List / Stats
# =============================================================================

@router.get("", response_model=dict)
def list_intended_parents(
    status: list[str] = Query(None, description="Filter by status (multi-select)"),
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = Query(None, description="Search name/email/phone"),
    assigned_to: UUID | None = None,
    include_archived: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """List intended parents with filters and pagination."""
    items, total = ip_service.list_intended_parents(
        db,
        org_id=session["org_id"],
        status=status,
        state=state,
        budget_min=budget_min,
        budget_max=budget_max,
        q=q,
        assigned_to=assigned_to,
        include_archived=include_archived,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [IntendedParentListItem.model_validate(ip) for ip in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/stats", response_model=IntendedParentStats)
def get_stats(
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get IP counts by status."""
    return ip_service.get_ip_stats(db, org_id=session["org_id"])


# =============================================================================
# CRUD
# =============================================================================

@router.post("", response_model=IntendedParentRead, status_code=status.HTTP_201_CREATED)
def create_intended_parent(
    data: IntendedParentCreate,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Create a new intended parent."""
    # Check for duplicate email
    existing = ip_service.get_ip_by_email(db, data.email, session["org_id"])
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intended parent with email '{data.email}' already exists",
        )
    
    ip = ip_service.create_intended_parent(
        db,
        org_id=session["org_id"],
        user_id=session["user_id"],
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        state=data.state,
        budget=data.budget,
        notes_internal=data.notes_internal,
        assigned_to_user_id=data.assigned_to_user_id,
    )
    return ip


@router.get("/{ip_id}", response_model=IntendedParentRead)
def get_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get an intended parent by ID."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    return ip


@router.patch("/{ip_id}", response_model=IntendedParentRead)
def update_intended_parent(
    ip_id: UUID,
    data: IntendedParentUpdate,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Update an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    # Check for duplicate email if changing
    if data.email and data.email.lower().strip() != ip.email.lower():
        existing = ip_service.get_ip_by_email(db, data.email, session["org_id"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Intended parent with email '{data.email}' already exists",
            )
    
    updated = ip_service.update_intended_parent(
        db,
        ip,
        user_id=session["user_id"],
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        state=data.state,
        budget=data.budget,
        notes_internal=data.notes_internal,
        assigned_to_user_id=data.assigned_to_user_id,
    )
    return updated


# =============================================================================
# Status / Archive / Restore / Delete
# =============================================================================

@router.patch("/{ip_id}/status", response_model=IntendedParentRead)
def update_status(
    ip_id: UUID,
    data: IntendedParentStatusUpdate,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Change status of an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    # Validate status
    valid_statuses = [s.value for s in IntendedParentStatus if s not in (IntendedParentStatus.ARCHIVED, IntendedParentStatus.RESTORED)]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    updated = ip_service.update_ip_status(
        db, ip, data.status, session["user_id"], data.reason
    )
    return updated


@router.post("/{ip_id}/archive", response_model=IntendedParentRead)
def archive_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Archive (soft delete) an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    if ip.is_archived:
        raise HTTPException(status_code=400, detail="Already archived")
    
    return ip_service.archive_intended_parent(db, ip, session["user_id"])


@router.post("/{ip_id}/restore", response_model=IntendedParentRead)
def restore_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.MANAGER)),
):
    """Restore an archived intended parent (manager only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    if not ip.is_archived:
        raise HTTPException(status_code=400, detail="Not archived")
    
    return ip_service.restore_intended_parent(db, ip, session["user_id"])


@router.delete("/{ip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intended_parent(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.MANAGER)),
):
    """Hard delete an archived intended parent (manager only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
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
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    return ip_service.get_ip_status_history(db, ip_id)


# =============================================================================
# Notes (polymorphic)
# =============================================================================

@router.get("/{ip_id}/notes", response_model=list[EntityNoteListItem])
def list_notes(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """List notes for an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    return note_service.list_entity_notes(db, session["org_id"], EntityType.INTENDED_PARENT, ip_id)


@router.post("/{ip_id}/notes", response_model=EntityNoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    ip_id: UUID,
    data: EntityNoteCreate,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Add a note to an intended parent."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    note = note_service.create_entity_note(
        db,
        org_id=session["org_id"],
        entity_type=EntityType.INTENDED_PARENT,
        entity_id=ip_id,
        author_id=session["user_id"],
        content=data.content,
    )
    
    # Bump last_activity
    ip.last_activity = note.created_at
    db.commit()
    
    return note


@router.delete("/{ip_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    ip_id: UUID,
    note_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Delete a note (author or manager only)."""
    ip = ip_service.get_intended_parent(db, ip_id, session["org_id"])
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    
    note = note_service.get_entity_note(db, note_id, session["org_id"])
    if not note or note.entity_id != ip_id:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check permission: author or manager+
    if note.author_id != session["user_id"] and session["role"] not in (Role.MANAGER.value, Role.DEVELOPER.value):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    
    note_service.delete_entity_note(db, note)
