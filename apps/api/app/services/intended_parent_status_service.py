"""Intended parent stage change helpers (apply + request + history + notifications)."""

from datetime import datetime, time, timedelta, timezone
from typing import TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import Role
from app.core.stage_definitions import INTENDED_PARENT_PIPELINE_ENTITY
from app.db.models import (
    IntendedParent,
    IntendedParentStatusHistory,
    Organization,
    PipelineStage,
    StatusChangeRequest,
    User,
)


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # "applied" or "pending_approval"
    intended_parent: IntendedParent | None
    request_id: UUID | None
    message: str | None


UNDO_GRACE_PERIOD = timedelta(minutes=5)


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None) -> User | None:
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


def _get_org_timezone(db: Session, org_id: UUID) -> str:
    result = db.execute(
        select(Organization.timezone).where(Organization.id == org_id)
    ).scalar_one_or_none()
    return result or "America/Los_Angeles"


def _normalize_effective_at(
    effective_at: datetime | None,
    org_timezone_str: str,
) -> datetime:
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


def get_default_pipeline_stage(
    db: Session,
    org_id: UUID,
    stage_id: UUID,
) -> PipelineStage:
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=INTENDED_PARENT_PIPELINE_ENTITY,
    )
    stage = pipeline_service.get_stage_by_id(db, stage_id)
    if not stage or stage.pipeline_id != pipeline.id or not stage.is_active:
        raise ValueError("Target stage not found")
    return stage


def get_current_stage(db: Session, ip: IntendedParent) -> PipelineStage:
    from app.services import pipeline_service

    if ip.stage and ip.stage.is_active:
        return ip.stage
    if ip.stage_id:
        stage = pipeline_service.get_stage_by_id(db, ip.stage_id)
        if stage and stage.is_active:
            return stage

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        ip.organization_id,
        entity_type=INTENDED_PARENT_PIPELINE_ENTITY,
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, ip.status)
    if not stage:
        raise ValueError("Current intended parent stage not found")
    ip.stage_id = stage.id
    ip.status = stage.stage_key
    return stage


def change_status(
    db: Session,
    ip: IntendedParent,
    new_stage: PipelineStage,
    user_id: UUID,
    user_role: Role | str | None,
    reason: str | None = None,
    effective_at: datetime | None = None,
) -> StatusChangeResult:
    """Change intended parent stage with backdating and regression support."""
    current_stage = get_current_stage(db, ip)
    if new_stage.id == current_stage.id:
        raise ValueError("Target stage is same as current stage")

    now = datetime.now(timezone.utc)
    org_tz_str = _get_org_timezone(db, ip.organization_id)
    normalized_effective_at = _normalize_effective_at(effective_at, org_tz_str)

    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = new_stage.order < current_stage.order

    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for status change")

    if ip.created_at and normalized_effective_at < ip.created_at:
        raise ValueError("Cannot set date before intended parent was created")

    role_str = user_role.value if hasattr(user_role, "value") else user_role
    if not role_str:
        raise ValueError("User role is required to change status")

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
            and last_history.old_stage_id == new_stage.id
            and last_history.new_stage_id == current_stage.id
        )

        if within_grace_period:
            return apply_status_change(
                db=db,
                ip=ip,
                old_stage=current_stage,
                new_stage=new_stage,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                is_undo=True,
            )

    if (is_backdated or is_regression) and not reason:
        raise ValueError("Reason required for backdated or regressed status changes")

    if is_regression:
        if role_str in {Role.ADMIN.value, Role.DEVELOPER.value}:
            return apply_status_change(
                db=db,
                ip=ip,
                old_stage=current_stage,
                new_stage=new_stage,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                is_undo=False,
                approved_by_user_id=user_id,
                approved_at=now,
            )

        request = StatusChangeRequest(
            organization_id=ip.organization_id,
            entity_type="intended_parent",
            entity_id=ip.id,
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

        requester = _get_org_user(db, ip.organization_id, user_id)
        notification_facade.notify_ip_status_change_request_pending(
            db=db,
            request=request,
            intended_parent=ip,
            target_status_label=new_stage.label,
            current_status_label=current_stage.label,
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
        old_stage=current_stage,
        new_stage=new_stage,
        user_id=user_id,
        reason=reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        is_undo=False,
    )


def apply_status_change(
    db: Session,
    ip: IntendedParent,
    old_stage: PipelineStage,
    new_stage: PipelineStage,
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
    """Apply a stage change to an intended parent."""
    ip.stage_id = new_stage.id
    ip.status = new_stage.stage_key
    ip.last_activity = datetime.now(timezone.utc)
    ip.updated_at = datetime.now(timezone.utc)

    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_stage_id=old_stage.id if old_stage else None,
        new_stage_id=new_stage.id,
        old_status=old_stage.stage_key if old_stage else None,
        new_status=new_stage.stage_key,
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
