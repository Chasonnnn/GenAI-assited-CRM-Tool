"""
Background worker for processing scheduled jobs.

Usage:
    python -m app.worker

The worker polls for pending jobs and processes them.
For production, run this as a separate process (e.g., systemd service, Docker container).
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import UUID

from app.core.config import settings
from app.core.gcp_monitoring import report_exception, setup_gcp_monitoring
from app.core.structured_logging import build_log_context
from app.db.session import SessionLocal
from app.db.models import EmailLog
from app.db.enums import JobType, JobStatus
from app.services import job_service, email_service

monitoring = setup_gcp_monitoring(f"{settings.GCP_SERVICE_NAME}-worker")

# Configure logging (fallback when Cloud Logging isn't enabled)
if not monitoring.logging_enabled:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
logger = logging.getLogger(__name__)

# Email sending configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@example.com")

# Worker configuration
POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL", "10"))
BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "10"))
SESSION_CLEANUP_INTERVAL_SECONDS = int(os.getenv("SESSION_CLEANUP_INTERVAL_SECONDS", "3600"))


def parse_worker_job_types(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    if not raw.strip():
        return None
    allowed_values = {job.value for job in JobType}
    values: list[str] = []
    seen = set()
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        token_norm = token.lower()
        resolved = None
        if token_norm in allowed_values:
            resolved = token_norm
        else:
            try:
                resolved = JobType[token.upper()].value
            except KeyError:
                resolved = None
        if resolved and resolved not in seen:
            seen.add(resolved)
            values.append(resolved)
    return values if values else []


WORKER_JOB_TYPES = parse_worker_job_types(os.getenv("WORKER_JOB_TYPES"))


def _mask_email(email: str | None) -> str:
    if not email:
        return ""
    try:
        from app.services import audit_service

        return audit_service.hash_email(email)
    except Exception:
        local, _, domain = email.partition("@")
        prefix = local[:3] if local else ""
        return f"{prefix}...@{domain}" if domain else f"{prefix}..."


def _safe_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _ensure_attachment_scanner_available() -> None:
    if settings.ATTACHMENT_SCAN_ENABLED and not settings.is_dev:
        from app.jobs.scan_attachment import get_available_scanner

        scanner = get_available_scanner()
        if not scanner:
            raise RuntimeError(
                "ATTACHMENT_SCAN_ENABLED is true but no ClamAV scanner was found "
                "(expected clamdscan or clamscan in PATH)."
            )
        logger.info("Attachment scanning enabled; using %s", scanner)


async def send_email_async(email_log: EmailLog) -> None:
    """
    Send an email using Resend API.

    If RESEND_API_KEY is not set, logs the email instead of sending.
    """
    if not RESEND_API_KEY:
        logger.info("[DRY RUN] Email send skipped for email_log=%s", email_log.id)
        return

    # In production, use Resend or another email provider
    # For now, we'll just import and use resend if available
    try:
        import resend

        resend.api_key = RESEND_API_KEY

        result = resend.Emails.send(
            {
                "from": EMAIL_FROM,
                "to": [email_log.recipient_email],
                "subject": email_log.subject,
                "html": email_log.body,
            }
        )
        logger.info(
            "Email sent for email_log=%s recipient=%s message_id=%s",
            email_log.id,
            _mask_email(email_log.recipient_email),
            result.get("id"),
        )
    except ImportError:
        logger.warning("resend package not installed, skipping email send")
        raise Exception("resend package not installed")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


async def process_job(db, job) -> None:
    """Process a single job based on its type."""
    logger.info(f"Processing job {job.id} (type={job.job_type}, attempt={job.attempts})")

    if job.job_type == JobType.SEND_EMAIL.value:
        email_log_id = job.payload.get("email_log_id")
        if not email_log_id:
            raise Exception("Missing email_log_id in job payload")

        email_log = db.query(EmailLog).filter(EmailLog.id == UUID(email_log_id)).first()
        if not email_log:
            raise Exception(f"EmailLog {email_log_id} not found")

        await send_email_async(email_log)
        email_service.mark_email_sent(db, email_log)

    elif job.job_type == JobType.REMINDER.value:
        # Process reminder - create notification and/or send email
        logger.info("Processing reminder job %s", job.id)
        payload = job.payload or {}

        # Create in-app notification if user_id provided
        if payload.get("user_id") and payload.get("message"):
            from app.db.models import Notification

            notification = Notification(
                organization_id=job.organization_id,
                user_id=payload["user_id"],
                title=payload.get("title", "Reminder"),
                message=payload["message"],
                notification_type=payload.get("type", "task_due"),
                entity_type=payload.get("entity_type"),
                entity_id=payload.get("entity_id"),
            )
            db.add(notification)
            db.commit()

        # Optionally send reminder email
        if payload.get("send_email") and payload.get("user_id"):
            from app.db.models import User

            user = db.query(User).filter(User.id == payload["user_id"]).first()
            if user and user.email:
                email_service.send_reminder_email(
                    db=db,
                    org_id=job.organization_id,
                    to_email=user.email,
                    subject=payload.get("title", "Reminder"),
                    message=payload["message"],
                )

    elif job.job_type == JobType.WEBHOOK_RETRY.value:
        # Retry failed webhook delivery
        logger.info("Processing webhook retry job %s", job.id)
        payload = job.payload or {}

        # Extract webhook details
        webhook_url = payload.get("url")
        webhook_data = payload.get("data")
        webhook_headers = payload.get("headers", {})

        if webhook_url and webhook_data:
            import httpx

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        webhook_url, json=webhook_data, headers=webhook_headers
                    )
                    response.raise_for_status()
                    logger.info("Webhook retry successful: %s", _safe_url(webhook_url))
            except Exception as e:
                logger.error(
                    "Webhook retry failed: %s (%s)",
                    _safe_url(webhook_url),
                    type(e).__name__,
                )
                raise  # Will trigger job retry mechanism
        else:
            logger.warning("Invalid webhook retry payload: missing url or data")

    elif job.job_type == JobType.NOTIFICATION.value:
        # Process notification - create in-app notification record
        logger.info("Processing notification job %s", job.id)
        payload = job.payload or {}

        if payload.get("user_id") and payload.get("message"):
            from app.db.models import Notification

            notification = Notification(
                organization_id=job.organization_id,
                user_id=payload["user_id"],
                title=payload.get("title", "Notification"),
                message=payload["message"],
                notification_type=payload.get("type", "general"),
                entity_type=payload.get("entity_type"),
                entity_id=payload.get("entity_id"),
            )
            db.add(notification)
            db.commit()
            logger.info(f"Created notification for user {payload['user_id']}")

    elif job.job_type == JobType.META_LEAD_FETCH.value:
        await process_meta_lead_fetch(db, job)

    elif job.job_type == JobType.META_CAPI_EVENT.value:
        await process_meta_capi_event(db, job)

    elif job.job_type == JobType.WORKFLOW_EMAIL.value:
        await process_workflow_email(db, job)

    elif job.job_type == JobType.WORKFLOW_SWEEP.value:
        await process_workflow_sweep(db, job)

    elif job.job_type == JobType.CSV_IMPORT.value:
        await process_csv_import(db, job)

    elif job.job_type == JobType.EXPORT_GENERATION.value:
        await process_export_generation(db, job)

    elif job.job_type == JobType.ADMIN_EXPORT.value:
        await process_admin_export(db, job)

    elif job.job_type == JobType.DATA_PURGE.value:
        await process_data_purge(db, job)

    elif job.job_type == JobType.CAMPAIGN_SEND.value:
        await process_campaign_send(db, job)

    elif job.job_type == JobType.AI_CHAT.value:
        await process_ai_chat(db, job)

    elif job.job_type == JobType.INTERVIEW_TRANSCRIPTION.value:
        await process_interview_transcription(db, job)

    elif job.job_type == JobType.ATTACHMENT_SCAN.value:
        attachment_id = job.payload.get("attachment_id")
        if not attachment_id:
            raise Exception("Missing attachment_id in job payload")
        from app.jobs.scan_attachment import scan_attachment_job

        scan_attachment_job(UUID(attachment_id))

    elif job.job_type == JobType.WORKFLOW_APPROVAL_EXPIRY.value:
        await process_workflow_approval_expiry(db, job)

    elif job.job_type == JobType.WORKFLOW_RESUME.value:
        await process_workflow_resume(db, job)

    elif job.job_type == JobType.META_HIERARCHY_SYNC.value:
        await process_meta_hierarchy_sync(db, job)

    elif job.job_type == JobType.META_SPEND_SYNC.value:
        await process_meta_spend_sync(db, job)

    elif job.job_type == JobType.META_FORM_SYNC.value:
        await process_meta_form_sync(db, job)

    else:
        raise Exception(f"Unknown job type: {job.job_type}")


def _resolve_integration_keys(db, job, integration_type) -> list[str]:
    from app.db.enums import IntegrationType

    payload = job.payload or {}
    keys: list[str] = []

    if integration_type in (
        IntegrationType.META_HIERARCHY,
        IntegrationType.META_SPEND,
    ):
        ad_account_id = payload.get("ad_account_id")
        if ad_account_id:
            try:
                ad_account_uuid = UUID(ad_account_id)
            except (TypeError, ValueError):
                keys.append(str(ad_account_id))
            else:
                from app.db.models import MetaAdAccount

                ad_account = (
                    db.query(MetaAdAccount).filter(MetaAdAccount.id == ad_account_uuid).first()
                )
                if ad_account and ad_account.ad_account_external_id:
                    keys.append(ad_account.ad_account_external_id)
                else:
                    keys.append(str(ad_account_uuid))

    elif integration_type == IntegrationType.META_FORMS:
        page_id = payload.get("page_id") or payload.get("meta_page_id")
        if page_id:
            keys.append(str(page_id))
        page_ids = payload.get("page_ids")
        if isinstance(page_ids, list):
            keys.extend(str(page_id) for page_id in page_ids if page_id)

    else:
        page_id = payload.get("page_id") or payload.get("meta_page_id")
        if page_id:
            keys.append(str(page_id))

    # De-dupe while preserving order
    return list(dict.fromkeys(keys))


def _record_job_success(db, job) -> None:
    """Record successful job for integration health."""
    from app.services import ops_service
    from app.db.enums import IntegrationType

    # Map job types to integration types
    job_to_integration = {
        JobType.META_LEAD_FETCH.value: IntegrationType.META_LEADS,
        JobType.META_CAPI_EVENT.value: IntegrationType.META_CAPI,
        JobType.META_HIERARCHY_SYNC.value: IntegrationType.META_HIERARCHY,
        JobType.META_SPEND_SYNC.value: IntegrationType.META_SPEND,
        JobType.META_FORM_SYNC.value: IntegrationType.META_FORMS,
    }

    integration_type = job_to_integration.get(job.job_type)
    if integration_type and job.organization_id:
        try:
            keys = _resolve_integration_keys(db, job, integration_type)
            if not keys:
                ops_service.record_success(
                    db=db,
                    org_id=job.organization_id,
                    integration_type=integration_type,
                    integration_key=None,
                )
            else:
                for key in keys:
                    ops_service.record_success(
                        db=db,
                        org_id=job.organization_id,
                        integration_type=integration_type,
                        integration_key=key,
                    )
        except Exception as e:
            logger.warning(f"Failed to record job success: {e}")


async def process_interview_transcription(db, job) -> None:
    """
    Process interview transcription job.

    Payload:
      - interview_attachment_id
      - language (optional)
      - prompt (optional)
      - requested_by_user_id (optional)
    """
    from sqlalchemy.orm import joinedload

    from app.db.enums import NotificationType
    from app.db.models import CaseInterview, InterviewAttachment
    from app.services import notification_service, transcription_service

    payload = job.payload or {}
    link_id = payload.get("interview_attachment_id")
    if not link_id:
        raise Exception("Missing interview_attachment_id in job payload")

    link = (
        db.query(InterviewAttachment)
        .options(
            joinedload(InterviewAttachment.attachment),
            joinedload(InterviewAttachment.interview).joinedload(CaseInterview.case),
        )
        .filter(
            InterviewAttachment.id == UUID(link_id),
            InterviewAttachment.organization_id == job.organization_id,
        )
        .first()
    )
    if not link:
        raise Exception(f"InterviewAttachment {link_id} not found")

    language = payload.get("language") or "en"
    prompt = payload.get("prompt")
    requested_by = payload.get("requested_by_user_id")
    requested_by_user_id = UUID(requested_by) if requested_by else None

    await transcription_service.request_transcription(
        db=db,
        interview_attachment=link,
        language=language,
        prompt=prompt,
        requested_by_user_id=requested_by_user_id,
    )

    if requested_by_user_id and link.interview:
        interview_date = link.interview.conducted_at.strftime("%b %d, %Y")
        notification_service.create_notification(
            db=db,
            org_id=job.organization_id,
            user_id=requested_by_user_id,
            type=NotificationType.INTERVIEW_TRANSCRIPTION_COMPLETED,
            title="Interview transcription ready",
            body=f"Transcription completed for interview on {interview_date}.",
            entity_type="case",
            entity_id=link.interview.surrogate_id,
            dedupe_key=f"interview_transcription_completed:{job.id}",
            dedupe_window_hours=None,
        )


def _record_job_failure(db, job, error_msg: str, exception: Exception | None = None) -> None:
    """Record failed job for integration health and create alert if final failure."""
    from app.services import ops_service, alert_service
    from app.db.enums import IntegrationType, AlertType, AlertSeverity

    if not job.organization_id:
        return

    try:
        # Map job types to integration types (for health tracking)
        job_to_integration = {
            JobType.META_LEAD_FETCH.value: IntegrationType.META_LEADS,
            JobType.META_CAPI_EVENT.value: IntegrationType.META_CAPI,
            JobType.META_HIERARCHY_SYNC.value: IntegrationType.META_HIERARCHY,
            JobType.META_SPEND_SYNC.value: IntegrationType.META_SPEND,
            JobType.META_FORM_SYNC.value: IntegrationType.META_FORMS,
        }

        integration_keys: list[str] = []

        # Record error in integration health (only for mapped types)
        integration_type = job_to_integration.get(job.job_type)
        if integration_type:
            integration_keys = _resolve_integration_keys(db, job, integration_type)
            if not integration_keys:
                ops_service.record_error(
                    db=db,
                    org_id=job.organization_id,
                    integration_type=integration_type,
                    error_message=error_msg,
                    integration_key=None,
                )
            else:
                for key in integration_keys:
                    ops_service.record_error(
                        db=db,
                        org_id=job.organization_id,
                        integration_type=integration_type,
                        error_message=error_msg,
                        integration_key=key,
                    )

        # Create alert if this is the final failure (max attempts reached)
        if job.attempts >= job.max_attempts:
            # Map to alert types
            alert_type_map = {
                JobType.META_LEAD_FETCH.value: AlertType.META_FETCH_FAILED,
                JobType.META_CAPI_EVENT.value: AlertType.META_API_ERROR,
                JobType.SEND_EMAIL.value: AlertType.EMAIL_SEND_FAILED,
                JobType.CAMPAIGN_SEND.value: AlertType.EMAIL_SEND_FAILED,
                JobType.WORKFLOW_EMAIL.value: AlertType.EMAIL_SEND_FAILED,
                JobType.WEBHOOK_RETRY.value: AlertType.WEBHOOK_DELIVERY_FAILED,
                JobType.AI_CHAT.value: AlertType.AI_PROVIDER_ERROR,
                JobType.INTERVIEW_TRANSCRIPTION.value: AlertType.TRANSCRIPTION_FAILED,
            }
            alert_type = alert_type_map.get(job.job_type, AlertType.WORKER_JOB_FAILED)

            # Use actual exception class name for fingerprinting
            error_class = type(exception).__name__ if exception else "UnknownError"

            alert_service.create_or_update_alert(
                db=db,
                org_id=job.organization_id,
                alert_type=alert_type,
                severity=AlertSeverity.ERROR,
                title=f"{job.job_type} failed after {job.attempts} attempts",
                message=error_msg[:500],
                integration_key=integration_keys[0] if integration_keys else None,
                error_class=error_class,
            )
    except Exception as e:
        logger.warning(f"Failed to record job failure: {e}")


async def process_meta_lead_fetch(db, job) -> None:
    """
    Process a Meta Lead Ads fetch job.

    1. Get page mapping and decrypt token
    2. Fetch lead details from Meta API
    3. Normalize field data
    4. Store in meta_leads table
    5. Update status on success/failure
    """
    from app.db.models import MetaPageMapping, MetaLead
    from app.core.encryption import decrypt_token
    from app.services import meta_api, meta_lead_service

    leadgen_id = job.payload.get("leadgen_id")
    page_id = job.payload.get("page_id")

    if not leadgen_id or not page_id:
        raise Exception("Missing leadgen_id or page_id in job payload")

    # Get page mapping
    mapping = (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.page_id == page_id,
            MetaPageMapping.is_active.is_(True),
        )
        .first()
    )

    if not mapping:
        raise Exception(f"No active mapping for page {page_id}")

    # Decrypt access token
    try:
        access_token = (
            decrypt_token(mapping.access_token_encrypted) if mapping.access_token_encrypted else ""
        )
    except Exception as e:
        mapping.last_error = f"Token decryption failed: {str(e)[:100]}"
        mapping.last_error_at = datetime.now(timezone.utc)
        db.commit()
        raise Exception(f"Token decryption failed: {e}")

    # Fetch lead from Meta API
    lead_data, error = await meta_api.fetch_lead_details(leadgen_id, access_token)

    if error:
        # Update mapping with error
        mapping.last_error = error
        mapping.last_error_at = datetime.now(timezone.utc)
        db.commit()

        # Check if we have an existing meta_lead to update
        existing = (
            db.query(MetaLead)
            .filter(
                MetaLead.organization_id == mapping.organization_id,
                MetaLead.meta_lead_id == leadgen_id,
            )
            .first()
        )
        if existing:
            existing.status = "fetch_failed"
            existing.fetch_error = error
            db.commit()

        raise Exception(error)

    # Normalize field data (scalars for conversion)
    field_data = meta_api.normalize_field_data(lead_data.get("field_data", []))

    # Extract raw field data preserving multi-select arrays (for form analysis)
    field_data_raw = meta_api.extract_field_data_raw(lead_data.get("field_data", []))

    # Add ad_id for campaign tracking (stored in field_data for conversion)
    if lead_data.get("ad_id"):
        field_data["meta_ad_id"] = lead_data["ad_id"]
        field_data_raw["meta_ad_id"] = lead_data["ad_id"]

    # Parse Meta timestamp
    meta_created_time = meta_api.parse_meta_timestamp(lead_data.get("created_time"))

    # Store meta lead (handles dedupe)
    meta_lead, store_error = meta_lead_service.store_meta_lead(
        db=db,
        org_id=mapping.organization_id,
        meta_lead_id=leadgen_id,
        field_data=field_data,
        field_data_raw=field_data_raw,
        raw_payload=None,  # PII minimization - don't store raw
        meta_form_id=lead_data.get("form_id"),
        meta_page_id=page_id,
        meta_created_time=meta_created_time,
    )

    if store_error:
        raise Exception(store_error)

    # Update success tracking (even for idempotent re-stores)
    mapping.last_success_at = datetime.now(timezone.utc)
    mapping.last_error = None
    db.commit()

    logger.info(f"Meta lead {leadgen_id} stored successfully for org {mapping.organization_id}")

    # Auto-convert to case so it appears in Cases list immediately
    if meta_lead.is_converted:
        meta_lead.status = "converted"
        db.commit()
        return

    meta_lead.status = "stored"
    db.commit()

    case, convert_error = meta_lead_service.convert_to_case(
        db=db,
        meta_lead=meta_lead,
        user_id=None,  # No assignee - managers can bulk-assign later
    )

    if convert_error:
        logger.warning(f"Meta lead auto-conversion failed: {convert_error}")
        meta_lead.status = "convert_failed"
        db.commit()
    else:
        meta_lead.status = "converted"
        db.commit()
        logger.info(f"Meta lead {leadgen_id} auto-converted to case {case.surrogate_number}")


async def process_meta_capi_event(db, job) -> None:
    """
    Process a Meta CAPI conversion event job.

    Payload:
      - meta_lead_id (leadgen id)
      - meta_ad_external_id (for resolving ad account)
      - surrogate_status
      - email, phone (optional)
      - meta_page_id (optional, unused - kept for backward compatibility)

    Ad account resolution:
      meta_ad_external_id → MetaAd → MetaAdAccount
      Uses per-account CAPI config (pixel_id, capi_token_encrypted, capi_enabled).
      Skips if no ad account found or CAPI is disabled for that account.
    """
    from app.db.models import MetaAd, MetaAdAccount
    from app.services import meta_capi

    payload = job.payload or {}
    meta_lead_id = payload.get("meta_lead_id")
    meta_ad_external_id = payload.get("meta_ad_external_id")
    surrogate_status = payload.get("surrogate_status")
    email = payload.get("email")
    phone = payload.get("phone")

    if not meta_lead_id or not surrogate_status:
        raise Exception("Missing meta_lead_id or surrogate_status in job payload")

    # Resolve ad account chain: meta_ad_external_id → MetaAd → MetaAdAccount
    ad_account = None
    if meta_ad_external_id:
        meta_ad = (
            db.query(MetaAd)
            .filter(
                MetaAd.organization_id == job.organization_id,
                MetaAd.ad_external_id == meta_ad_external_id,
            )
            .first()
        )
        if meta_ad:
            ad_account = (
                db.query(MetaAdAccount)
                .filter(
                    MetaAdAccount.id == meta_ad.ad_account_id,
                    MetaAdAccount.is_active.is_(True),
                )
                .first()
            )

    # Skip if no ad account or CAPI not enabled for this account
    if not ad_account:
        logger.info(
            f"Skipping CAPI for lead {meta_lead_id}: no ad account found "
            f"(ad_external_id={meta_ad_external_id})"
        )
        return

    if not ad_account.capi_enabled:
        logger.info(
            f"Skipping CAPI for lead {meta_lead_id}: CAPI disabled for ad account "
            f"{ad_account.ad_account_external_id}"
        )
        return

    if not ad_account.pixel_id:
        logger.warning(
            f"Skipping CAPI for lead {meta_lead_id}: no pixel_id configured for ad account "
            f"{ad_account.ad_account_external_id}"
        )
        return

    meta_status = meta_capi.map_surrogate_status_to_meta_status(str(surrogate_status))
    if not meta_status:
        raise Exception(f"Unsupported case status for Meta CAPI: {surrogate_status}")

    success, error = await meta_capi.send_status_event_for_account(
        meta_lead_id=str(meta_lead_id),
        ad_account=ad_account,
        surrogate_status=str(surrogate_status),
        meta_status=meta_status,
        email=str(email) if email else None,
        phone=str(phone) if phone else None,
    )

    if not success:
        # Record error on ad account for observability
        ad_account.last_error = f"CAPI: {error}"
        ad_account.last_error_at = datetime.now(timezone.utc)
        db.commit()
        raise Exception(error or "Meta CAPI failed")


async def worker_loop() -> None:
    """Main worker loop - polls for and processes pending jobs."""
    if WORKER_JOB_TYPES is None:
        job_types_display = "all"
    elif WORKER_JOB_TYPES:
        job_types_display = ",".join(WORKER_JOB_TYPES)
    else:
        job_types_display = "none"
    logger.info(
        "Worker starting (poll interval: %ss, batch size: %s, job types: %s)",
        POLL_INTERVAL_SECONDS,
        BATCH_SIZE,
        job_types_display,
    )

    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set - emails will be logged but not sent")

    last_session_cleanup = datetime.min.replace(tzinfo=timezone.utc)

    while True:
        with SessionLocal() as db:
            try:
                now = datetime.now(timezone.utc)
                if now - last_session_cleanup >= timedelta(
                    seconds=SESSION_CLEANUP_INTERVAL_SECONDS
                ):
                    try:
                        from app.services import session_service

                        deleted = session_service.cleanup_all_expired_sessions(db)
                        if deleted:
                            logger.info("Cleaned up %d expired sessions", deleted)
                    except Exception as exc:
                        logger.warning("Session cleanup failed: %s", exc)
                    last_session_cleanup = now

                jobs = job_service.claim_pending_jobs(
                    db,
                    limit=BATCH_SIZE,
                    job_types=WORKER_JOB_TYPES,
                )

                if jobs:
                    logger.info(f"Found {len(jobs)} pending jobs")

                for job in jobs:
                    try:
                        await process_job(db, job)
                        job_service.mark_job_completed(db, job)
                        logger.info(f"Job {job.id} completed successfully")

                        # Record success for integration health (Meta jobs)
                        _record_job_success(db, job)

                    except Exception as e:
                        error_msg = str(e)
                        job_service.mark_job_failed(db, job, error_msg)
                        logger.error("Job %s failed: %s", job.id, type(e).__name__)

                        # Record failure for integration health
                        _record_job_failure(db, job, error_msg, exception=e)

                        if job.job_type == JobType.AI_CHAT.value and job.status == JobStatus.FAILED.value:
                            payload = job.payload or {}
                            if "message" in payload or "message_encrypted" in payload:
                                payload.pop("message", None)
                                payload.pop("message_encrypted", None)
                                job.payload = payload
                                db.commit()

                        # Also mark email as failed if applicable
                        if job.job_type == JobType.SEND_EMAIL.value:
                            email_log_id = job.payload.get("email_log_id")
                            if email_log_id:
                                email_log = (
                                    db.query(EmailLog)
                                    .filter(EmailLog.id == UUID(email_log_id))
                                    .first()
                                )
                                if email_log:
                                    email_service.mark_email_failed(db, email_log, error_msg)

            except Exception as e:
                logger.error(f"Error in worker loop: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# =============================================================================
# Workflow Job Handlers
# =============================================================================


async def process_workflow_email(db, job) -> None:
    """
    Process a WORKFLOW_EMAIL job - send email triggered by workflow action.

    Payload:
        - template_id: UUID of email template
        - surrogate_id: UUID of case (for variable resolution)
        - recipient_email: Target email address
        - variables: Dict of resolved template variables
    """
    from app.db.models import EmailTemplate, EmailLog
    from app.services import email_service

    template_id = job.payload.get("template_id")
    surrogate_id = job.payload.get("surrogate_id")
    recipient_email = job.payload.get("recipient_email")
    variables = job.payload.get("variables", {})

    if not template_id or not recipient_email:
        raise Exception("Missing template_id or recipient_email in workflow email job")

    # Get template
    template = db.query(EmailTemplate).filter(EmailTemplate.id == UUID(template_id)).first()
    if not template:
        raise Exception(f"Email template {template_id} not found")

    # Resolve subject and body with variables
    subject = template.subject
    body = template.body
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        subject = subject.replace(placeholder, str(value) if value else "")
        body = body.replace(placeholder, str(value) if value else "")

    # Create email log
    email_log = EmailLog(
        organization_id=job.organization_id,
        job_id=job.id,
        template_id=template.id,
        surrogate_id=UUID(surrogate_id) if surrogate_id else None,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        status="pending",
    )
    db.add(email_log)
    db.commit()

    # Send email
    await send_email_async(email_log)
    email_service.mark_email_sent(db, email_log)

    logger.info(
        "Workflow email sent for case=%s recipient=%s",
        surrogate_id,
        _mask_email(recipient_email),
    )


async def process_csv_import(db, job) -> None:
    """
    Process CSV import job in background.

    Payload:
        - import_id: UUID of the SurrogateImport record
        - dedupe_action: "skip" (default) or other action
    """
    from app.services import import_service
    from app.db.models import SurrogateImport

    payload = job.payload or {}
    import_id = payload.get("import_id")
    dedupe_action = payload.get("dedupe_action", "skip")

    if not import_id:
        raise Exception("Missing import_id in payload")

    # Get import record
    import_record = (
        db.query(SurrogateImport).filter(SurrogateImport.id == UUID(import_id)).first()
    )

    if not import_record:
        raise Exception(f"Import record {import_id} not found")

    if not import_record.file_content:
        raise Exception(f"Import record {import_id} missing file content")

    # Update status to running
    import_record.status = "running"
    db.commit()

    logger.info(f"Starting CSV import job: {import_id}, rows={import_record.total_rows}")

    try:
        # Execute the import
        import_service.execute_import(
            db=db,
            org_id=job.organization_id,
            user_id=import_record.created_by_user_id,
            import_id=import_record.id,
            file_content=import_record.file_content,
            dedupe_action=dedupe_action,
        )
        import_record.file_content = None
        db.commit()
        logger.info(f"CSV import completed: {import_id}")
    except Exception as e:
        # Update import status to failed
        import_record.status = "failed"
        import_record.errors = import_record.errors or []
        import_record.errors.append({"message": str(e)})
        db.commit()
        logger.error(f"CSV import failed: {import_id} - {e}")
        raise


async def process_export_generation(db, job) -> None:
    """Process export generation job."""
    from app.services import compliance_service

    payload = job.payload or {}
    export_job_id = payload.get("export_job_id")
    if not export_job_id:
        raise Exception("Missing export_job_id in job payload")

    compliance_service.process_export_job(db, UUID(export_job_id))


async def process_admin_export(db, job) -> None:
    """Process admin export job."""
    from app.services import admin_export_service, analytics_service

    payload = job.payload or {}
    export_type = payload.get("export_type")
    filename = payload.get("filename")

    if not export_type:
        raise Exception("Missing export_type in job payload")

    if not filename:
        filename = admin_export_service.build_export_filename(export_type)

    if export_type == "surrogates_csv":
        file_path = admin_export_service.store_surrogates_csv(db, job.organization_id, filename)
    elif export_type == "org_config_zip":
        export_bytes = admin_export_service.build_org_config_zip(db, job.organization_id)
        file_path = admin_export_service.store_export_bytes(
            job.organization_id, filename, export_bytes
        )
    elif export_type == "analytics_zip":
        from_date = payload.get("from_date")
        to_date = payload.get("to_date")
        ad_id = payload.get("ad_id")
        start, end = analytics_service.parse_date_range(from_date, to_date)
        meta_spend = await analytics_service.get_cached_meta_spend_summary(
            db=db,
            organization_id=job.organization_id,
            start=start,
            end=end,
            time_increment=None,
            breakdowns=None,
        )
        export_bytes = admin_export_service.build_analytics_zip(
            db=db,
            org_id=job.organization_id,
            start=start,
            end=end,
            ad_id=ad_id,
            meta_spend=meta_spend,
        )
        file_path = admin_export_service.store_export_bytes(
            job.organization_id, filename, export_bytes
        )
    else:
        raise Exception(f"Unsupported admin export type: {export_type}")

    payload = {
        **payload,
        "file_path": file_path,
        "filename": filename,
    }
    job.payload = payload


async def process_ai_chat(db, job) -> None:
    """Process AI chat job."""
    from app.services import ai_chat_service, oauth_service
    from app.core.encryption import decrypt_value

    payload = job.payload or {}
    user_id = payload.get("user_id")
    message = payload.get("message")
    message_encrypted = payload.get("message_encrypted")
    entity_type = payload.get("entity_type") or "global"
    entity_id = payload.get("entity_id")

    if message_encrypted:
        try:
            message = decrypt_value(message_encrypted)
        except Exception:
            raise Exception("Failed to decrypt AI chat message")

    if not user_id or not message:
        raise Exception("Missing user_id or message in AI chat payload")

    user_uuid = UUID(user_id)
    if entity_type == "global" or not entity_id:
        entity_type = "global"
        entity_uuid = user_uuid
    else:
        entity_uuid = UUID(entity_id)

    integrations = oauth_service.get_user_integrations(db, user_uuid)
    user_integrations = [i.integration_type for i in integrations]

    result = await ai_chat_service.chat_async(
        db=db,
        organization_id=job.organization_id,
        user_id=user_uuid,
        entity_type=entity_type,
        entity_id=entity_uuid,
        message=message,
        user_integrations=user_integrations,
    )

    updated_payload = dict(payload)
    updated_payload.pop("message", None)
    updated_payload.pop("message_encrypted", None)
    updated_payload["result"] = {
        "content": result.get("content"),
        "proposed_actions": result.get("proposed_actions", []),
        "tokens_used": result.get("tokens_used", {}),
        "conversation_id": result.get("conversation_id"),
        "assistant_message_id": result.get("assistant_message_id"),
    }
    job.payload = updated_payload


async def process_data_purge(db, job) -> None:
    """Process data purge job based on retention policies."""
    from app.services import compliance_service

    payload = job.payload or {}
    org_id = payload.get("org_id")
    user_id = payload.get("user_id")
    if not org_id:
        raise Exception("Missing org_id in job payload")

    compliance_service.execute_purge(
        db=db,
        org_id=UUID(org_id),
        user_id=UUID(user_id) if user_id else None,
    )


async def process_workflow_sweep(db, job) -> None:
    """
    Process a WORKFLOW_SWEEP job - daily sweep for scheduled and inactivity workflows.

    Payload:
        - org_id: Organization to sweep (optional, sweeps all if not provided)
        - sweep_type: 'scheduled', 'inactivity', 'task_due', 'task_overdue', or 'all'
    """
    from app.services import workflow_triggers
    from app.db.models import Organization

    sweep_type = job.payload.get("sweep_type", "all")
    org_id = job.payload.get("org_id")

    if org_id:
        orgs = [db.query(Organization).filter(Organization.id == UUID(org_id)).first()]
        orgs = [o for o in orgs if o]
    else:
        orgs = db.query(Organization).all()

    logger.info(f"Starting workflow sweep: type={sweep_type}, orgs={len(orgs)}")

    for org in orgs:
        try:
            if sweep_type in ("all", "scheduled"):
                workflow_triggers.trigger_scheduled_workflows(db, org.id)

            if sweep_type in ("all", "inactivity"):
                workflow_triggers.trigger_inactivity_workflows(db, org.id)

            if sweep_type in ("all", "task_due"):
                workflow_triggers.trigger_task_due_sweep(db, org.id)

            if sweep_type in ("all", "task_overdue"):
                workflow_triggers.trigger_task_overdue_sweep(db, org.id)

            db.commit()
            logger.info(f"Workflow sweep complete for org {org.id}")
        except Exception as e:
            logger.error(f"Workflow sweep failed for org {org.id}: {e}")
            db.rollback()

    logger.info(f"Workflow sweep finished for {len(orgs)} organizations")


async def process_campaign_send(db, job) -> None:
    """
    Process a CAMPAIGN_SEND job - execute bulk email campaign.

    Payload:
        - campaign_id: UUID of the campaign
        - run_id: UUID of the campaign run
        - user_id: UUID of user who triggered the send
    """
    from uuid import UUID
    from app.services import campaign_service

    payload = job.payload or {}
    campaign_id = payload.get("campaign_id")
    run_id = payload.get("run_id")

    if not campaign_id or not run_id:
        raise Exception("Missing campaign_id or run_id in campaign send job")

    logger.info(f"Starting campaign send: campaign={campaign_id}, run={run_id}")

    try:
        # Check if campaign was cancelled before executing
        from app.db.models import Campaign
        from app.db.enums import CampaignStatus

        campaign = db.query(Campaign).filter(Campaign.id == UUID(campaign_id)).first()
        if not campaign:
            raise Exception(f"Campaign {campaign_id} not found")

        if campaign.status == CampaignStatus.CANCELLED.value:
            logger.info(f"Campaign {campaign_id} was cancelled, skipping execution")
            return  # Don't execute cancelled campaigns

        # Execute the campaign send
        result = campaign_service.execute_campaign_run(
            db=db,
            org_id=job.organization_id,
            campaign_id=UUID(campaign_id),
            run_id=UUID(run_id),
        )

        logger.info(
            f"Campaign send completed: campaign={campaign_id}, "
            f"sent={result.get('sent_count', 0)}, "
            f"failed={result.get('failed_count', 0)}, "
            f"skipped={result.get('skipped_count', 0)}"
        )
    except Exception as e:
        logger.error(
            "Campaign send failed: campaign=%s error=%s",
            campaign_id,
            type(e).__name__,
        )
        raise


async def process_workflow_approval_expiry(db, job) -> None:
    """
    Sweep for expired workflow approval tasks and mark them as expired.

    This job should be scheduled to run every 5 minutes.
    """
    from app.services import task_service
    from app.db.models import Task
    from app.db.enums import TaskType, TaskStatus

    logger.info("Starting workflow approval expiry sweep for org %s", job.organization_id)

    now = datetime.now(timezone.utc)

    # Find overdue approval tasks
    overdue_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == job.organization_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
            Task.due_at < now,
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    expired_count = 0
    for task in overdue_tasks:
        try:
            task_service.expire_approval_task(db, task)
            expired_count += 1
            logger.info(f"Expired workflow approval task {task.id}")
        except Exception as e:
            logger.error(f"Failed to expire task {task.id}: {e}")

    logger.info(f"Workflow approval expiry sweep complete: {expired_count} expired")


async def process_workflow_resume(db, job) -> None:
    """
    Resume a paused workflow after approval resolution.

    Payload:
        - execution_id: UUID of the workflow execution
        - task_id: UUID of the resolved approval task
    """
    from app.db.models import WorkflowExecution, Task, AutomationWorkflow, WorkflowResumeJob
    from app.db.enums import WorkflowExecutionStatus, TaskStatus
    from app.services.workflow_engine import WorkflowEngine

    payload = job.payload or {}
    execution_id = payload.get("execution_id")
    task_id = payload.get("task_id")
    idempotency_key = payload.get("idempotency_key")

    if not execution_id or not task_id:
        raise Exception("Missing execution_id or task_id in workflow resume job")

    # Check idempotency
    if idempotency_key:
        existing = (
            db.query(WorkflowResumeJob)
            .filter(WorkflowResumeJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing and existing.processed_at is not None:
            logger.info(f"Workflow resume job already processed: {idempotency_key}")
            return

    # Get task and execution
    task = db.query(Task).filter(Task.id == UUID(task_id)).first()
    if not task:
        raise Exception(f"Task {task_id} not found")

    execution = (
        db.query(WorkflowExecution).filter(WorkflowExecution.id == UUID(execution_id)).first()
    )
    if not execution:
        raise Exception(f"Execution {execution_id} not found")

    # Check execution is paused on this task
    if execution.status != WorkflowExecutionStatus.PAUSED.value:
        logger.info(f"Execution {execution_id} not paused, skipping resume")
        return

    if str(execution.paused_task_id) != str(task_id):
        logger.warning(
            f"Execution {execution_id} not waiting on task {task_id}, "
            f"waiting on {execution.paused_task_id}"
        )
        return

    # Get workflow
    workflow = (
        db.query(AutomationWorkflow).filter(AutomationWorkflow.id == execution.workflow_id).first()
    )
    if not workflow:
        raise Exception(f"Workflow {execution.workflow_id} not found")

    # Handle based on task status
    if task.status == TaskStatus.COMPLETED.value:
        # APPROVED: Execute the action and continue workflow
        logger.info(f"Resuming approved workflow execution {execution_id}")

        # Get entity for action execution
        from app.services.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()
        engine.continue_execution(
            db=db,
            execution_id=execution.id,
            task=task,
            decision="approve",
        )

    elif task.status == TaskStatus.DENIED.value:
        # DENIED: Cancel workflow
        logger.info(f"Workflow execution {execution_id} denied")
        execution.paused_at_action_index = None
        execution.paused_task_id = None
        execution.status = WorkflowExecutionStatus.CANCELED.value
        execution.error_message = task.workflow_denial_reason or "Approval denied by case owner"

        # Record the skipped action
        action_results = list(execution.actions_executed or [])
        action_results.append(
            {
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "denied",
            }
        )
        execution.actions_executed = action_results

    elif task.status == TaskStatus.EXPIRED.value:
        # EXPIRED: Mark workflow expired
        logger.info(f"Workflow execution {execution_id} expired")
        execution.paused_at_action_index = None
        execution.paused_task_id = None
        execution.status = WorkflowExecutionStatus.EXPIRED.value
        execution.error_message = "Approval timed out"

        action_results = list(execution.actions_executed or [])
        action_results.append(
            {
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "expired",
            }
        )
        execution.actions_executed = action_results

    else:
        logger.warning(f"Unexpected task status for resume: {task.status}")
        return

    # Mark idempotency record as processed
    if idempotency_key:
        resume_job = (
            db.query(WorkflowResumeJob)
            .filter(WorkflowResumeJob.idempotency_key == idempotency_key)
            .first()
        )
        if resume_job:
            resume_job.processed_at = datetime.now(timezone.utc)

    db.commit()
    logger.info(f"Workflow resume complete for execution {execution_id}")


# =============================================================================
# Meta Sync Job Handlers
# =============================================================================


async def process_meta_hierarchy_sync(db, job) -> None:
    """
    Process a META_HIERARCHY_SYNC job - sync campaign/adset/ad hierarchy.

    Payload:
        - ad_account_id: UUID of the MetaAdAccount
        - full_sync: bool (if True, ignore delta and fetch all)
    """
    from app.db.models import MetaAdAccount
    from app.services import meta_sync_service

    payload = job.payload or {}
    ad_account_id = payload.get("ad_account_id")
    full_sync = payload.get("full_sync", False)

    if not ad_account_id:
        raise Exception("Missing ad_account_id in job payload")

    # Get ad account
    ad_account = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.id == UUID(ad_account_id),
            MetaAdAccount.organization_id == job.organization_id,
        )
        .first()
    )

    if not ad_account:
        raise Exception(f"Ad account {ad_account_id} not found")

    if not ad_account.is_active:
        logger.info(f"Skipping hierarchy sync for inactive ad account {ad_account_id}")
        return

    logger.info(
        f"Starting hierarchy sync for ad account {ad_account.ad_account_external_id} "
        f"(full_sync={full_sync})"
    )

    try:
        result = await meta_sync_service.sync_hierarchy(
            db=db,
            ad_account=ad_account,
            full_sync=full_sync,
        )

        logger.info(
            f"Hierarchy sync complete: campaigns={result.get('campaigns', 0)}, "
            f"adsets={result.get('adsets', 0)}, ads={result.get('ads', 0)}"
        )

        # Note: Health recording handled centrally by _record_job_success

        # Link cases to campaigns (backfill)
        linked = meta_sync_service.link_surrogates_to_campaigns(db, job.organization_id)
        if linked:
            logger.info(f"Linked {linked} cases to campaign data")

    except Exception:
        raise


async def process_meta_spend_sync(db, job) -> None:
    """
    Process a META_SPEND_SYNC job - sync daily spend data.

    Payload:
        - ad_account_id: UUID of the MetaAdAccount
        - sync_type: 'daily' (default), 'weekly', 'initial'
        - date_start: optional override
        - date_end: optional override
    """
    from datetime import date, timedelta
    from app.db.models import MetaAdAccount
    from app.services import meta_sync_service

    payload = job.payload or {}
    ad_account_id = payload.get("ad_account_id")
    sync_type = payload.get("sync_type", "daily")

    if not ad_account_id:
        raise Exception("Missing ad_account_id in job payload")

    # Get ad account
    ad_account = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.id == UUID(ad_account_id),
            MetaAdAccount.organization_id == job.organization_id,
        )
        .first()
    )

    if not ad_account:
        raise Exception(f"Ad account {ad_account_id} not found")

    if not ad_account.is_active:
        logger.info(f"Skipping spend sync for inactive ad account {ad_account_id}")
        return

    # Determine date range based on sync_type
    today = date.today()

    if payload.get("date_start") and payload.get("date_end"):
        # Override dates
        date_start = date.fromisoformat(payload["date_start"])
        date_end = date.fromisoformat(payload["date_end"])
    elif sync_type == "daily":
        # Yesterday + 7-day rolling backfill
        date_start = today - timedelta(days=7)
        date_end = today - timedelta(days=1)
    elif sync_type == "weekly":
        # 90-day backfill
        date_start = today - timedelta(days=90)
        date_end = today - timedelta(days=1)
    elif sync_type == "initial":
        # 180-day initial load
        date_start = today - timedelta(days=180)
        date_end = today - timedelta(days=1)
    else:
        date_start = today - timedelta(days=7)
        date_end = today - timedelta(days=1)

    logger.info(
        f"Starting spend sync for ad account {ad_account.ad_account_external_id} "
        f"({sync_type}: {date_start} to {date_end})"
    )

    try:
        result = await meta_sync_service.sync_spend(
            db=db,
            ad_account=ad_account,
            date_start=date_start,
            date_end=date_end,
        )

        logger.info(
            f"Spend sync complete: rows_synced={result.get('rows_synced', 0)}, "
            f"campaigns={result.get('campaigns', 0)}"
        )

        # Note: Health recording handled centrally by _record_job_success

    except Exception:
        raise


async def process_meta_form_sync(db, job) -> None:
    """
    Process a META_FORM_SYNC job - sync form metadata with versioning.

    NOTE: Uses PAGE tokens from meta_page_mappings, NOT ad account tokens.
    Ad accounts don't have page permissions for leadgen_forms endpoint.

    Payload:
        - page_ids: list of page IDs to sync (optional, syncs all active if not provided)
    """
    from app.services import meta_sync_service

    payload = job.payload or {}
    page_ids = payload.get("page_ids")

    logger.info(f"Starting forms sync for org {job.organization_id} (pages={page_ids or 'all'})")

    try:
        if page_ids and isinstance(page_ids, list):
            # Sync each specified page
            total_result = {"forms_synced": 0, "versions_created": 0}
            for page_id in page_ids:
                page_result = await meta_sync_service.sync_forms(
                    db=db,
                    org_id=job.organization_id,
                    page_id=page_id,
                )
                total_result["forms_synced"] += page_result.get("forms_synced", 0)
                total_result["versions_created"] += page_result.get("versions_created", 0)
            result = total_result
        else:
            # Sync all pages
            result = await meta_sync_service.sync_forms(
                db=db,
                org_id=job.organization_id,
                page_id=None,
            )

        logger.info(
            f"Forms sync complete: forms_synced={result.get('forms_synced', 0)}, "
            f"versions_created={result.get('versions_created', 0)}"
        )

        # Note: Health recording handled centrally by _record_job_success

    except Exception:
        raise


def main() -> None:
    """Entry point for the worker."""
    try:
        _ensure_attachment_scanner_available()
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker shutting down")
    except Exception:
        report_exception(monitoring.error_reporter)
        logger.exception(
            "Worker crashed",
            extra=build_log_context(
                request_id=os.getenv("CLOUD_RUN_TASK_INDEX"),
                route="worker",
                method="background",
            ),
        )
        raise


if __name__ == "__main__":
    main()
