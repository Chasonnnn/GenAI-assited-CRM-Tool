"""Surrogate domain events for side effects."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobType, OwnerType, SurrogateSource
from app.db.models import MetaLead, PipelineStage, Surrogate

logger = logging.getLogger(__name__)


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None):
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


def _record_side_effect_failure(
    *,
    surrogate: Surrogate,
    alert_type,
    title: str,
    integration_key: str,
    exc: Exception,
    details: dict | None = None,
) -> None:
    from app.db.enums import AlertSeverity
    from app.services import alert_service

    logger.exception(title)
    alert_service.record_alert_isolated(
        org_id=surrogate.organization_id,
        alert_type=alert_type,
        severity=AlertSeverity.ERROR,
        title=title,
        message=str(exc)[:500],
        integration_key=integration_key,
        error_class=type(exc).__name__,
        details=details,
    )


def handle_status_changed(
    *,
    db: Session,
    surrogate: Surrogate,
    new_stage: PipelineStage,
    old_stage_id: UUID | None,
    old_label: str | None,
    old_slug: str | None,
    user_id: UUID | None,
    effective_at: datetime,
    recorded_at: datetime,
    is_undo: bool,
    request_id: UUID | None,
    approved_by_user_id: UUID | None,
    approved_at: datetime | None,
    requested_at: datetime | None,
    trigger_workflows: bool = True,
) -> None:
    """Dispatch surrogate status change side effects."""
    from app.db.enums import AlertType
    from app.services import notification_facade, pipeline_service, queue_service, workflow_triggers

    actor = _get_org_user(db, surrogate.organization_id, user_id)
    actor_name = actor.display_name if actor else "Someone"
    old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
    old_stage_key = pipeline_service.get_stage_semantic_key(old_stage) or old_slug or ""
    new_stage_key = pipeline_service.get_stage_semantic_key(new_stage) or new_stage.slug

    if not pipeline_service.stage_matches_key(new_stage, "application_submitted"):
        try:
            notification_facade.notify_surrogate_status_changed(
                db=db,
                surrogate=surrogate,
                from_status=old_label,
                to_status=new_stage.label,
                actor_id=user_id or surrogate.created_by_user_id or surrogate.owner_id,
                actor_name=actor_name,
            )
        except Exception as exc:
            _record_side_effect_failure(
                surrogate=surrogate,
                alert_type=AlertType.NOTIFICATION_PUSH_FAILED,
                title="Surrogate status notification failed",
                integration_key="surrogate_status_changed",
                exc=exc,
                details={
                    "surrogate_id": str(surrogate.id),
                    "old_stage_id": str(old_stage_id) if old_stage_id else None,
                    "new_stage_id": str(new_stage.id),
                    "old_stage_slug": old_slug,
                    "new_stage_slug": new_stage.slug,
                },
            )

    if pipeline_service.stage_matches_key(new_stage, "approved"):
        try:
            pool_queue = queue_service.get_or_create_surrogate_pool_queue(
                db, surrogate.organization_id
            )
            if pool_queue and (
                surrogate.owner_type != OwnerType.QUEUE.value or surrogate.owner_id != pool_queue.id
            ):
                surrogate = queue_service.assign_surrogate_to_queue(
                    db=db,
                    org_id=surrogate.organization_id,
                    surrogate_id=surrogate.id,
                    queue_id=pool_queue.id,
                    assigner_user_id=user_id,
                )
                db.commit()
                db.refresh(surrogate)
            if pool_queue:
                notification_facade.notify_surrogate_ready_for_claim(db=db, surrogate=surrogate)
        except Exception:
            logger.debug("surrogate_ready_for_claim_notify_failed", exc_info=True)

    _maybe_send_capi_event(db, surrogate, old_stage_key, new_stage_key)
    _dispatch_conversion_events(
        db,
        surrogate,
        new_stage_key=new_stage_key,
        new_stage_slug=new_stage.slug,
        new_stage_id=str(new_stage.id),
        new_stage_label=new_stage.label,
        effective_at=effective_at,
    )

    if trigger_workflows:
        try:
            workflow_triggers.trigger_status_changed(
                db=db,
                surrogate=surrogate,
                old_stage_id=old_stage_id,
                new_stage_id=new_stage.id,
                old_stage_slug=old_slug,
                new_stage_slug=new_stage.slug,
                old_stage_key=old_stage_key or None,
                new_stage_key=new_stage_key,
                effective_at=effective_at,
                recorded_at=recorded_at,
                is_undo=is_undo,
                request_id=request_id,
                approved_by_user_id=approved_by_user_id,
                approved_at=approved_at,
                requested_at=requested_at,
                changed_by_user_id=user_id,
            )
        except Exception as exc:
            _record_side_effect_failure(
                surrogate=surrogate,
                alert_type=AlertType.WORKFLOW_EXECUTION_FAILED,
                title="Surrogate status workflow trigger failed",
                integration_key="surrogate_status_changed",
                exc=exc,
                details={
                    "surrogate_id": str(surrogate.id),
                    "old_stage_id": str(old_stage_id) if old_stage_id else None,
                    "new_stage_id": str(new_stage.id),
                    "old_stage_slug": old_slug,
                    "new_stage_slug": new_stage.slug,
                    "request_id": str(request_id) if request_id else None,
                },
            )


def _maybe_send_capi_event(
    db: Session, surrogate: Surrogate, old_status: str, new_status: str
) -> None:
    """
    Send Meta Conversions API event if applicable.

    Triggers when:
    - Surrogate source is META
    - Status changes into a different Meta status bucket
    """
    from app.services import job_service, meta_capi

    if surrogate.source != SurrogateSource.META.value:
        return

    if not meta_capi.should_send_capi_event_for_org(
        db,
        surrogate.organization_id,
        old_status,
        new_status,
    ):
        return

    if not surrogate.meta_lead_id:
        return

    meta_lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.id == surrogate.meta_lead_id,
            MetaLead.organization_id == surrogate.organization_id,
        )
        .first()
    )
    if not meta_lead:
        return

    try:
        idempotency_key = f"meta_capi:{meta_lead.meta_lead_id}:{new_status}"
        job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.META_CAPI_EVENT,
            payload={
                "meta_lead_id": meta_lead.meta_lead_id,
                "meta_ad_external_id": surrogate.meta_ad_external_id,
                "surrogate_status": new_status,
                "email": surrogate.email,
                "phone": surrogate.phone,
                "meta_page_id": meta_lead.meta_page_id,
            },
            idempotency_key=idempotency_key,
        )
    except Exception:
        return


def _maybe_send_zapier_stage_event(
    db: Session,
    surrogate: Surrogate,
    *,
    new_stage_key: str,
    new_stage_slug: str,
    new_stage_id: str,
    new_stage_label: str | None,
    effective_at: datetime,
    source: str = "automatic",
) -> None:
    """Send stage changes to Zapier when outbound integration is configured."""
    from app.services import zapier_outbound_service

    try:
        zapier_outbound_service.enqueue_stage_event(
            db=db,
            surrogate=surrogate,
            stage_key=new_stage_key,
            stage_slug=new_stage_slug,
            stage_id=new_stage_id,
            stage_label=new_stage_label,
            effective_at=effective_at,
            source=source,
        )
    except Exception:
        return


def _maybe_send_meta_crm_dataset_stage_event(
    db: Session,
    surrogate: Surrogate,
    *,
    new_stage_key: str,
    new_stage_slug: str,
    new_stage_id: str,
    new_stage_label: str | None,
    effective_at: datetime,
    source: str = "automatic",
) -> None:
    """Send stage changes to the direct Meta CRM dataset integration when configured."""
    from app.services import meta_crm_dataset_service

    try:
        meta_crm_dataset_service.enqueue_stage_event(
            db=db,
            surrogate=surrogate,
            stage_key=new_stage_key,
            stage_slug=new_stage_slug,
            stage_id=new_stage_id,
            stage_label=new_stage_label,
            effective_at=effective_at,
            source=source,
        )
    except Exception:
        return


def _dispatch_conversion_events(
    db: Session,
    surrogate: Surrogate,
    *,
    new_stage_key: str,
    new_stage_slug: str,
    new_stage_id: str,
    new_stage_label: str | None,
    effective_at: datetime,
    source: str = "automatic",
) -> None:
    _maybe_send_zapier_stage_event(
        db,
        surrogate,
        new_stage_key=new_stage_key,
        new_stage_slug=new_stage_slug,
        new_stage_id=new_stage_id,
        new_stage_label=new_stage_label,
        effective_at=effective_at,
        source=source,
    )
    _maybe_send_meta_crm_dataset_stage_event(
        db,
        surrogate,
        new_stage_key=new_stage_key,
        new_stage_slug=new_stage_slug,
        new_stage_id=new_stage_id,
        new_stage_label=new_stage_label,
        effective_at=effective_at,
        source=source,
    )


def handle_surrogate_created(*, db: Session, surrogate: Surrogate) -> None:
    """Emit initial outbound conversion events for Meta-sourced surrogates."""
    from app.services import pipeline_service

    if surrogate.source != SurrogateSource.META.value or not surrogate.stage_id:
        return

    stage = db.query(PipelineStage).filter(PipelineStage.id == surrogate.stage_id).first()
    if not stage:
        return
    stage_key = pipeline_service.get_stage_semantic_key(stage)
    if stage_key == "new_unread":
        return

    _maybe_send_capi_event(db, surrogate, "", stage_key or "")
    _dispatch_conversion_events(
        db,
        surrogate,
        new_stage_key=stage_key or stage.slug,
        new_stage_slug=stage.slug,
        new_stage_id=str(stage.id),
        new_stage_label=stage.label,
        effective_at=surrogate.created_at or datetime.now(timezone.utc),
    )
