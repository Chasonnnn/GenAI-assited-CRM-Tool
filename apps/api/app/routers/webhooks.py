"""Webhooks router - external service integrations."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.db.enums import JobType
from app.db.models import Appointment, ZoomWebhookEvent
from app.services import job_service, meta_api, meta_page_service

# Rate limiting
from app.core.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/meta")
async def verify_meta_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification endpoint.

    When you configure the webhook in Meta, it sends a GET request
    with a challenge that must be echoed back as PLAIN TEXT (not JSON).
    """
    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return PlainTextResponse(challenge or "")

    logger.warning(f"Meta webhook verification failed: mode={mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Meta Lead Ads webhook.

    Security:
    - Validates X-Hub-Signature-256 HMAC (except in test mode)
    - Validates payload size
    - Validates page_id is mapped

    Processing:
    - Enqueues async jobs for lead fetching (idempotent via DB constraint)
    - Returns 200 fast before heavy DB work
    """
    # 1. Check payload size
    content_length = request.headers.get("content-length", "0")
    try:
        if int(content_length) > settings.META_WEBHOOK_MAX_PAYLOAD_BYTES:
            raise HTTPException(413, "Payload too large")
    except ValueError:
        pass

    # 2. Get raw body for signature verification
    body = await request.body()
    # Fallback size check in case Content-Length is missing/incorrect
    if len(body) > settings.META_WEBHOOK_MAX_PAYLOAD_BYTES:
        raise HTTPException(413, "Payload too large")
    signature = request.headers.get("X-Hub-Signature-256", "")

    # 3. Validate signature (skip in test mode)
    if not settings.META_TEST_MODE:
        if not signature:
            logger.warning("Meta webhook missing signature")
            raise HTTPException(403, "Missing signature")
        if not meta_api.verify_signature(body, signature):
            logger.warning("Meta webhook invalid signature")
            raise HTTPException(403, "Invalid signature")

    # 4. Parse payload
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    # 5. Validate object type
    if data.get("object") != "page":
        logger.warning(f"Meta webhook invalid object: {data.get('object')}")
        raise HTTPException(400, f"Invalid object: {data.get('object')}")

    # 6. Process entries
    jobs_created = 0
    jobs_skipped = 0

    for entry in data.get("entry", []):
        page_id = str(entry.get("id", ""))
        if not page_id:
            continue

        # Validate page_id is mapped to an org
        mapping = meta_page_service.get_active_mapping_by_page_id(db, page_id)

        if not mapping:
            logger.info(f"Meta webhook: unmapped page_id={page_id}")
            continue

        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue

            value = change.get("value", {})
            leadgen_id = value.get("leadgen_id")

            if not leadgen_id:
                logger.warning("Meta webhook: missing leadgen_id in change")
                continue

            # Idempotent job creation via DB unique constraint
            job_key = f"meta_lead_fetch:{page_id}:{leadgen_id}"

            try:
                job_service.schedule_job(
                    db=db,
                    org_id=mapping.organization_id,
                    job_type=JobType.META_LEAD_FETCH,
                    payload={
                        "leadgen_id": leadgen_id,
                        "page_id": page_id,
                    },
                    idempotency_key=job_key,
                )
                jobs_created += 1
                logger.info(f"Meta webhook: enqueued job for leadgen_id={leadgen_id}")
            except IntegrityError:
                db.rollback()
                jobs_skipped += 1
                logger.info(f"Meta webhook: duplicate job skipped for leadgen_id={leadgen_id}")

    return {
        "status": "ok",
        "jobs_enqueued": jobs_created,
        "jobs_skipped": jobs_skipped,
    }


# =============================================================================
# Dev/Test endpoint for simulating Meta webhook
# =============================================================================


@router.post("/meta/simulate", include_in_schema=False)
async def simulate_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Simulate a Meta webhook for testing.

    Only works in test mode. Requires X-Dev-Secret header.
    """
    if not settings.META_TEST_MODE:
        raise HTTPException(403, "Only available in test mode")

    dev_secret = request.headers.get("X-Dev-Secret", "")
    if dev_secret != settings.DEV_SECRET:
        raise HTTPException(403, "Invalid dev secret")

    # Create a mock webhook payload
    import uuid

    mock_leadgen_id = str(uuid.uuid4())

    # Find any active page mapping (or use mock)
    mapping = meta_page_service.get_first_active_mapping(db)

    page_id = mapping.page_id if mapping else "mock_page_456"
    org_id = mapping.organization_id if mapping else None

    if not org_id:
        raise HTTPException(400, "No active page mapping found. Create one first.")

    # Enqueue the job
    job_key = f"meta_lead_fetch:{page_id}:{mock_leadgen_id}"

    try:
        job = job_service.schedule_job(
            db=db,
            org_id=org_id,
            job_type=JobType.META_LEAD_FETCH,
            payload={
                "leadgen_id": mock_leadgen_id,
                "page_id": page_id,
            },
            idempotency_key=job_key,
        )

        return {
            "status": "ok",
            "job_id": str(job.id),
            "leadgen_id": mock_leadgen_id,
            "page_id": page_id,
            "message": "Job enqueued. Run worker to process.",
        }
    except IntegrityError:
        db.rollback()
        return {"status": "ok", "message": "Duplicate job already exists"}


# =============================================================================
# Zoom Webhooks
# =============================================================================


def _verify_zoom_webhook_signature(
    body: bytes,
    signature: str,
    timestamp: str,
    secret: str,
) -> bool:
    """
    Verify Zoom webhook signature.

    Zoom sends: v0:timestamp:body_string
    Then HMAC-SHA256 with webhook secret, compare to signature.
    """
    message = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected_signature = f"v0={expected}"
    return hmac.compare_digest(expected_signature, signature)


@router.post("/zoom")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def zoom_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Zoom webhook events.

    Handles:
    - endpoint.url_validation: Zoom verification challenge
    - meeting.started: Log meeting start timestamp
    - meeting.ended: Log meeting end timestamp

    Security:
    - Validates webhook signature using ZOOM_WEBHOOK_SECRET
    - Deduplicates events via ZoomWebhookEvent table
    """
    body = await request.body()

    # Handle URL validation challenge from Zoom
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    # URL validation event (during webhook setup)
    if data.get("event") == "endpoint.url_validation":
        plain_token = data.get("payload", {}).get("plainToken", "")
        if not plain_token:
            raise HTTPException(400, "Missing plainToken")

        # Encrypt the token with our webhook secret
        encrypted_token = hmac.new(
            settings.ZOOM_WEBHOOK_SECRET.encode("utf-8"),
            plain_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return JSONResponse(
            {
                "plainToken": plain_token,
                "encryptedToken": encrypted_token,
            }
        )

    # Verify signature for other events
    signature = request.headers.get("x-zm-signature", "")
    timestamp = request.headers.get("x-zm-request-timestamp", "")

    if not signature or not timestamp:
        logger.warning("Zoom webhook missing signature or timestamp")
        raise HTTPException(403, "Missing signature")

    if not settings.ZOOM_WEBHOOK_SECRET:
        logger.error("ZOOM_WEBHOOK_SECRET not configured")
        raise HTTPException(500, "Webhook not configured")

    if not _verify_zoom_webhook_signature(body, signature, timestamp, settings.ZOOM_WEBHOOK_SECRET):
        logger.warning("Zoom webhook invalid signature")
        raise HTTPException(403, "Invalid signature")

    # Extract event info
    event_type = data.get("event", "")
    payload = data.get("payload", {})
    event_id = data.get("event_ts", str(datetime.now(timezone.utc).timestamp()))

    # Meeting object from payload
    meeting_obj = payload.get("object", {})
    zoom_meeting_id = str(meeting_obj.get("id", ""))

    if not zoom_meeting_id:
        logger.warning(f"Zoom webhook missing meeting ID: {event_type}")
        return {"status": "ok", "message": "No meeting ID"}

    # Dedupe: check if we've already processed this event
    provider_event_id = f"{event_type}:{zoom_meeting_id}:{event_id}"

    try:
        webhook_event = ZoomWebhookEvent(
            provider_event_id=provider_event_id,
            event_type=event_type,
            zoom_meeting_id=zoom_meeting_id,
            payload=data,
        )
        db.add(webhook_event)
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(f"Zoom webhook duplicate event: {provider_event_id}")
        return {"status": "ok", "message": "Duplicate event"}

    # Find appointment by zoom_meeting_id
    appointment = (
        db.query(Appointment).filter(Appointment.zoom_meeting_id == zoom_meeting_id).first()
    )

    if not appointment:
        logger.info(f"Zoom webhook: no appointment for meeting {zoom_meeting_id}")
        db.commit()  # Commit the webhook event for audit
        return {"status": "ok", "message": "No matching appointment"}

    # Handle event types
    event_timestamp = datetime.now(timezone.utc)
    if event_type == "meeting.started":
        appointment.meeting_started_at = event_timestamp
        logger.info(f"Zoom meeting started: {zoom_meeting_id}, appointment {appointment.id}")

    elif event_type == "meeting.ended":
        appointment.meeting_ended_at = event_timestamp
        logger.info(f"Zoom meeting ended: {zoom_meeting_id}, appointment {appointment.id}")

    db.commit()

    return {"status": "ok", "event": event_type, "meeting_id": zoom_meeting_id}


# =============================================================================
# Resend Webhooks (Email Delivery Events)
# =============================================================================


def _verify_svix_signature(
    body: bytes,
    headers: dict,
    secret: str,
) -> bool:
    """
    Verify Resend webhook signature using Svix.

    Resend uses Svix for webhooks. The signature is in 'svix-signature' header.
    """
    import base64

    svix_id = headers.get("svix-id", "")
    svix_timestamp = headers.get("svix-timestamp", "")
    svix_signature = headers.get("svix-signature", "")

    if not svix_id or not svix_timestamp or not svix_signature:
        return False

    # Build the signed payload
    signed_payload = f"{svix_id}.{svix_timestamp}.{body.decode('utf-8')}"

    def _pad_b64(value: str) -> str:
        return value + "=" * (-len(value) % 4)

    # Decode the secret (Svix uses whsec_ + base64). If no whsec_ prefix,
    # treat the secret as raw bytes (matches our tests + backward compatibility).
    if secret.startswith("whsec_"):
        secret = secret[6:]  # Remove "whsec_" prefix
        secret_bytes = None
        for decoder in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                secret_bytes = decoder(_pad_b64(secret))
                break
            except Exception:
                continue
        if secret_bytes is None:
            secret_bytes = secret.encode("utf-8")
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


@router.post("/resend/{webhook_id}")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def resend_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
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
    from app.services import resend_settings_service, campaign_service

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
                "Resend webhook invalid signature for org=%s", resend_settings.organization_id
            )
            return {"status": "ok"}

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
    from app.db.models import EmailLog, CampaignRecipient, CampaignRun

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

        # Add to suppression list for hard bounces
        if email_log.bounce_type == "hard":
            campaign_service.add_to_suppression(
                db,
                resend_settings.organization_id,
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

        # Add to suppression list for complaints
        campaign_service.add_to_suppression(
            db,
            resend_settings.organization_id,
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

            run = (
                db.query(CampaignRun)
                .filter(CampaignRun.id == campaign_recipient.run_id)
                .first()
            )
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
                run.failed_count = (
                    db.query(CampaignRecipient)
                    .filter(
                        CampaignRecipient.run_id == run.id,
                        CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
                    )
                    .count()
                )

    db.commit()
    return {"status": "ok"}
