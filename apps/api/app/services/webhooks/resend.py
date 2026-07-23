"""Resend webhook handlers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailLog, ResendWebhookEvent
from app.services import resend_settings_service

logger = logging.getLogger(__name__)

_DELIVERY_STATUS_RANK = {
    "scheduled": 5,
    "sent": 10,
    "delivery_delayed": 20,
    "delivered": 30,
    "failed": 40,
    "suppressed": 50,
    "bounced": 60,
    "complained": 70,
}
_DELIVERY_EVENT_STATUS = {
    "email.scheduled": "scheduled",
    "email.sent": "sent",
    "email.delivery_delayed": "delivery_delayed",
    "email.delivered": "delivered",
    "email.failed": "failed",
    "email.suppressed": "suppressed",
    "email.bounced": "bounced",
    "email.complained": "complained",
}
_DELIVERY_FAILURE_EVENTS = {
    "email.failed",
    "email.suppressed",
    "email.bounced",
    "email.complained",
}
_EVENT_RECONCILE_MAX_ATTEMPTS = 8


def _verify_svix_signature(
    body: bytes,
    headers: dict,
    secret: str,
) -> bool:
    """
    Verify Resend webhook signature using Svix.

    Resend uses Svix for webhooks. The signature is in 'svix-signature' header.
    """
    svix_id = headers.get("svix-id", "")
    svix_timestamp = headers.get("svix-timestamp", "")
    svix_signature = headers.get("svix-signature", "")

    if not svix_id or not svix_timestamp or not svix_signature:
        return False

    # Reject stale or malformed timestamps to prevent replay attacks.
    try:
        timestamp = int(svix_timestamp)
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if abs(now - timestamp) > 300:
        return False

    # Build the signed payload
    signed_payload = f"{svix_id}.{svix_timestamp}.{body.decode('utf-8')}"

    def _pad_b64(value: str) -> str:
        return value + "=" * (-len(value) % 4)

    # Decode the secret (Svix uses whsec_ + base64url). If no whsec_ prefix,
    # treat the secret as raw bytes (matches our tests + backward compatibility).
    if secret.startswith("whsec_"):
        secret = secret[6:]  # Remove "whsec_" prefix
        secret_bytes = None
        # Try urlsafe first since our _generate_webhook_secret uses urlsafe_b64encode.
        # Standard b64decode silently corrupts urlsafe chars instead of raising.
        for decoder in (base64.urlsafe_b64decode, base64.b64decode):
            try:
                decoded = decoder(_pad_b64(secret))
            except Exception:
                decoded = None
            if decoded:
                secret_bytes = decoded
                break
        if secret_bytes is None:
            logger.warning("Invalid Resend webhook signing secret: malformed whsec_ encoding")
            return False
    else:
        secret_bytes = secret.encode("utf-8")

    # Compute HMAC-SHA256
    expected = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    # Check against all provided signatures (v1, v1a, etc.)
    # svix-signature format: "v1,base64signature v1,base64signature2"
    for sig_entry in svix_signature.split(" "):
        parts = sig_entry.split(",", 1)
        if len(parts) == 2:
            version, sig = parts
            if version == "v1" and hmac.compare_digest(sig, expected_b64):
                return True

    return False


def _parse_event_created_at(value: object) -> datetime:
    """Parse Resend's root created_at timestamp, falling back to receipt time."""
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            logger.warning("Resend webhook has invalid created_at timestamp")
    return datetime.now(timezone.utc)


def _first_timestamp(current: datetime | None, event_created_at: datetime) -> datetime:
    """Retain the earliest provider timestamp for a delivery milestone."""
    if current is None or event_created_at < current:
        return event_created_at
    return current


def _advance_delivery_state(
    email_log: EmailLog,
    *,
    resend_status: str,
    event_created_at: datetime,
) -> bool:
    """Apply rank-monotonic delivery transitions from unordered provider events."""
    current_status = email_log.resend_status
    current_rank = _DELIVERY_STATUS_RANK.get(current_status or "", 0)
    next_rank = _DELIVERY_STATUS_RANK[resend_status]

    if next_rank < current_rank:
        return False
    if (
        next_rank == current_rank
        and email_log.resend_status_at
        and event_created_at <= email_log.resend_status_at
    ):
        return False

    email_log.resend_status = resend_status
    email_log.resend_status_at = event_created_at
    return True


