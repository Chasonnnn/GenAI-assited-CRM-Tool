"""Surrogate domain events for side effects."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobType, OwnerType, SurrogateSource
from app.db.models import MetaLead, PipelineStage, Surrogate


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None):
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


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
) -> None:
    """Dispatch surrogate status change side effects."""
    from app.services import notification_facade, queue_service, workflow_triggers

    actor = _get_org_user(db, surrogate.organization_id, user_id)
    actor_name = actor.display_name if actor else "Someone"

    notification_facade.notify_surrogate_status_changed(
        db=db,
        surrogate=surrogate,
        from_status=old_label,
        to_status=new_stage.label,
        actor_id=user_id or surrogate.created_by_user_id or surrogate.owner_id,
        actor_name=actor_name,
    )

    if new_stage.slug == "approved":
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
            pass  # Best-effort: don't block status change

    _maybe_send_capi_event(db, surrogate, old_slug or "", new_stage.slug)

    workflow_triggers.trigger_status_changed(
        db=db,
        surrogate=surrogate,
        old_stage_id=old_stage_id,
        new_stage_id=new_stage.id,
        old_stage_slug=old_slug,
        new_stage_slug=new_stage.slug,
        effective_at=effective_at,
        recorded_at=recorded_at,
        is_undo=is_undo,
        request_id=request_id,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
        requested_at=requested_at,
        changed_by_user_id=user_id,
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

    if not meta_capi.should_send_capi_event(old_status, new_status):
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
