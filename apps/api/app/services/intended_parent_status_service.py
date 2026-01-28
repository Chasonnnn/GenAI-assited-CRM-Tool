"""Intended parent status change helpers (apply + request + history + notifications)."""

from datetime import datetime, time, timedelta, timezone
from typing import TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import IntendedParentStatus
from app.db.models import (
    IntendedParent,
    IntendedParentStatusHistory,
    Organization,
    StatusChangeRequest,
    User,
)


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    intended_parent: IntendedParent | None
    request_id: UUID | None
    message: str | None


UNDO_GRACE_PERIOD = timedelta(minutes=5)

IP_STATUS_ORDER = {
    IntendedParentStatus.NEW.value: 0,
    IntendedParentStatus.READY_TO_MATCH.value: 1,
    IntendedParentStatus.MATCHED.value: 2,
    IntendedParentStatus.DELIVERED.value: 3,
}


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


def _get_org_timezone(db: Session, org_id: UUID) -> str:
    """Get organization timezone string."""
    result = db.execute(
        select(Organization.timezone).where(Organization.id == org_id)
    ).scalar_one_or_none()
    return result or "America/Los_Angeles"


def _normalize_effective_at(
    effective_at: datetime | None,
    org_timezone_str: str,
) -> datetime:
    """
    Normalize effective_at to UTC datetime.

    Rules:
    - None: return now (UTC)
    - Today with time 00:00:00: return now (UTC) - effective now
    - Past date with time 00:00:00: default to 12:00 PM in org timezone
    - Otherwise: use as-is (assume UTC if no timezone)
    """
    now = datetime.now(timezone.utc)

    if effective_at is None:
        return now

    org_tz = ZoneInfo(org_timezone_str)
    if effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=org_tz)
    else:
        effective_at = effective_at.astimezone(org_tz)

    if effective_at.time() == time(0, 0, 0):
        today_org = now.astimezone(org_tz).date()
        effective_date = effective_at.date()

        if effective_date == today_org:
            return now
        if effective_date < today_org:
            noon = datetime.combine(effective_date, time(12, 0, 0)).replace(tzinfo=org_tz)
            return noon.astimezone(timezone.utc)
        return effective_at.astimezone(timezone.utc)

    return effective_at.astimezone(timezone.utc)


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
    org_tz_str = _get_org_timezone(db, ip.organization_id)
    normalized_effective_at = _normalize_effective_at(effective_at, org_tz_str)

    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = _status_order(new_status) < _status_order(ip.status)

    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for status change")

    if ip.created_at and normalized_effective_at < ip.created_at:
        raise ValueError("Cannot set date before intended parent was created")

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
            return apply_status_change(
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

    return apply_status_change(
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


def apply_status_change(
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
    """Apply a status change to an intended parent."""
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
