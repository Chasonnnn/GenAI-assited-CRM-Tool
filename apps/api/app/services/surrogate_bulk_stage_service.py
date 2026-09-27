"""Stage changes for explicitly selected surrogates."""

import logging
from uuid import UUID

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, Role
from app.schemas.surrogate import (
    BulkStageChange,
    BulkStageChangeFailure,
    BulkStageChangeResult,
)

logger = logging.getLogger(__name__)


def change_selected_stage(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: Role,
    data: BulkStageChange,
    request: Request | None = None,
) -> BulkStageChangeResult:
    """Move each selected surrogate through the single stage-change rules.

    Each row commits or rolls back on its own, with its history, note and
    appointment records. Request-level input errors raise ValueError before any row runs.
    """
    from app.services import (
        audit_service,
        dashboard_service,
        pipeline_semantics_service,
        pipeline_service,
        surrogate_service,
        surrogate_status_service,
    )

    surrogate_pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    target_stage = pipeline_service.get_stage_by_id(db, data.stage_id)
    if (
        not target_stage
        or not target_stage.is_active
        or target_stage.pipeline_id != surrogate_pipeline.id
    ):
        raise ValueError("Invalid or inactive stage")

    target_stage_id = target_stage.id
    target_stage_slug = target_stage.slug
    is_interview = pipeline_service.stage_matches_key(target_stage, "interview_scheduled")
    reason = (data.reason or "").strip() or None

    if data.interview_times and not is_interview:
        raise ValueError("Interview times are only allowed when moving to Interview Scheduled")
    if data.on_hold_follow_up_months is not None and not pipeline_service.stage_matches_key(
        target_stage, "on_hold"
    ):
        raise ValueError("Follow-up timing is only allowed when moving to On-Hold")
    target_semantics = pipeline_semantics_service.get_stage_semantics(target_stage)
    if target_semantics.requires_reason_on_enter and not reason:
        raise ValueError(f"Reason required when moving to {target_stage.label}")
    # Like the single flow, times are checked against the owner's availability unless the
    # user chose an override; the shared reason is then the override reason.
    if data.override_availability and not is_interview:
        raise ValueError("Availability override applies only to interview scheduling")
    if data.override_availability and not reason:
        raise ValueError("Reason required to override availability")

    interview_times = {entry.surrogate_id: entry.scheduled_at for entry in data.interview_times}
    archived_by_id = surrogate_service.get_surrogate_archive_state_by_ids(
        db,
        org_id,
        data.surrogate_ids,
    )
    applied = 0
    pending_approval = 0
    failed: list[BulkStageChangeFailure] = []

    def fail(surrogate_id: UUID, message: str) -> None:
        failed.append(BulkStageChangeFailure(surrogate_id=surrogate_id, reason=message))

    for surrogate_id in data.surrogate_ids:
        if surrogate_id not in archived_by_id:
            fail(surrogate_id, "Surrogate not found")
            continue
        if archived_by_id[surrogate_id]:
            fail(surrogate_id, "Cannot change status of archived surrogate")
            continue

        db.expunge_all()
        surrogate = surrogate_service.get_surrogate(db, org_id, surrogate_id)
        if surrogate is None:
            fail(surrogate_id, "Surrogate not found")
            continue
        if surrogate.is_archived:
            fail(surrogate_id, "Cannot change status of archived surrogate")
            continue

        try:
            with db.begin_nested():
                result = surrogate_status_service.change_status(
                    db=db,
                    surrogate=surrogate,
                    new_stage_id=target_stage_id,
                    user_id=user_id,
                    user_role=user_role,
                    reason=reason,
                    interview_scheduled_at=interview_times.get(surrogate_id),
                    on_hold_follow_up_months=data.on_hold_follow_up_months,
                    override_availability=data.override_availability,
                    override_reason=reason if data.override_availability else None,
                    commit=False,
                )
        except ValueError as exc:
            fail(surrogate_id, str(exc))
            continue
        except SQLAlchemyError as exc:
            logger.warning(
                "surrogate_bulk_stage_change_row_failed",
                extra={"surrogate_id": str(surrogate_id), "error_class": type(exc).__name__},
            )
            fail(surrogate_id, "Stage change failed")
            continue

        db.commit()
        after_commit = result.get("after_commit")
        if after_commit is not None:
            after_commit()
        if result["status"] == "applied":
            applied += 1
        elif result["status"] == "pending_approval":
            pending_approval += 1
        else:
            fail(surrogate_id, "Stage change was not applied")

    if applied or pending_approval:
        dashboard_service.push_dashboard_stats(db, org_id)

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.SURROGATE_BULK_STATUS_CHANGED,
        actor_user_id=user_id,
        target_type="surrogate",
        details={
            "requested_count": len(data.surrogate_ids),
            "applied_count": applied,
            "pending_approval_count": pending_approval,
            "failed_count": len(failed),
            "target_stage_id": str(target_stage_id),
            "target_stage_slug": target_stage_slug,
            "reason_provided": reason is not None,
            "on_hold_follow_up_months": data.on_hold_follow_up_months,
            "interview_time_count": len(interview_times),
            "override_availability": data.override_availability,
        },
        request=request,
    )
    db.commit()

    return BulkStageChangeResult(
        requested=len(data.surrogate_ids),
        applied=applied,
        pending_approval=pending_approval,
        failed=failed,
    )
