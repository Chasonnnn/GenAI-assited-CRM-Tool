"""Lifecycle helpers for PII-safe email reconciliation cases."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import select

from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, JobStatus, JobType
from app.db.models import EmailDelivery, EmailReconciliationCase, Job, ResendWebhookEvent


_DELIVERY_REASON_CODES = {
    "idempotency_window_expired": "idempotency_window_expired",
    "lease_expired": "delivery_lease_expired",
    "provider_outcome_unknown": "provider_outcome_unknown",
}
_EVENT_RECONCILE_MAX_ATTEMPTS = 8


class ReconciliationCaseNotFound(LookupError):
    """The case is absent from the authenticated organization."""


class ReconciliationCaseConflict(RuntimeError):
    """The case changed or is no longer eligible for the requested action."""


def ensure_orphan_webhook_case(
    db: Session,
    *,
    event: ResendWebhookEvent,
    status: str = "pending",
    reason_code: str = "correlation_pending",
    visible_transition: bool = False,
) -> EmailReconciliationCase:
    """Create or safely advance the operator case for one accepted orphan event."""
    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == event.organization_id,
            EmailReconciliationCase.resend_webhook_event_id == event.id,
        )
        .one_or_none()
    )
    if case is None:
        case = EmailReconciliationCase(
            organization_id=event.organization_id,
            case_type="orphan_webhook",
            status=status,
            reason_code=reason_code,
            resend_webhook_event_id=event.id,
            detected_at=event.received_at or datetime.now(timezone.utc),
        )
        db.add(case)
        db.flush()
        return case

    if case.status in {"resolved", "dismissed"}:
        return case
    if case.status != status or case.reason_code != reason_code:
        case.status = status
        case.reason_code = reason_code
        case.updated_at = datetime.now(timezone.utc)
        case.resolved_at = None
        case.resolved_by_user_id = None
        case.resolution_code = None
        case.version += 1
    elif visible_transition:
        case.updated_at = datetime.now(timezone.utc)
        case.version += 1
    return case


def resolve_orphan_webhook_case(
    db: Session,
    *,
    event: ResendWebhookEvent,
    resolution_code: str = "correlated_automatically",
) -> EmailReconciliationCase | None:
    """Resolve an existing orphan case after its signed event is projected."""
    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == event.organization_id,
            EmailReconciliationCase.resend_webhook_event_id == event.id,
        )
        .one_or_none()
    )
    if case is None or case.status == "resolved":
        return case

    resolved_at = datetime.now(timezone.utc)
    case.status = "resolved"
    case.reason_code = "correlation_succeeded"
    case.resolved_at = resolved_at
    case.resolution_code = resolution_code
    case.updated_at = resolved_at
    case.version += 1
    return case


def ensure_unknown_delivery_case(
    db: Session,
    *,
    delivery: EmailDelivery,
    error_type: str,
    detected_at: datetime,
) -> EmailReconciliationCase:
    """Create the single action-required case for an unresolved provider outcome."""
    reason_code = _DELIVERY_REASON_CODES.get(error_type, "provider_outcome_unknown")
    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == delivery.organization_id,
            EmailReconciliationCase.email_delivery_id == delivery.id,
        )
        .one_or_none()
    )
    if case is None:
        case = EmailReconciliationCase(
            organization_id=delivery.organization_id,
            case_type="unknown_delivery",
            status="action_required",
            reason_code=reason_code,
            email_delivery_id=delivery.id,
            detected_at=detected_at,
        )
        db.add(case)
        db.flush()
        return case

    if case.status not in {"resolved", "dismissed"} and (
        case.status != "action_required" or case.reason_code != reason_code
    ):
        case.status = "action_required"
        case.reason_code = reason_code
        case.updated_at = detected_at
        case.version += 1
    return case


def resolve_unknown_delivery_case(
    db: Session,
    *,
    delivery: EmailDelivery,
    resolution_code: str = "provider_evidence_superseded",
) -> EmailReconciliationCase | None:
    """Make later verified provider acceptance authoritative over operator state."""
    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == delivery.organization_id,
            EmailReconciliationCase.email_delivery_id == delivery.id,
        )
        .one_or_none()
    )
    if case is None:
        return None
    if case.status == "resolved" and case.resolution_code == resolution_code:
        return case

    resolved_at = datetime.now(timezone.utc)
    case.status = "resolved"
    case.reason_code = "provider_acceptance_verified"
    case.resolved_at = resolved_at
    case.resolved_by_user_id = None
    case.resolution_code = resolution_code
    case.updated_at = resolved_at
    case.version += 1
    return case


def retry_orphan_correlation(
    db: Session,
    *,
    organization_id: UUID,
    case_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    request: Request | None = None,
) -> EmailReconciliationCase:
    """Requeue local correlation only; this action never invokes provider transport."""
    case_snapshot = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == organization_id,
            EmailReconciliationCase.id == case_id,
        )
        .one_or_none()
    )
    if case_snapshot is None or case_snapshot.resend_webhook_event_id is None:
        raise ReconciliationCaseNotFound

    event = db.execute(
        select(ResendWebhookEvent)
        .where(
            ResendWebhookEvent.organization_id == organization_id,
            ResendWebhookEvent.id == case_snapshot.resend_webhook_event_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if event is None:
        raise ReconciliationCaseNotFound

    case = db.execute(
        select(EmailReconciliationCase)
        .where(
            EmailReconciliationCase.organization_id == organization_id,
            EmailReconciliationCase.id == case_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if case is None:
        raise ReconciliationCaseNotFound
    if case.version != expected_version:
        raise ReconciliationCaseConflict
    if (
        case.case_type != "orphan_webhook"
        or case.status != "action_required"
        or event.processed_at is not None
    ):
        raise ReconciliationCaseConflict

    idempotency_key = (
        f"resend-event-reconcile/{organization_id}/{event.provider_event_id}"
    )
    job = (
        db.query(Job)
        .filter(
            Job.organization_id == organization_id,
            Job.idempotency_key == idempotency_key,
        )
        .with_for_update()
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if job is None:
        job = Job(
            organization_id=organization_id,
            job_type=JobType.RESEND_EVENT_RECONCILE.value,
            payload={"event_id": str(event.id)},
            run_at=now,
            status=JobStatus.PENDING.value,
            max_attempts=_EVENT_RECONCILE_MAX_ATTEMPTS,
            idempotency_key=idempotency_key,
        )
        db.add(job)
    elif job.status == JobStatus.FAILED.value:
        from app.services import job_service

        job_service.replay_failed_job(
            db,
            org_id=organization_id,
            job_id=job.id,
            reason="Operator requested local event correlation retry",
            commit=False,
        )
        job.max_attempts = _EVENT_RECONCILE_MAX_ATTEMPTS
    elif job.status not in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
        raise ReconciliationCaseConflict

    previous_version = case.version
    case.status = "pending"
    case.reason_code = "operator_retry_requested"
    case.resolved_at = None
    case.resolved_by_user_id = None
    case.resolution_code = None
    case.updated_at = now
    case.version += 1

    from app.services import audit_service

    audit_service.log_event(
        db,
        org_id=organization_id,
        event_type=AuditEventType.EMAIL_RECONCILIATION_RETRIED,
        actor_user_id=actor_user_id,
        target_type="email_reconciliation_case",
        target_id=case.id,
        details={
            "action": "retry_correlation",
            "case_type": case.case_type,
            "from_version": previous_version,
            "reason_code": case.reason_code,
            "to_version": case.version,
        },
        request=request,
    )
    db.commit()
    db.refresh(case)
    return case


def mark_orphan_case_exhausted_for_job(
    db: Session,
    *,
    job: Job,
) -> EmailReconciliationCase | None:
    """Expose a controlled operator state when automatic correlation is exhausted."""
    if job.job_type != JobType.RESEND_EVENT_RECONCILE.value:
        return None
    payload = job.payload if isinstance(job.payload, dict) else {}
    try:
        event_id = UUID(str(payload.get("event_id")))
    except (TypeError, ValueError):
        return None

    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == job.organization_id,
            EmailReconciliationCase.resend_webhook_event_id == event_id,
        )
        .one_or_none()
    )
    if case is None or case.status in {"resolved", "dismissed"}:
        return case
    if (
        case.status != "action_required"
        or case.reason_code != "automatic_correlation_exhausted"
    ):
        case.status = "action_required"
        case.reason_code = "automatic_correlation_exhausted"
        case.updated_at = datetime.now(timezone.utc)
        case.version += 1
    return case


def mark_orphan_case_claim_expired(
    db: Session,
    *,
    job: Job,
) -> EmailReconciliationCase | None:
    """Return a stranded automatic correlation case to its visible pending state."""
    if job.job_type != JobType.RESEND_EVENT_RECONCILE.value:
        return None
    payload = job.payload if isinstance(job.payload, dict) else {}
    try:
        event_id = UUID(str(payload.get("event_id")))
    except (TypeError, ValueError):
        return None

    case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == job.organization_id,
            EmailReconciliationCase.resend_webhook_event_id == event_id,
        )
        .one_or_none()
    )
    if case is None or case.status in {"resolved", "dismissed"}:
        return case
    if case.status != "pending" or case.reason_code != "worker_claim_expired":
        case.status = "pending"
        case.reason_code = "worker_claim_expired"
        case.updated_at = datetime.now(timezone.utc)
        case.version += 1
    return case
