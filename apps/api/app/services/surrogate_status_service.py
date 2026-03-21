"""Surrogate status change helpers (apply + request + history + notifications)."""

import calendar
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import TypedDict
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import ContactStatus, OwnerType, Role, SurrogateStatus, TaskType
from app.db.models import (
    Organization,
    PipelineStage,
    StatusChangeRequest,
    Surrogate,
    SurrogateStatusHistory,
    Task,
    User,
)

logger = logging.getLogger(__name__)


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


def _add_calendar_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_on_hold_follow_up_description(
    *,
    reason: str,
    paused_from_stage: PipelineStage | None,
) -> str:
    paused_from_label = paused_from_stage.label if paused_from_stage else "Unknown"
    return f"Paused from: {paused_from_label}\nReason: {reason}"


def _create_on_hold_follow_up_task(
    db: Session,
    *,
    surrogate: Surrogate,
    paused_from_stage: PipelineStage | None,
    actor_user_id: UUID | None,
    reason: str,
    effective_at: datetime,
    org_timezone_str: str,
    follow_up_months: int | None,
) -> Task | None:
    if not follow_up_months:
        return None

    owner_id = surrogate.owner_id if surrogate.owner_type == OwnerType.USER.value else actor_user_id
    if not owner_id:
        return None

    due_date = _add_calendar_months(
        effective_at.astimezone(ZoneInfo(org_timezone_str)).date(),
        follow_up_months,
    )
    task = Task(
        id=uuid4(),
        organization_id=surrogate.organization_id,
        surrogate_id=surrogate.id,
        created_by_user_id=actor_user_id or surrogate.created_by_user_id or owner_id,
        owner_type=OwnerType.USER.value,
        owner_id=owner_id,
        title="On-Hold follow-up",
        description=_build_on_hold_follow_up_description(
            reason=reason,
            paused_from_stage=paused_from_stage,
        ),
        task_type=TaskType.FOLLOW_UP.value,
        due_date=due_date,
    )
    db.add(task)
    db.flush()
    return task


def _cleanup_on_hold_follow_up_task(
    db: Session,
    *,
    surrogate: Surrogate,
) -> Task | None:
    task: Task | None = None
    if surrogate.on_hold_follow_up_task_id:
        task = (
            db.query(Task)
            .filter(
                Task.id == surrogate.on_hold_follow_up_task_id,
                Task.organization_id == surrogate.organization_id,
            )
            .one_or_none()
        )
        if task and not task.is_completed:
            db.delete(task)
        else:
            task = None

    surrogate.on_hold_follow_up_task_id = None
    surrogate.paused_from_stage_id = None
    return task


def change_status(
    db: Session,
    surrogate: Surrogate,
    new_stage_id: UUID,
    user_id: UUID | None,
    user_role: Role | None,
    reason: str | None = None,
    effective_at: datetime | None = None,
    on_hold_follow_up_months: int | None = None,
    trigger_workflows: bool = True,
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
    from app.services import pipeline_semantics_service, pipeline_service, surrogate_stage_context

    now = datetime.now(timezone.utc)
    org_tz_str = _get_org_timezone(db, surrogate.organization_id)
    normalized_effective_at = _normalize_effective_at(effective_at, org_tz_str)

    old_stage_id = surrogate.stage_id
    old_label = surrogate.status_label
    stage_context = surrogate_stage_context.get_stage_context(db, surrogate)
    current_stage = stage_context.current_stage
    effective_old_stage = stage_context.effective_stage
    paused_from_stage = stage_context.paused_from_stage
    old_slug = current_stage.slug if current_stage else None
    old_order = effective_old_stage.order if effective_old_stage else 0
    surrogate_pipeline_id = current_stage.pipeline_id if current_stage else None
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

    if (
        not pipeline_service.stage_matches_key(new_stage, "on_hold")
        and on_hold_follow_up_months is not None
    ):
        raise ValueError("Follow-up timing is only allowed when moving to On-Hold")

    if pipeline_service.stage_matches_key(new_stage, "on_hold") and not reason:
        raise ValueError("Reason required when moving to On-Hold")

    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_resume_from_on_hold = bool(
        current_stage
        and pipeline_service.stage_matches_key(current_stage, "on_hold")
        and paused_from_stage
        and paused_from_stage.id == new_stage.id
    )
    is_regression = (not is_resume_from_on_hold) and new_stage.order < old_order

    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for stage change")

    if surrogate.created_at and normalized_effective_at < surrogate.created_at:
        raise ValueError("Cannot set date before surrogate was created")

    role_str = user_role.value if hasattr(user_role, "value") else user_role
    if not role_str:
        raise ValueError("User role is required to change stage")

    if role_str == Role.CASE_MANAGER.value:
        if surrogate.owner_type != OwnerType.USER.value or surrogate.owner_id != user_id:
            raise ValueError("Surrogate must be claimed before changing stage")

    pipeline = pipeline_service.get_pipeline(db, surrogate.organization_id, surrogate_pipeline_id)
    if not pipeline:
        raise ValueError("Pipeline not found")
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline)
    if is_resume_from_on_hold:
        pass
    elif not is_regression:
        if not pipeline_semantics_service.can_role_access_stage(
            role_str,
            new_stage,
            feature_config=feature_config,
            mutation=True,
        ):
            if role_str == Role.INTAKE_SPECIALIST.value:
                raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
            if role_str == Role.CASE_MANAGER.value:
                raise ValueError("Case managers can only set post-approval stages")
            raise ValueError("Role not permitted to change stage")
    elif role_str == Role.INTAKE_SPECIALIST.value:
        if new_stage.stage_type not in allowed_types and new_stage_key not in allowed_stage_keys:
            raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
    elif role_str == Role.CASE_MANAGER.value:
        regression_allowed_types = allowed_types | {"intake"}
        if (
            new_stage.stage_type not in regression_allowed_types
            and new_stage_key not in allowed_stage_keys
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
                current_stage=current_stage,
                old_stage_id=old_stage_id,
                old_label=old_label,
                old_slug=old_slug,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                org_timezone_str=org_tz_str,
                is_undo=True,
                paused_from_stage=effective_old_stage
                if pipeline_service.stage_matches_key(new_stage, "on_hold")
                else paused_from_stage,
                on_hold_follow_up_months=on_hold_follow_up_months,
                trigger_workflows=trigger_workflows,
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
        try:
            notification_facade.notify_status_change_request_pending(
                db=db,
                request=request,
                surrogate=surrogate,
                target_stage_label=new_stage.label,
                current_stage_label=(
                    effective_old_stage.label if effective_old_stage else old_label or "Unknown"
                ),
                requester_name=requester.display_name if requester else "Someone",
            )
        except Exception as exc:
            from app.db.enums import AlertSeverity, AlertType
            from app.services import alert_service

            logger.exception("surrogate_status_regression_notify_failed")
            alert_service.record_alert_isolated(
                org_id=surrogate.organization_id,
                alert_type=AlertType.NOTIFICATION_PUSH_FAILED,
                severity=AlertSeverity.ERROR,
                title="Surrogate status regression notification failed",
                message=str(exc)[:500],
                integration_key="surrogate_status_request",
                error_class=type(exc).__name__,
                details={
                    "surrogate_id": str(surrogate.id),
                    "request_id": str(request.id),
                    "target_stage_id": str(new_stage.id),
                    "target_stage_slug": new_stage.slug,
                },
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
        current_stage=current_stage,
        old_stage_id=old_stage_id,
        old_label=old_label,
        old_slug=old_slug,
        user_id=user_id,
        reason=reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        org_timezone_str=org_tz_str,
        is_undo=False,
        paused_from_stage=(
            effective_old_stage
            if pipeline_service.stage_matches_key(new_stage, "on_hold")
            else paused_from_stage
        ),
        on_hold_follow_up_months=on_hold_follow_up_months,
        trigger_workflows=trigger_workflows,
    )
    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, surrogate.organization_id)
    return result


