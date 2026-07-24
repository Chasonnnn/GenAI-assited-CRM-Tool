"""Resend webhook reconciliation job handlers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.db.enums import JobScope
from app.db.models import EmailLog, ResendWebhookEvent


async def process_resend_event_reconcile(db, job) -> None:
    """Project a durably accepted Resend event after its EmailLog is available."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    event_id_value = payload.get("event_id")
    try:
        event_id = UUID(str(event_id_value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Resend event reconciliation payload") from exc

    event = (
        db.query(ResendWebhookEvent)
        .filter(
            ResendWebhookEvent.id == event_id,
            ResendWebhookEvent.organization_id == job.organization_id,
        )
        .first()
    )
    if event is None:
        raise ValueError("Resend webhook event not found")
    if event.processed_at is not None:
        return

    event_payload = event.payload if isinstance(event.payload, dict) else {}
    data_value = event_payload.get("data")
    data = data_value if isinstance(data_value, dict) else {}
    email_id = data.get("email_id")
    if not isinstance(email_id, str) or not email_id:
        raise ValueError("Resend webhook event has no email_id")

    from app.services.webhooks.resend import (
        _organization_email_log_from_correlation_tags,
    )

    email_log, correlation_tags_present = _organization_email_log_from_correlation_tags(
        db,
        organization_id=job.organization_id,
        email_id=email_id,
        data=data,
        provider_scope=event.provider_scope or "organization",
        provider_account_id=(event.provider_account_id or f"organization:{job.organization_id}"),
    )
    if not correlation_tags_present:
        email_log = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == job.organization_id,
                EmailLog.provider == "resend",
                EmailLog.provider_scope == (event.provider_scope or "organization"),
                EmailLog.provider_account_id
                == (event.provider_account_id or f"organization:{job.organization_id}"),
                EmailLog.external_id == email_id,
            )
            .first()
        )
    if email_log is None:
        attempts = max(1, int(getattr(job, "attempts", 1) or 1))
        delay_seconds = min(300, 5 * (2 ** (attempts - 1)))
        job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        raise RuntimeError("Resend event correlation pending")

    from app.services.webhooks.resend import _process_verified_payload

    _process_verified_payload(
        db,
        event=event,
        email_log=email_log,
        payload=event_payload,
    )


async def process_resend_readiness_check(db, job) -> None:
    """Probe exactly the durable job's trusted organization or platform route."""
    from app.services import resend_readiness_service

    payload = job.payload if isinstance(job.payload, dict) else {}
    provider_scope = payload.get("provider_scope")
    if (
        job.job_scope == JobScope.ORGANIZATION.value
        and job.organization_id is not None
        and provider_scope == JobScope.ORGANIZATION.value
    ):
        result = await resend_readiness_service.refresh_organization_readiness(
            db,
            organization_id=job.organization_id,
        )
    elif (
        job.job_scope == JobScope.PLATFORM.value
        and job.organization_id is None
        and provider_scope == JobScope.PLATFORM.value
    ):
        result = await resend_readiness_service.refresh_platform_readiness(db)
    else:
        raise ValueError("Invalid Resend readiness job scope")

    retry_after = result.retry_after_seconds
    if retry_after is not None or not result.persisted:
        delay_seconds = max(0, min(3600, int(retry_after or 0)))
        job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        db.flush()
        raise RuntimeError("Resend readiness retry requested")