def _provider_error(data: dict, fallback: str) -> str:
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    elif isinstance(error, str) and error.strip():
        return error.strip()
    return fallback


def _is_permanent_bounce(raw_bounce_type: str) -> bool:
    normalized = raw_bounce_type.strip().casefold().replace("_", "-")
    return normalized == "hard" or normalized.startswith("permanent")


def _accept_verified_event(
    db: Session,
    *,
    organization_id: UUID,
    email_log: EmailLog | None,
    provider_event_id: str,
    event_type: str,
    event_created_at: datetime,
    payload: dict,
) -> tuple[ResendWebhookEvent, bool]:
    """Durably accept a verified event once, before message correlation."""
    inserted_id = db.execute(
        insert(ResendWebhookEvent)
        .values(
            organization_id=organization_id,
            email_log_id=email_log.id if email_log else None,
            provider_event_id=provider_event_id,
            event_type=event_type,
            event_created_at=event_created_at,
            payload=payload,
        )
        .on_conflict_do_nothing(constraint="uq_resend_webhook_events_org_provider_event")
        .returning(ResendWebhookEvent.id)
    ).scalar_one_or_none()
    if inserted_id is not None:
        event = (
            db.query(ResendWebhookEvent)
            .filter(
                ResendWebhookEvent.organization_id == organization_id,
                ResendWebhookEvent.id == inserted_id,
            )
            .one()
        )
        return event, True

    event = (
        db.query(ResendWebhookEvent)
        .filter(
            ResendWebhookEvent.organization_id == organization_id,
            ResendWebhookEvent.provider_event_id == provider_event_id,
        )
        .one()
    )
    return event, False