def apply_status_change(
    db: Session,
    surrogate: Surrogate,
    new_stage: PipelineStage,
    current_stage: PipelineStage | None,
    old_stage_id: UUID | None,
    old_label: str | None,
    old_slug: str | None,
    user_id: UUID | None,
    reason: str | None,
    effective_at: datetime,
    recorded_at: datetime,
    org_timezone_str: str | None = None,
    is_undo: bool = False,
    request_id: UUID | None = None,
    approved_by_user_id: UUID | None = None,
    approved_at: datetime | None = None,
    requested_at: datetime | None = None,
    paused_from_stage: PipelineStage | None = None,
    on_hold_follow_up_months: int | None = None,
    trigger_workflows: bool = True,
) -> StatusChangeResult:
    """
    Apply a status change to a surrogate.

    Called for non-regressions, undo within grace period, and approved regressions.
    """
    from app.services import pipeline_service

    resolved_org_timezone = org_timezone_str or _get_org_timezone(db, surrogate.organization_id)
    deleted_follow_up_task = None
    created_follow_up_task = None
    leaving_on_hold = bool(
        pipeline_service.stage_matches_key(current_stage, "on_hold")
        and not pipeline_service.stage_matches_key(new_stage, "on_hold")
    )

    if leaving_on_hold:
        deleted_follow_up_task = _cleanup_on_hold_follow_up_task(db, surrogate=surrogate)

    surrogate.stage_id = new_stage.id
    surrogate.status_label = new_stage.label

    if pipeline_service.stage_matches_key(new_stage, "on_hold"):
        surrogate.paused_from_stage_id = paused_from_stage.id if paused_from_stage else old_stage_id
        created_follow_up_task = _create_on_hold_follow_up_task(
            db,
            surrogate=surrogate,
            paused_from_stage=paused_from_stage,
            actor_user_id=user_id,
            reason=reason or "",
            effective_at=effective_at,
            org_timezone_str=resolved_org_timezone,
            follow_up_months=on_hold_follow_up_months,
        )
        surrogate.on_hold_follow_up_task_id = (
            created_follow_up_task.id if created_follow_up_task else None
        )

    # Update contact status if reached or leaving intake stage
    if surrogate.contact_status == ContactStatus.UNREACHED.value:
        if pipeline_service.stage_matches_key(new_stage, SurrogateStatus.CONTACTED.value) or (
            new_stage.is_intake_stage is False
            and not pipeline_service.stage_matches_key(new_stage, "on_hold")
        ):
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

    if deleted_follow_up_task is not None:
        from app.services import task_service

        task_service._delete_task_from_google_best_effort(db, deleted_follow_up_task)
    if created_follow_up_task is not None:
        from app.services import task_service

        task_service._sync_task_to_google_best_effort(db, created_follow_up_task)

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
        trigger_workflows=trigger_workflows,
    )

    return StatusChangeResult(
        status="applied",
        surrogate=surrogate,
        request_id=None,
        message=None,
    )
