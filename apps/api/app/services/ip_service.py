"""Intended Parent service - business logic for IP CRUD and status management."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import IntendedParentStatus
from app.db.models import IntendedParent, IntendedParentStatusHistory
from app.utils.normalization import normalize_email, normalize_phone


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
    owner_id: UUID | None = None,
    include_archived: bool = False,
    created_after: str | None = None,
    created_before: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[IntendedParent], int]:
    """
    List intended parents with filters and pagination.

    Returns (items, total_count).
    """
    from sqlalchemy import asc, desc

    query = db.query(IntendedParent).filter(IntendedParent.organization_id == org_id)

    # Archive filter
    if not include_archived:
        query = query.filter(IntendedParent.is_archived.is_(False))

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
        filters = [IntendedParent.full_name.ilike(search_term)]
        if "@" in q:
            try:
                filters.append(IntendedParent.email_hash == hash_email(q))
            except Exception:
                pass
        try:
            normalized_phone = normalize_phone(q)
            filters.append(IntendedParent.phone_hash == hash_phone(normalized_phone))
        except Exception:
            pass
        query = query.filter(or_(*filters))

    # Owner filter
    if owner_id:
        query = query.filter(IntendedParent.owner_id == owner_id)

    # Created date range filter (ISO format)
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            query = query.filter(IntendedParent.created_at >= after_date)
        except (ValueError, AttributeError):
            pass
    if created_before:
        try:
            before_date = datetime.fromisoformat(created_before.replace("Z", "+00:00"))
            query = query.filter(IntendedParent.created_at <= before_date)
        except (ValueError, AttributeError):
            pass

    # Get total count before pagination
    total = query.count()

    # Dynamic sorting
    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "full_name": IntendedParent.full_name,
        "state": IntendedParent.state,
        "budget": IntendedParent.budget,
        "status": IntendedParent.status,
        "created_at": IntendedParent.created_at,
    }

    if sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        query = query.order_by(IntendedParent.created_at.desc())

    # Pagination
    per_page = min(per_page, 100)  # Cap at 100
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()

    return items, total


def get_intended_parent(db: Session, ip_id: UUID, org_id: UUID) -> IntendedParent | None:
    """Get a single intended parent by ID, scoped to organization."""
    return (
        db.query(IntendedParent)
        .filter(IntendedParent.id == ip_id, IntendedParent.organization_id == org_id)
        .first()
    )


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
    owner_type: str | None = None,
    owner_id: UUID | None = None,
) -> IntendedParent:
    """Create a new intended parent and record initial status."""
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone) if phone else None
    ip = IntendedParent(
        organization_id=org_id,
        full_name=full_name,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
        state=state,
        budget=budget,
        notes_internal=notes_internal,
        owner_type=owner_type,
        owner_id=owner_id,
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
    owner_type: str | None = None,
    owner_id: UUID | None = None,
) -> IntendedParent:
    """Update intended parent fields and bump last_activity."""
    if full_name is not None:
        ip.full_name = full_name
    if email is not None:
        normalized_email = normalize_email(email)
        ip.email = normalized_email
        ip.email_hash = hash_email(normalized_email)
    if phone is not None:
        normalized_phone = normalize_phone(phone) if phone else None
        ip.phone = normalized_phone
        ip.phone_hash = hash_phone(normalized_phone) if normalized_phone else None
    if state is not None:
        ip.state = state
    if budget is not None:
        ip.budget = budget
    if notes_internal is not None:
        ip.notes_internal = notes_internal
    if owner_type is not None:
        ip.owner_type = owner_type
    if owner_id is not None:
        ip.owner_id = owner_id

    ip.last_activity = datetime.now(timezone.utc)
    ip.updated_at = datetime.now(timezone.utc)

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
    ip.last_activity = datetime.now(timezone.utc)
    ip.updated_at = datetime.now(timezone.utc)

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
    return (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == ip_id)
        .order_by(IntendedParentStatusHistory.changed_at.desc())
        .all()
    )


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
    ip.archived_at = datetime.now(timezone.utc)
    ip.status = IntendedParentStatus.ARCHIVED.value  # Actually change the status
    ip.last_activity = datetime.now(timezone.utc)

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
    history = (
        db.query(IntendedParentStatusHistory)
        .filter(
            IntendedParentStatusHistory.intended_parent_id == ip.id,
            IntendedParentStatusHistory.new_status == IntendedParentStatus.ARCHIVED.value,
        )
        .order_by(IntendedParentStatusHistory.changed_at.desc())
        .first()
    )

    # Restore to previous status, or default to 'new' if not found
    previous_status = (
        history.old_status if history and history.old_status else IntendedParentStatus.NEW.value
    )

    ip.is_archived = False
    ip.archived_at = None
    ip.status = previous_status
    ip.last_activity = datetime.now(timezone.utc)

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
    results = (
        db.query(IntendedParent.status, func.count(IntendedParent.id))
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.is_archived.is_(False),
        )
        .group_by(IntendedParent.status)
        .all()
    )

    by_status = {status: count for status, count in results}
    total = sum(by_status.values())

    return {"total": total, "by_status": by_status}


# =============================================================================
# Duplicate Check
# =============================================================================


def get_ip_by_email(db: Session, email: str, org_id: UUID) -> IntendedParent | None:
    """Check if an active IP with this email exists in the org."""
    return (
        db.query(IntendedParent)
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.email_hash == hash_email(email),
            IntendedParent.is_archived.is_(False),
        )
        .first()
    )