def _enqueue_event_reconciliation(db: Session, event: ResendWebhookEvent) -> None:
    """Ensure an accepted orphan event has a live bounded reconciliation job."""
    from app.db.enums import JobStatus, JobType
    from app.services import job_service

    idempotency_key = f"resend-event-reconcile/{event.organization_id}/{event.provider_event_id}"
    existing = job_service.get_job_by_idempotency_key(
        db,
        org_id=event.organization_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if existing.status == JobStatus.FAILED.value:
            existing = job_service.replay_failed_job(
                db,
                org_id=event.organization_id,
                job_id=existing.id,
                reason="Duplicate signed webhook revived orphan correlation",
                commit=False,
            )
            existing.run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
            existing.max_attempts = _EVENT_RECONCILE_MAX_ATTEMPTS
        return

    job = job_service.enqueue_job(
        db=db,
        org_id=event.organization_id,
        job_type=JobType.RESEND_EVENT_RECONCILE,
        payload={"event_id": str(event.id)},
        run_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        idempotency_key=idempotency_key,
        commit=False,
    )
    # Keep the bounded retry horizon beyond the normal two-minute delivery
    # lease so provider events can survive a send/commit race.
    job.max_attempts = _EVENT_RECONCILE_MAX_ATTEMPTS


def _campaign_recipient_for_email(db: Session, email_log: EmailLog):
    from app.db.models import CampaignRecipient, CampaignRun

    return (
        db.query(CampaignRecipient)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .filter(
            CampaignRun.organization_id == email_log.organization_id,
            CampaignRecipient.email_log_id == email_log.id,
        )
        .with_for_update(of=CampaignRecipient)
        .one_or_none()
    )


def _process_resend_event(
    db: Session,
    *,
    email_log: EmailLog,
    event_type: str | None,
    data: dict,
    event_created_at: datetime,
) -> None:
    from app.db.enums import CampaignRecipientStatus, EmailStatus
    from app.services import campaign_service

    resend_status = _DELIVERY_EVENT_STATUS.get(event_type or "")
    state_advanced = False
    if resend_status:
        state_advanced = _advance_delivery_state(
            email_log,
            resend_status=resend_status,
            event_created_at=event_created_at,
        )

    if event_type == "email.sent":
        if state_advanced:
            email_log.status = EmailStatus.SENT.value
            email_log.sent_at = _first_timestamp(email_log.sent_at, event_created_at)
            email_log.error = None

    elif event_type == "email.delivery_delayed":
        if state_advanced:
            email_log.status = EmailStatus.SENT.value
            email_log.error = _provider_error(data, "delivery delayed")

    elif event_type == "email.delivered":
        email_log.delivered_at = _first_timestamp(email_log.delivered_at, event_created_at)
        if state_advanced:
            email_log.status = EmailStatus.SENT.value
            email_log.error = None
        logger.info("Resend: email delivered for email_log=%s", email_log.id)

    elif event_type == "email.failed":
        if state_advanced:
            email_log.status = EmailStatus.FAILED.value
            email_log.error = _provider_error(data, "delivery failed")
        _downgrade_workflow_execution_for_delivery_failure(
            db, email_log=email_log, event_type=event_type
        )

    elif event_type == "email.suppressed":
        if state_advanced:
            email_log.status = EmailStatus.SKIPPED.value
            email_log.error = _provider_error(data, "suppressed by Resend")
        campaign_service.add_to_suppression(
            db,
            email_log.organization_id,
            email_log.recipient_email,
            "bounced",
            source_type="email_log",
            source_id=email_log.id,
        )
        _downgrade_workflow_execution_for_delivery_failure(
            db, email_log=email_log, event_type=event_type
        )

    elif event_type == "email.bounced":
        email_log.bounced_at = _first_timestamp(email_log.bounced_at, event_created_at)
        bounce_data = data.get("bounce")
        raw_bounce_type = (
            str(bounce_data.get("type") or "permanent")
            if isinstance(bounce_data, dict)
            else "permanent"
        )
        email_log.bounce_type = raw_bounce_type
        if state_advanced:
            email_log.status = EmailStatus.FAILED.value
            email_log.error = "bounced"
        _downgrade_workflow_execution_for_delivery_failure(
            db, email_log=email_log, event_type=event_type
        )
        _log_surrogate_email_bounced_activity(db, email_log=email_log)

        if _is_permanent_bounce(raw_bounce_type):
            campaign_service.add_to_suppression(
                db,
                email_log.organization_id,
                email_log.recipient_email,
                "bounced",
                source_type="email_log",
                source_id=email_log.id,
            )
            logger.info(
                "Resend: permanent bounce, added to suppression: email_log=%s",
                email_log.id,
            )
        else:
            logger.info(
                "Resend: non-permanent bounce (%s) for email_log=%s",
                raw_bounce_type,
                email_log.id,
            )

    elif event_type == "email.complained":
        email_log.complained_at = _first_timestamp(email_log.complained_at, event_created_at)
        if state_advanced:
            email_log.status = EmailStatus.FAILED.value
            email_log.error = "complaint"
        _downgrade_workflow_execution_for_delivery_failure(
            db, email_log=email_log, event_type=event_type
        )

        # Add to suppression list for complaints
        campaign_service.add_to_suppression(
            db,
            email_log.organization_id,
            email_log.recipient_email,
            "complaint",
            source_type="email_log",
            source_id=email_log.id,
        )
        logger.info(
            "Resend: complaint, added to suppression: email_log=%s",
            email_log.id,
        )

    elif event_type == "email.opened":
        email_log.open_count = (email_log.open_count or 0) + 1
        email_log.opened_at = _first_timestamp(email_log.opened_at, event_created_at)
        # Update campaign recipient if linked
        campaign_recipient = _campaign_recipient_for_email(db, email_log)
        if campaign_recipient:
            if not campaign_recipient.opened_at:
                campaign_recipient.opened_at = event_created_at
            campaign_recipient.open_count = (campaign_recipient.open_count or 0) + 1
            campaign_service.recompute_campaign_run_aggregates(
                db,
                organization_id=email_log.organization_id,
                run_id=campaign_recipient.run_id,
                commit=False,
            )
            logger.info("Resend: email opened for campaign_recipient=%s", campaign_recipient.id)

    elif event_type == "email.clicked":
        email_log.click_count = (email_log.click_count or 0) + 1
        email_log.clicked_at = _first_timestamp(email_log.clicked_at, event_created_at)
        # Update campaign recipient if linked
        campaign_recipient = _campaign_recipient_for_email(db, email_log)
        if campaign_recipient:
            if not campaign_recipient.clicked_at:
                campaign_recipient.clicked_at = event_created_at
            campaign_recipient.click_count = (campaign_recipient.click_count or 0) + 1
            campaign_service.recompute_campaign_run_aggregates(
                db,
                organization_id=email_log.organization_id,
                run_id=campaign_recipient.run_id,
                commit=False,
            )
            logger.info("Resend: link clicked for campaign_recipient=%s", campaign_recipient.id)

    if state_advanced and event_type in {
        "email.sent",
        "email.delivered",
        *_DELIVERY_FAILURE_EVENTS,
    }:
        from app.services.email_delivery_service import (
            project_appointment_email_canonical_state,
        )

        project_appointment_email_canonical_state(
            db,
            email_log=email_log,
        )
        campaign_recipient = _campaign_recipient_for_email(db, email_log)
        if campaign_recipient:
            if event_type == "email.delivered":
                if campaign_recipient.status in {
                    CampaignRecipientStatus.PENDING.value,
                    CampaignRecipientStatus.SENT.value,
                }:
                    campaign_recipient.status = CampaignRecipientStatus.DELIVERED.value
                    if not campaign_recipient.sent_at:
                        campaign_recipient.sent_at = event_created_at
            elif event_type == "email.sent":
                if campaign_recipient.status == CampaignRecipientStatus.PENDING.value:
                    campaign_recipient.status = CampaignRecipientStatus.SENT.value
                    campaign_recipient.sent_at = event_created_at
            elif event_type == "email.suppressed":
                campaign_recipient.status = CampaignRecipientStatus.SKIPPED.value
                campaign_recipient.error = email_log.error
            else:
                campaign_recipient.status = CampaignRecipientStatus.FAILED.value
                campaign_recipient.error = email_log.error

            campaign_service.recompute_campaign_run_aggregates(
                db,
                organization_id=email_log.organization_id,
                run_id=campaign_recipient.run_id,
                commit=False,
            )


def _downgrade_workflow_execution_for_delivery_failure(
    db: Session,
    *,
    email_log: EmailLog,
    event_type: str | None,
) -> None:
    """Downgrade linked workflow execution after terminal delivery failures."""
    if event_type not in _DELIVERY_FAILURE_EVENTS:
        return

    if not email_log.job_id:
        return

    from uuid import UUID

    from app.db.enums import JobType, WorkflowExecutionStatus
    from app.db.models import Job, WorkflowExecution

    job = (
        db.query(Job)
        .filter(
            Job.id == email_log.job_id,
            Job.organization_id == email_log.organization_id,
        )
        .first()
    )
    if not job or job.job_type != JobType.WORKFLOW_EMAIL.value:
        return

    payload = job.payload if isinstance(job.payload, dict) else {}
    execution_id_value = payload.get("workflow_execution_id")
    if not execution_id_value:
        return

    try:
        execution_id = UUID(str(execution_id_value))
    except (TypeError, ValueError):
        logger.warning(
            "Resend: invalid workflow_execution_id in workflow email job payload: job_id=%s",
            job.id,
        )
        return

    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.organization_id == email_log.organization_id,
        )
        .first()
    )
    if not execution:
        return

    if execution.status not in {
        WorkflowExecutionStatus.SUCCESS.value,
        WorkflowExecutionStatus.PARTIAL.value,
    }:
        return

    failure_kind = {
        "email.bounced": "bounced",
        "email.complained": "complaint",
        "email.failed": "failed",
        "email.suppressed": "suppressed",
    }[event_type]
    failure_message = f"Workflow email {failure_kind} via Resend webhook (email_log={email_log.id})"
    existing_error = (execution.error_message or "").strip()
    if not existing_error:
        execution.error_message = failure_message
    elif failure_kind not in existing_error.lower():
        execution.error_message = f"{existing_error}; {failure_message}"

    execution.status = WorkflowExecutionStatus.PARTIAL.value


