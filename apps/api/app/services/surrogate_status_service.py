"""Surrogate status change helpers (apply + request + history + notifications)."""

from datetime import datetime, time, timedelta, timezone
from typing import TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import ContactStatus, OwnerType, Role, SurrogateStatus
from app.db.models import (
    Organization,
    PipelineStage,
    StatusChangeRequest,
    Surrogate,
    SurrogateStatusHistory,
    User,
)


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    surrogate: Surrogate | None
    request_id: UUID | None
    message: str | None


UNDO_GRACE_PERIOD = timedelta(minutes=5)


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


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None) -> User | None:
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


def change_status(
    db: Session,
    surrogate: Surrogate,
    new_stage_id: UUID,
    user_id: UUID | None,
    user_role: Role | None,
    reason: str | None = None,
    effective_at: datetime | None = None,
    *,
    emit_events: bool = False,
) -> StatusChangeResult:
    """
    Change surrogate stage and record history with backdating support.

    Supports:
    - Normal changes (effective now)
    - Backdated changes (effective in the past, requires reason)
    - Regressions (earlier stage, requires admin approval)

    Args:
        effective_at: When the change actually occurred. None = now.
            - Today with no time: effective now
            - Past with no time: 12:00 PM org timezone

    Returns:
        StatusChangeResult with status='applied' or 'pending_approval'
    """
    from app.core.stage_rules import ROLE_STAGE_MUTATION
    from app.services import pipeline_service

    now = datetime.now(timezone.utc)
    org_tz_str = _get_org_timezone(db, surrogate.organization_id)
    normalized_effective_at = _normalize_effective_at(effective_at, org_tz_str)

    old_stage_id = surrogate.stage_id
    old_label = surrogate.status_label
    old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
    old_slug = old_stage.slug if old_stage else None
    old_order = old_stage.order if old_stage else 0
    surrogate_pipeline_id = old_stage.pipeline_id if old_stage else None
    if not surrogate_pipeline_id:
        surrogate_pipeline_id = pipeline_service.get_or_create_default_pipeline(
            db,
            surrogate.organization_id,
        ).id

    new_stage = pipeline_service.get_stage_by_id(db, new_stage_id)
    if not new_stage or not new_stage.is_active:
        raise ValueError("Invalid or inactive stage")
    if new_stage.pipeline_id != surrogate_pipeline_id:
        raise ValueError("Stage does not belong to surrogate pipeline")

    if old_stage_id == new_stage.id:
        raise ValueError("Target stage is same as current stage")

    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = new_stage.order < old_order

    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for stage change")

    if surrogate.created_at and normalized_effective_at < surrogate.created_at:
        raise ValueError("Cannot set date before surrogate was created")

    role_str = user_role.value if hasattr(user_role, "value") else user_role
    if not role_str:
        raise ValueError("User role is required to change stage")

    rules = ROLE_STAGE_MUTATION.get(role_str)
    if not rules:
        raise ValueError("Role not permitted to change stage")

    if role_str == Role.CASE_MANAGER.value:
        if surrogate.owner_type != OwnerType.USER.value or surrogate.owner_id != user_id:
            raise ValueError("Surrogate must be claimed before changing stage")

    allowed_types = set(rules["stage_types"])
    allowed_slugs = set(rules.get("extra_slugs", []))
    if not is_regression:
        if new_stage.stage_type not in allowed_types and new_stage.slug not in allowed_slugs:
            if role_str == Role.INTAKE_SPECIALIST.value:
                raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
            if role_str == Role.CASE_MANAGER.value:
                raise ValueError("Case managers can only set post-approval stages")
            raise ValueError("Role not permitted to change stage")
    elif role_str == Role.INTAKE_SPECIALIST.value:
        if new_stage.stage_type not in allowed_types and new_stage.slug not in allowed_slugs:
            raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
    elif role_str == Role.CASE_MANAGER.value:
        regression_allowed_types = allowed_types | {"intake"}
        if (
            new_stage.stage_type not in regression_allowed_types
            and new_stage.slug not in allowed_slugs
        ):
            raise ValueError("Case managers can only regress to intake or post-approval stages")

    if is_regression:
        last_history = (
            db.query(SurrogateStatusHistory)
            .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
            .order_by(SurrogateStatusHistory.recorded_at.desc())
            .first()
        )

        within_grace_period = (
            last_history
            and last_history.changed_by_user_id == user_id
            and last_history.recorded_at
            and (now - last_history.recorded_at) <= UNDO_GRACE_PERIOD
            and last_history.from_stage_id == new_stage.id
        )

        if within_grace_period:
            result = apply_status_change(
                db=db,
                surrogate=surrogate,
                new_stage=new_stage,
                old_stage_id=old_stage_id,
                old_label=old_label,
                old_slug=old_slug,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                is_undo=True,
            )
            if emit_events:
                from app.services import dashboard_events

                dashboard_events.push_dashboard_stats(db, surrogate.organization_id)
            return result

    if (is_backdated or is_regression) and not reason:
        raise ValueError("Reason required for backdated or regressed stage changes")

    if is_regression:
        request = StatusChangeRequest(
            organization_id=surrogate.organization_id,
            entity_type="surrogate",
            entity_id=surrogate.id,
            target_stage_id=new_stage.id,
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
            raise ValueError("A pending regression request already exists for this stage and date.")
        db.refresh(request)

        from app.services import notification_facade

        requester = _get_org_user(db, surrogate.organization_id, user_id)
        notification_facade.notify_status_change_request_pending(
            db=db,
            request=request,
            surrogate=surrogate,
            target_stage_label=new_stage.label,
            current_stage_label=old_label or "Unknown",
            requester_name=requester.display_name if requester else "Someone",
        )

        result = StatusChangeResult(
            status="pending_approval",
            surrogate=surrogate,
            request_id=request.id,
            message="Regression requires admin approval. Request submitted.",
        )
        if emit_events:
            from app.services import dashboard_events

            dashboard_events.push_dashboard_stats(db, surrogate.organization_id)
        return result

    result = apply_status_change(
        db=db,
        surrogate=surrogate,
        new_stage=new_stage,
        old_stage_id=old_stage_id,
        old_label=old_label,
        old_slug=old_slug,
        user_id=user_id,
        reason=reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        is_undo=False,
    )
    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, surrogate.organization_id)
    return result


