"""Intended Parent service - business logic for IP CRUD and status management."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app.db.enums import IntendedParentStatus, EntityType
from app.db.models import IntendedParent, IntendedParentStatusHistory


# =============================================================================
# CRUD Operations
# =============================================================================

def list_intended_parents(
    db: Session,
    org_id: UUID,
    *,
    status: list[str] | None = None,
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = None,
    assigned_to: UUID | None = None,
    include_archived: bool = False,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[IntendedParent], int]:
    """
    List intended parents with filters and pagination.
    
    Returns (items, total_count).
    """
    query = db.query(IntendedParent).filter(IntendedParent.organization_id == org_id)
    
    # Archive filter
    if not include_archived:
        query = query.filter(IntendedParent.is_archived == False)
    
    # Status filter (multi-select)
    if status:
        query = query.filter(IntendedParent.status.in_(status))
    
    # State filter
    if state:
        query = query.filter(IntendedParent.state == state)
    
    # Budget range filter
    if budget_min is not None:
        query = query.filter(IntendedParent.budget >= budget_min)
    if budget_max is not None:
        query = query.filter(IntendedParent.budget <= budget_max)
    
    # Search filter (name, email, phone)
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                IntendedParent.full_name.ilike(search_term),
                IntendedParent.email.ilike(search_term),
                IntendedParent.phone.ilike(search_term),
            )
        )
    
    # Assigned to filter
    if assigned_to:
        query = query.filter(IntendedParent.assigned_to_user_id == assigned_to)
    
    # Get total count before pagination
    total = query.count()
    
    # Pagination and ordering
    per_page = min(per_page, 100)  # Cap at 100
    offset = (page - 1) * per_page
    items = query.order_by(IntendedParent.created_at.desc()).offset(offset).limit(per_page).all()
    
    return items, total


def get_intended_parent(db: Session, ip_id: UUID, org_id: UUID) -> IntendedParent | None:
    """Get a single intended parent by ID, scoped to organization."""
    return db.query(IntendedParent).filter(
        IntendedParent.id == ip_id,
        IntendedParent.organization_id == org_id
    ).first()


def create_intended_parent(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    *,
    full_name: str,
    email: str,
    phone: str | None = None,
    state: str | None = None,
    budget: Decimal | None = None,
    notes_internal: str | None = None,
    assigned_to_user_id: UUID | None = None,
) -> IntendedParent:
    """Create a new intended parent and record initial status."""
    ip = IntendedParent(
        organization_id=org_id,
        full_name=full_name,
        email=email.lower().strip(),
        phone=phone,
        state=state,
        budget=budget,
        notes_internal=notes_internal,
        assigned_to_user_id=assigned_to_user_id,
    )
    db.add(ip)
    db.flush()
    
    # Record initial status in history
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=None,
        new_status=ip.status,
        reason="Initial creation",
    )
    db.add(history)
    db.commit()
    db.refresh(ip)
    return ip


def update_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
    *,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    state: str | None = None,
    budget: Decimal | None = None,
    notes_internal: str | None = None,
    assigned_to_user_id: UUID | None = None,
) -> IntendedParent:
    """Update intended parent fields and bump last_activity."""
    if full_name is not None:
        ip.full_name = full_name
    if email is not None:
        ip.email = email.lower().strip()
    if phone is not None:
        ip.phone = phone
    if state is not None:
        ip.state = state
    if budget is not None:
        ip.budget = budget
    if notes_internal is not None:
        ip.notes_internal = notes_internal
    if assigned_to_user_id is not None:
        ip.assigned_to_user_id = assigned_to_user_id
    
    ip.last_activity = datetime.utcnow()
    ip.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ip)
    return ip


# =============================================================================
# Status Management
# =============================================================================

def update_ip_status(
    db: Session,
    ip: IntendedParent,
    new_status: str,
    user_id: UUID,
    reason: str | None = None,
) -> IntendedParent:
    """Change status and record in history."""
    old_status = ip.status
    ip.status = new_status
    ip.last_activity = datetime.utcnow()
    ip.updated_at = datetime.utcnow()
    
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
    )
    db.add(history)
    db.commit()
    db.refresh(ip)
    return ip


def get_ip_status_history(db: Session, ip_id: UUID) -> list[IntendedParentStatusHistory]:
    """Get status history for an intended parent."""
    return db.query(IntendedParentStatusHistory).filter(
        IntendedParentStatusHistory.intended_parent_id == ip_id
    ).order_by(IntendedParentStatusHistory.changed_at.desc()).all()


# =============================================================================
# Archive / Restore
# =============================================================================

def archive_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
) -> IntendedParent:
    """Soft delete (archive) an intended parent. Sets status to 'archived'."""
    old_status = ip.status
    ip.is_archived = True
    ip.archived_at = datetime.utcnow()
    ip.status = IntendedParentStatus.ARCHIVED.value  # Actually change the status
    ip.last_activity = datetime.utcnow()
    
    # Record in history
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=old_status,
        new_status=IntendedParentStatus.ARCHIVED.value,
        reason="Archived",
    )
    db.add(history)
    db.commit()
    db.refresh(ip)
    return ip


def restore_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
) -> IntendedParent:
    """Restore an archived intended parent. Restores to previous status before archive."""
    # Get the status before archiving from history
    history = db.query(IntendedParentStatusHistory).filter(
        IntendedParentStatusHistory.intended_parent_id == ip.id,
        IntendedParentStatusHistory.new_status == IntendedParentStatus.ARCHIVED.value
    ).order_by(IntendedParentStatusHistory.changed_at.desc()).first()
    
    # Restore to previous status, or default to 'new' if not found
    previous_status = history.old_status if history and history.old_status else IntendedParentStatus.NEW.value
    
    ip.is_archived = False
    ip.archived_at = None
    ip.status = previous_status
    ip.last_activity = datetime.utcnow()
    
    history_entry = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=IntendedParentStatus.ARCHIVED.value,
        new_status=previous_status,
        reason="Restored from archive",
    )
    db.add(history_entry)
    db.commit()
    db.refresh(ip)
    return ip


def delete_intended_parent(db: Session, ip: IntendedParent) -> None:
    """Hard delete an intended parent (must be archived first)."""
    if not ip.is_archived:
        raise ValueError("Cannot delete non-archived intended parent")
    db.delete(ip)
    db.commit()


# =============================================================================
# Stats
# =============================================================================

def get_ip_stats(db: Session, org_id: UUID) -> dict:
    """Get IP counts by status."""
    results = db.query(
        IntendedParent.status,
        func.count(IntendedParent.id)
    ).filter(
        IntendedParent.organization_id == org_id,
        IntendedParent.is_archived == False
    ).group_by(IntendedParent.status).all()
    
    by_status = {status: count for status, count in results}
    total = sum(by_status.values())
    
    return {"total": total, "by_status": by_status}


# =============================================================================
# Duplicate Check
# =============================================================================

def get_ip_by_email(db: Session, email: str, org_id: UUID) -> IntendedParent | None:
    """Check if an active IP with this email exists in the org."""
    return db.query(IntendedParent).filter(
        IntendedParent.organization_id == org_id,
        IntendedParent.email == email.lower().strip(),
        IntendedParent.is_archived == False
    ).first()
