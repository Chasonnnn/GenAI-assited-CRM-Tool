"""Resend webhook handlers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailLog
from app.services import resend_settings_service

logger = logging.getLogger(__name__)


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


def _process_resend_event(
    db: Session,
    *,
    email_log: EmailLog,
    event_type: str | None,
    data: dict,
) -> None:
    from app.db.models import CampaignRecipient, CampaignRun
    from app.services import campaign_service

    now = datetime.now(timezone.utc)

    if event_type == "email.delivered":
        email_log.resend_status = "delivered"
        email_log.delivered_at = now
        if email_log.status != "sent":
            from app.db.enums import EmailStatus

            email_log.status = EmailStatus.SENT.value
        logger.info("Resend: email delivered for email_log=%s", email_log.id)

    elif event_type == "email.bounced":
        email_log.resend_status = "bounced"
        email_log.bounced_at = now
        bounce_data = data.get("bounce", {})
        email_log.bounce_type = bounce_data.get("type", "hard")
        from app.db.enums import EmailStatus

        email_log.status = EmailStatus.FAILED.value
        email_log.error = "bounced"
        _downgrade_workflow_execution_for_delivery_failure(
            db, email_log=email_log, event_type=event_type
        )
        _log_surrogate_email_bounced_activity(db, email_log=email_log)

        # Add to suppression list for hard bounces
        if email_log.bounce_type == "hard":
            campaign_service.add_to_suppression(
                db,
                email_log.organization_id,
                email_log.recipient_email,
                "bounced",
                source_type="email_log",
                source_id=email_log.id,
            )
            logger.info(
                "Resend: hard bounce, added to suppression: email_log=%s",
                email_log.id,
            )
        else:
            logger.info("Resend: soft bounce for email_log=%s", email_log.id)

    elif event_type == "email.complained":
        email_log.resend_status = "complained"
        email_log.complained_at = now
        from app.db.enums import EmailStatus

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
        if not email_log.opened_at:
            email_log.opened_at = now
        # Update campaign recipient if linked
        campaign_recipient = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.external_message_id == str(email_log.id))
            .first()
        )
        if campaign_recipient:
            if not campaign_recipient.opened_at:
                campaign_recipient.opened_at = now
                # Update run opened_count
                run = (
                    db.query(CampaignRun)
                    .filter(CampaignRun.id == campaign_recipient.run_id)
                    .first()
                )
                if run:
                    run.opened_count = (
                        db.query(CampaignRecipient)
                        .filter(
                            CampaignRecipient.run_id == run.id,
                            CampaignRecipient.opened_at.isnot(None),
                        )
                        .count()
                    )
            campaign_recipient.open_count = (campaign_recipient.open_count or 0) + 1
            logger.info("Resend: email opened for campaign_recipient=%s", campaign_recipient.id)

    elif event_type == "email.clicked":
        email_log.click_count = (email_log.click_count or 0) + 1
        if not email_log.clicked_at:
            email_log.clicked_at = now
        # Update campaign recipient if linked
        campaign_recipient = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.external_message_id == str(email_log.id))
            .first()
        )
        if campaign_recipient:
            if not campaign_recipient.clicked_at:
                campaign_recipient.clicked_at = now
                # Update run clicked_count
                run = (
                    db.query(CampaignRun)
                    .filter(CampaignRun.id == campaign_recipient.run_id)
                    .first()
                )
                if run:
                    run.clicked_count = (
                        db.query(CampaignRecipient)
                        .filter(
                            CampaignRecipient.run_id == run.id,
                            CampaignRecipient.clicked_at.isnot(None),
                        )
                        .count()
                    )
            campaign_recipient.click_count = (campaign_recipient.click_count or 0) + 1
            logger.info("Resend: link clicked for campaign_recipient=%s", campaign_recipient.id)

    # Update campaign recipient status for delivery failures/success
    if event_type in {"email.delivered", "email.bounced", "email.complained"}:
        from app.db.enums import CampaignRecipientStatus

        campaign_recipient = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.external_message_id == str(email_log.id))
            .first()
        )
        if campaign_recipient:
            if event_type == "email.delivered":
                if campaign_recipient.status != CampaignRecipientStatus.DELIVERED.value:
                    campaign_recipient.status = CampaignRecipientStatus.DELIVERED.value
                    if not campaign_recipient.sent_at:
                        campaign_recipient.sent_at = now
            else:
                campaign_recipient.status = CampaignRecipientStatus.FAILED.value
                campaign_recipient.error = (
                    "bounced" if event_type == "email.bounced" else "complaint"
                )

            # Ensure status updates are persisted before aggregate counts (autoflush is disabled).
            db.flush()

            run = db.query(CampaignRun).filter(CampaignRun.id == campaign_recipient.run_id).first()
            if run:
                run.sent_count = (
                    db.query(CampaignRecipient)
                    .filter(
                        CampaignRecipient.run_id == run.id,
                        CampaignRecipient.status.in_(
                            [
                                CampaignRecipientStatus.SENT.value,
                                CampaignRecipientStatus.DELIVERED.value,
                            ]
                        ),
                    )
                    .count()
                )
                run.delivered_count = (
                    db.query(CampaignRecipient)
                    .filter(
                        CampaignRecipient.run_id == run.id,
                        CampaignRecipient.status == CampaignRecipientStatus.DELIVERED.value,
                    )
                    .count()
                )
                run.failed_count = (
                    db.query(CampaignRecipient)
                    .filter(
                        CampaignRecipient.run_id == run.id,
                        CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
                    )
                    .count()
                )


def _downgrade_workflow_execution_for_delivery_failure(
    db: Session,
    *,
    email_log: EmailLog,
    event_type: str | None,
) -> None:
    """Downgrade linked workflow execution after bounce/complaint events."""
    if event_type not in {"email.bounced", "email.complained"}:
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

    failure_kind = "bounced" if event_type == "email.bounced" else "complaint"
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


class ResendWebhookHandler:
    async def handle(self, request: Request, db: Session, **kwargs) -> dict:
        """
        Receive Resend webhook events.

        Handles email delivery events:
        - email.delivered: Email was delivered to recipient
        - email.bounced: Email bounced (hard or soft)
        - email.complained: Recipient marked as spam
        - email.opened: Recipient opened the email
        - email.clicked: Recipient clicked a link

        Security:
        - Webhook URL uses unique webhook_id per org
        - Verifies Svix signature before processing
        - Always returns 200 to avoid leaking information
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
        if resend_settings.webhook_secret_encrypted:
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
        else:
            # Accept webhook without signature verification if the org hasn't configured the
            # Resend signing secret yet. The unguessable webhook_id in the URL still provides
            # a basic level of protection.
            logger.warning(
                "Resend webhook signing secret not configured for org=%s; skipping signature verification",
                resend_settings.organization_id,
            )

        # 3. Parse and process
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Resend webhook invalid JSON")
            return {"status": "ok"}

        event_type = payload.get("type")
        data = payload.get("data", {})
        email_id = data.get("email_id")

        if not email_id:
            logger.info("Resend webhook: no email_id in payload")
            return {"status": "ok"}

        # Find the EmailLog by external_id
        email_log = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == resend_settings.organization_id,
                EmailLog.external_id == email_id,
            )
            .first()
        )

        if not email_log:
            logger.info("Resend webhook: no EmailLog found for email_id=%s", email_id)
            return {"status": "ok"}

        # 4. Process events
        _process_resend_event(db, email_log=email_log, event_type=event_type, data=data)

        db.commit()
        return {"status": "ok"}


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

        secret = (settings.PLATFORM_RESEND_WEBHOOK_SECRET or "").strip()
        if not secret:
            logger.error("Platform Resend webhook secret not configured")
            raise HTTPException(status_code=500, detail="Webhook not configured")

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

        event_type = payload.get("type")
        data = payload.get("data", {})
        email_id = data.get("email_id")
        if not email_id:
            logger.info("Platform Resend webhook: no email_id in payload")
            return {"status": "ok"}

        email_log = db.query(EmailLog).filter(EmailLog.external_id == email_id).first()
        if not email_log:
            logger.info("Platform Resend webhook: no EmailLog found for email_id=%s", email_id)
            return {"status": "ok"}

        _process_resend_event(db, email_log=email_log, event_type=event_type, data=data)
        db.commit()
        return {"status": "ok"}
