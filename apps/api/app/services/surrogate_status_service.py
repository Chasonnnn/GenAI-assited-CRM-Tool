"""Surrogate status change helpers (apply + history + notifications)."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import ContactStatus, OwnerType, SurrogateStatus
from app.db.models import PipelineStage, Surrogate, SurrogateStatusHistory, User


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    surrogate: Surrogate | None
    request_id: UUID | None
    message: str | None


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None) -> User | None:
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


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

    # Send notifications
    from app.services import notification_facade

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

    # If transitioning to approved, auto-assign to Surrogate Pool queue
    if new_stage.slug == "approved":
        from app.services import queue_service

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

    # Meta CAPI: Send lead quality signal for Meta-sourced surrogates
    _maybe_send_capi_event(db, surrogate, old_slug or "", new_stage.slug)

    # Trigger workflows with effective_at in payload
    from app.services import workflow_triggers

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

    return StatusChangeResult(
        status="applied",
        surrogate=surrogate,
        request_id=None,
        message=None,
    )


def _maybe_send_capi_event(
    db: Session, surrogate: Surrogate, old_status: str, new_status: str
) -> None:
    """
    Send Meta Conversions API event if applicable.

    Triggers when:
    - Surrogatesource is META
    - Status changes into a different Meta status bucket

    Note: Per-account CAPI enablement is checked in the worker handler,
    allowing us to skip surrogates without an ad account or where CAPI is disabled.
    """
    from app.db.enums import SurrogateSource, JobType
    from app.services import job_service

    # Only for Meta-sourced surrogates
    if surrogate.source != SurrogateSource.META.value:
        return

    # Check if this status change should trigger CAPI
    from app.services.meta_capi import should_send_capi_event

    if not should_send_capi_event(old_status, new_status):
        return

    # Need the original meta_lead_id
    if not surrogate.meta_lead_id:
        return

    # Get the meta lead to get the original Meta leadgen_id
    from app.db.models import MetaLead

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
        # Offload to worker for reliability (no event-loop assumptions, retries supported)
        idempotency_key = f"meta_capi:{meta_lead.meta_lead_id}:{new_status}"
        job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.META_CAPI_EVENT,
            payload={
                "meta_lead_id": meta_lead.meta_lead_id,
                "meta_ad_external_id": surrogate.meta_ad_external_id,  # For per-account CAPI
                "surrogate_status": new_status,
                "email": surrogate.email,
                "phone": surrogate.phone,
                "meta_page_id": meta_lead.meta_page_id,
            },
            idempotency_key=idempotency_key,
        )
    except Exception:
        # Best-effort: never block status change on CAPI scheduling.
        return