def _log_surrogate_email_bounced_activity(
    db: Session,
    *,
    email_log: EmailLog,
) -> None:
    """Log a case activity row for bounced outbound emails."""
    if not email_log.surrogate_id:
        return

    from app.core.constants import SYSTEM_USER_ID
    from app.services import activity_service

    activity_service.log_email_bounced(
        db=db,
        surrogate_id=email_log.surrogate_id,
        organization_id=email_log.organization_id,
        actor_user_id=SYSTEM_USER_ID,
        email_log_id=email_log.id,
        subject=email_log.subject,
        provider="resend",
        reason="bounced",
        bounce_type=email_log.bounce_type,
    )


def _process_verified_payload(
    db: Session,
    *,
    event: ResendWebhookEvent,
    email_log: EmailLog,
    payload: dict,
) -> dict:
    """Project one durably accepted Resend event transactionally."""
    event_id = event.id
    organization_id = event.organization_id
    email_log_id = email_log.id

    locked_event = db.execute(
        select(ResendWebhookEvent)
        .where(
            ResendWebhookEvent.id == event_id,
            ResendWebhookEvent.organization_id == organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked_event is None:
        raise RuntimeError("Resend webhook event projection target is missing")

    from app.services import campaign_service

    campaign_service.lock_campaign_run_for_email_log(
        db,
        organization_id=organization_id,
        email_log_id=email_log_id,
    )

    locked_email_log = db.execute(
        select(EmailLog)
        .where(
            EmailLog.id == email_log_id,
            EmailLog.organization_id == organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked_email_log is None:
        raise RuntimeError("Resend email projection target is missing")
    if locked_event.email_log_id is not None and locked_event.email_log_id != locked_email_log.id:
        raise RuntimeError("Resend webhook event is already linked to another email")

    if locked_event.processed_at is not None:
        logger.info(
            "Resend webhook duplicate event: org=%s event_id=%s",
            locked_event.organization_id,
            locked_event.provider_event_id,
        )
        db.commit()
        return {"status": "ok"}

    event_type_value = payload.get("type")
    event_type = event_type_value if isinstance(event_type_value, str) else "unknown"
    data_value = payload.get("data")
    data = data_value if isinstance(data_value, dict) else {}
    event_created_at = _parse_event_created_at(payload.get("created_at"))

    _process_resend_event(
        db,
        email_log=locked_email_log,
        event_type=event_type,
        data=data,
        event_created_at=event_created_at,
    )
    locked_event.email_log_id = locked_email_log.id
    locked_event.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}


def _accept_or_process_verified_payload(
    db: Session,
    *,
    organization_id: UUID,
    email_log: EmailLog | None,
    payload: dict,
    headers: dict[str, str],
) -> dict:
    """Accept a signed event, then project now or enqueue later correlation."""
    provider_event_id = headers.get("svix-id", "")
    if not provider_event_id:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type_value = payload.get("type")
    event_type = event_type_value if isinstance(event_type_value, str) else "unknown"
    event, _inserted = _accept_verified_event(
        db,
        organization_id=organization_id,
        email_log=email_log,
        provider_event_id=provider_event_id,
        event_type=event_type,
        event_created_at=_parse_event_created_at(payload.get("created_at")),
        payload=payload,
    )

    if email_log is None:
        _enqueue_event_reconciliation(db, event)
        db.commit()
        return {"status": "ok"}

    return _process_verified_payload(
        db,
        event=event,
        email_log=email_log,
        payload=payload,
    )


def _organization_email_log_from_correlation_tags(
    db: Session,
    *,
    organization_id: UUID,
    email_id: str,
    data: dict,
) -> tuple[EmailLog | None, bool]:
    """Resolve a tenant email by signed tags before using legacy provider-id lookup."""
    tags_value = data.get("tags")
    tags = tags_value if isinstance(tags_value, dict) else {}
    has_correlation_tags = "organization_id" in tags or "email_log_id" in tags
    if not has_correlation_tags:
        return None, False

    try:
        tagged_organization_id = UUID(str(tags["organization_id"]))
        tagged_email_log_id = UUID(str(tags["email_log_id"]))
    except (KeyError, TypeError, ValueError):
        logger.warning("Resend webhook has invalid email correlation tags")
        return None, True
    if tagged_organization_id != organization_id:
        logger.warning("Resend webhook correlation tags do not match signed tenant")
        return None, True

    email_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == organization_id,
            EmailLog.id == tagged_email_log_id,
        )
        .one_or_none()
    )
    if email_log is None:
        return None, True
    if email_log.external_id not in {None, email_id}:
        logger.warning("Resend webhook correlation tags conflict with provider message id")
        return None, True
    if email_log.external_id is None:
        # A signed event can beat the provider-response commit. Bind the message
        # identity now so later webhook retries and delivery reconciliation agree.
        email_log.external_id = email_id
        db.flush()
    return email_log, True


class ResendWebhookHandler:
    async def handle(self, request: Request, db: Session, **kwargs) -> dict:
        """
        Receive Resend webhook events.

        Handles current Resend delivery and engagement lifecycle events.

        Security:
        - Webhook URL uses unique webhook_id per org
        - Verifies Svix signature before processing
        - Returns 503 for recoverable setup/send-commit races so Resend retries
        """
        webhook_id = kwargs.get("webhook_id")
        if not webhook_id:
            logger.warning("Resend webhook missing webhook_id")
            return {"status": "ok"}

        body = await request.body()

        # Check payload size
        if len(body) > settings.META_WEBHOOK_MAX_PAYLOAD_BYTES:
            logger.warning("Resend webhook payload too large")
            return {"status": "ok"}

        # 1. Lookup settings by webhook_id
        resend_settings = resend_settings_service.get_settings_by_webhook_id(db, webhook_id)
        if not resend_settings:
            logger.info("Resend webhook: unknown webhook_id")
            return {"status": "ok"}  # Don't reveal validity

        # 2. Verify signature BEFORE parsing
        if not resend_settings.webhook_secret_encrypted:
            logger.warning(
                "Resend webhook signing secret not configured for org=%s",
                resend_settings.organization_id,
            )
            raise HTTPException(status_code=503, detail="Webhook not configured")

        webhook_secret = resend_settings_service.decrypt_api_key(
            resend_settings.webhook_secret_encrypted
        )
        headers = {k.lower(): v for k, v in request.headers.items()}
        if not _verify_svix_signature(body, headers, webhook_secret):
            logger.warning(
                "Resend webhook invalid signature for org=%s",
                resend_settings.organization_id,
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # 3. Parse and process
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Resend webhook invalid JSON")
            return {"status": "ok"}

        if not isinstance(payload, dict):
            logger.warning("Resend webhook payload is not an object")
            return {"status": "ok"}

        data_value = payload.get("data")
        data = data_value if isinstance(data_value, dict) else {}
        email_id = data.get("email_id")

        if not email_id:
            logger.info("Resend webhook: no email_id in payload")
            return {"status": "ok"}

        email_log, correlation_tags_present = _organization_email_log_from_correlation_tags(
            db,
            organization_id=resend_settings.organization_id,
            email_id=email_id,
            data=data,
        )
        if not correlation_tags_present:
            # Legacy messages predate reserved correlation tags.
            email_log = (
                db.query(EmailLog)
                .filter(
                    EmailLog.organization_id == resend_settings.organization_id,
                    EmailLog.external_id == email_id,
                )
                .first()
            )

        return _accept_or_process_verified_payload(
            db,
            organization_id=resend_settings.organization_id,
            email_log=email_log,
            payload=payload,
            headers=headers,
        )


class PlatformResendWebhookHandler:
    async def handle(self, request: Request, db: Session, **kwargs) -> dict:
        """
        Receive Resend webhook events for platform/system emails.

        Uses PLATFORM_RESEND_WEBHOOK_SECRET for signature verification.
        """
        body = await request.body()

        # Check payload size
        if len(body) > settings.META_WEBHOOK_MAX_PAYLOAD_BYTES:
            logger.warning("Platform Resend webhook payload too large")
            return {"status": "ok"}

        secret = (settings.PLATFORM_RESEND_WEBHOOK_SECRET.get_secret_value() or "").strip()
        if not secret:
            logger.error("Platform Resend webhook secret not configured")
            raise HTTPException(status_code=503, detail="Webhook not configured")

        headers = {k.lower(): v for k, v in request.headers.items()}
        if not _verify_svix_signature(body, headers, secret):
            logger.warning("Platform Resend webhook invalid signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Parse payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Platform Resend webhook invalid JSON")
            return {"status": "ok"}

        if not isinstance(payload, dict):
            logger.warning("Platform Resend webhook payload is not an object")
            return {"status": "ok"}

        data_value = payload.get("data")
        data = data_value if isinstance(data_value, dict) else {}
        email_id = data.get("email_id")
        if not email_id:
            logger.info("Platform Resend webhook: no email_id in payload")
            return {"status": "ok"}

        tags_value = data.get("tags")
        tags = tags_value if isinstance(tags_value, dict) else {}
        try:
            organization_id = UUID(str(tags["organization_id"]))
            email_log_id = UUID(str(tags["email_log_id"]))
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Platform Resend webhook missing valid tenant correlation tags; "
                "acknowledging unsupported legacy event"
            )
            return {"status": "ok"}

        email_log = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == organization_id,
                EmailLog.id == email_log_id,
                EmailLog.external_id == email_id,
            )
            .first()
        )
        return _accept_or_process_verified_payload(
            db,
            organization_id=organization_id,
            email_log=email_log,
            payload=payload,
            headers=headers,
        )