def apply_status_change(
    db: Session,
    surrogate: Surrogate,
    new_stage: PipelineStage,
    old_stage_id: UUID | None,
    old_label: str | None,
    old_slug: str | None,
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
    """
    Apply a status change to a surrogate.

    Called for non-regressions, undo within grace period, and approved regressions.
    """
    surrogate.stage_id = new_stage.id
    surrogate.status_label = new_stage.label

    # Update contact status if reached or leaving intake stage
    if surrogate.contact_status == ContactStatus.UNREACHED.value:
        if new_stage.slug == SurrogateStatus.CONTACTED.value or new_stage.is_intake_stage is False:
            surrogate.contact_status = ContactStatus.REACHED.value
            if not surrogate.contacted_at:
                surrogate.contacted_at = effective_at

    # Record history with dual timestamps
    history = SurrogateStatusHistory(
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        from_stage_id=old_stage_id,
        to_stage_id=new_stage.id,
        from_label_snapshot=old_label,
        to_label_snapshot=new_stage.label,
        changed_by_user_id=user_id,
        reason=reason,
        changed_at=effective_at,  # Derived from effective_at for backward compat
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
    db.refresh(surrogate)

    from app.services import surrogate_events

    surrogate_events.handle_status_changed(
        db=db,
        surrogate=surrogate,
        new_stage=new_stage,
        old_stage_id=old_stage_id,
        old_label=old_label,
        old_slug=old_slug,
        user_id=user_id,
        effective_at=effective_at,
        recorded_at=recorded_at,
        is_undo=is_undo,
        request_id=request_id,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
        requested_at=requested_at,
    )

    return StatusChangeResult(
        status="applied",
        surrogate=surrogate,
        request_id=None,
        message=None,
    )
