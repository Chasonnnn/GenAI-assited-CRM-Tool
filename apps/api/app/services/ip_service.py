"""Intended Parent service - business logic for IP CRUD and status management."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import IntendedParentStatus
from app.db.models import IntendedParent, IntendedParentStatusHistory, StatusChangeRequest, User
from app.utils.normalization import normalize_email, normalize_phone


# =============================================================================
# CRUD Operations
# =============================================================================


UNDO_GRACE_PERIOD = timedelta(minutes=5)

IP_STATUS_ORDER = {
    IntendedParentStatus.NEW.value: 0,
    IntendedParentStatus.READY_TO_MATCH.value: 1,
    IntendedParentStatus.MATCHED.value: 2,
    IntendedParentStatus.DELIVERED.value: 3,
}


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    intended_parent: IntendedParent | None
    request_id: UUID | None
    message: str | None


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None) -> User | None:
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


def _format_status_label(status: str | None) -> str:
    if not status:
        return "Unknown"
    return status.replace("_", " ").title()


def _status_order(status: str) -> int:
    if status not in IP_STATUS_ORDER:
        raise ValueError(f"Unknown intended parent status: {status}")
    return IP_STATUS_ORDER[status]


def generate_intended_parent_number(db: Session, org_id: UUID) -> str:
    """
    Generate next sequential intended parent number for org (I10001+).

    Uses atomic INSERT...ON CONFLICT for race-condition-free counter increment.
    """
    result = db.execute(
        text("""
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'intended_parent_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
        """),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError("Failed to generate intended parent number")

    return f"I{result:05d}"


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

    # Search filter (name, number, email, phone)
    if q:
        search_term = f"%{q}%"
        filters = [
            IntendedParent.full_name.ilike(search_term),
            IntendedParent.intended_parent_number.ilike(search_term),
        ]
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
        "intended_parent_number": IntendedParent.intended_parent_number,
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
    now = datetime.now(timezone.utc)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone) if phone else None
    ip = IntendedParent(
        intended_parent_number=generate_intended_parent_number(db, org_id),
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
        effective_at=now,
        recorded_at=now,
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


def change_status(
    db: Session,
    ip: IntendedParent,
    new_status: str,
    user_id: UUID,
    reason: str | None = None,
    effective_at: datetime | None = None,
) -> StatusChangeResult:
    """
    Change intended parent status with backdating and regression support.

    - Backdating (past date): Requires reason, applies immediately
    - Regression (earlier status): Requires reason + admin approval
    - Undo within 5-min grace period: Bypasses admin approval
    """
    if new_status == ip.status:
        raise ValueError("Target status is same as current status")

    now = datetime.now(timezone.utc)

    from app.services import surrogate_service

    org_tz_str = surrogate_service._get_org_timezone(db, ip.organization_id)
    normalized_effective_at = surrogate_service._normalize_effective_at(effective_at, org_tz_str)

    # Detect backdating and regression
    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = _status_order(new_status) < _status_order(ip.status)

    # Validation: cannot set future date (allow 1 second tolerance)
    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for status change")

    # Validation: cannot set date before intended parent creation
    if ip.created_at and normalized_effective_at < ip.created_at:
        raise ValueError("Cannot set date before intended parent was created")

    # Regression: allow undo within grace period (no approval)
    if is_regression:
        last_history = (
            db.query(IntendedParentStatusHistory)
            .filter(IntendedParentStatusHistory.intended_parent_id == ip.id)
            .order_by(IntendedParentStatusHistory.recorded_at.desc())
            .first()
        )

        within_grace_period = (
            last_history
            and last_history.changed_by_user_id == user_id
            and last_history.recorded_at
            and (now - last_history.recorded_at) <= UNDO_GRACE_PERIOD
            and last_history.old_status == new_status
            and last_history.new_status == ip.status
        )

        if within_grace_period:
            return _apply_status_change(
                db=db,
                ip=ip,
                new_status=new_status,
                old_status=ip.status,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                is_undo=True,
            )

    # Backdating or regression requires reason (unless undo)
    if (is_backdated or is_regression) and not reason:
        raise ValueError("Reason required for backdated or regressed status changes")

    if is_regression:
        request = StatusChangeRequest(
            organization_id=ip.organization_id,
            entity_type="intended_parent",
            entity_id=ip.id,
            target_status=new_status,
            effective_at=normalized_effective_at,
            reason=reason or "",
            requested_by_user_id=user_id,
            requested_at=now,
            status="pending",
        )
        db.add(request)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError(
                "A pending regression request already exists for this status and date."
            )
        db.refresh(request)

        from app.services import notification_service

        requester = _get_org_user(db, ip.organization_id, user_id)
        notification_service.notify_ip_status_change_request_pending(
            db=db,
            request=request,
            intended_parent=ip,
            target_status_label=_format_status_label(new_status),
            current_status_label=_format_status_label(ip.status),
            requester_name=requester.display_name if requester else "Someone",
        )

        return StatusChangeResult(
            status="pending_approval",
            intended_parent=ip,
            request_id=request.id,
            message="Regression requires admin approval. Request submitted.",
        )

    # NON-REGRESSION: Apply immediately
    return _apply_status_change(
        db=db,
        ip=ip,
        new_status=new_status,
        old_status=ip.status,
        user_id=user_id,
        reason=reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        is_undo=False,
    )


def _apply_status_change(
    db: Session,
    ip: IntendedParent,
    new_status: str,
    old_status: str,
    user_id: UUID | None,
    reason: str | None,
    effective_at: datetime,
    recorded_at: datetime,
    is_undo: bool = False,
    request_id: UUID | None = None,
    approved_by_user_id: UUID | None = None,
    approved_at: datetime | None = None,
    requested_at: datetime | None = None,
) -> StatusChangeResult:
    """Apply a status change to an intended parent (internal helper)."""
    ip.status = new_status
    ip.last_activity = datetime.now(timezone.utc)
    ip.updated_at = datetime.now(timezone.utc)

    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        changed_at=effective_at,
        effective_at=effective_at,
        recorded_at=recorded_at,
        is_undo=is_undo,
        request_id=request_id,
        requested_at=requested_at,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
    )
    db.add(history)
    db.commit()
    db.refresh(ip)

    return StatusChangeResult(
        status="applied",
        intended_parent=ip,
        request_id=None,
        message=None,
    )


def get_ip_status_history(db: Session, ip_id: UUID) -> list[IntendedParentStatusHistory]:
    """Get status history for an intended parent."""
    return (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == ip_id)
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
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
    now = datetime.now(timezone.utc)
    old_status = ip.status
    ip.is_archived = True
    ip.archived_at = now
    ip.status = IntendedParentStatus.ARCHIVED.value  # Actually change the status
    ip.last_activity = now

    # Record in history
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=old_status,
        new_status=IntendedParentStatus.ARCHIVED.value,
        reason="Archived",
        effective_at=now,
        recorded_at=now,
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
    now = datetime.now(timezone.utc)
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
    ip.last_activity = now

    history_entry = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_status=IntendedParentStatus.ARCHIVED.value,
        new_status=previous_status,
        reason="Restored from archive",
        effective_at=now,
        recorded_at=now,
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
