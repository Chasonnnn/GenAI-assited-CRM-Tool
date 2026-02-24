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
import secrets
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.gcp_monitoring import report_exception, setup_gcp_monitoring
from app.core.structured_logging import build_log_context
from app.db.enums import JobStatus, JobType
from app.db.models import EmailLog
from app.db.session import SessionLocal
from app.jobs.handlers.ai import process_ai_chat  # noqa: F401
from app.jobs.handlers.email import RESEND_API_KEY, process_workflow_email  # noqa: F401
from app.jobs.handlers.exports import process_admin_export  # noqa: F401
from app.jobs.handlers.imports import process_csv_import  # noqa: F401
from app.jobs.handlers.interviews import process_interview_transcription  # noqa: F401
from app.jobs.handlers.meta import (  # noqa: F401
    process_meta_form_sync,
    process_meta_hierarchy_sync,
    process_meta_lead_fetch,
    process_meta_spend_sync,
)
from app.jobs.registry import resolve_job_handler
from app.services import email_service, job_service

monitoring = setup_gcp_monitoring(f"{settings.GCP_SERVICE_NAME}-worker")

# Configure logging (fallback when Cloud Logging isn't enabled)
if not monitoring.logging_enabled:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
logger = logging.getLogger(__name__)

# Worker configuration
POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL", "10"))
BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "10"))
SESSION_CLEANUP_INTERVAL_SECONDS = int(os.getenv("SESSION_CLEANUP_INTERVAL_SECONDS", "3600"))


def _env_flag_enabled(raw: str | None, *, default: bool = True) -> bool:
    if raw is None:
        return default
    token = raw.strip().lower()
    if not token:
        return default
    return token not in {"0", "false", "no", "off"}


GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED = _env_flag_enabled(
    os.getenv("GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED"),
    default=True,
)
GOOGLE_CALENDAR_SYNC_FALLBACK_INTERVAL_SECONDS = int(
    os.getenv("GOOGLE_CALENDAR_SYNC_FALLBACK_INTERVAL_SECONDS", "300")
)
GMAIL_SYNC_FALLBACK_ENABLED = _env_flag_enabled(
    os.getenv("GMAIL_SYNC_FALLBACK_ENABLED"),
    default=True,
)
GMAIL_SYNC_FALLBACK_INTERVAL_SECONDS = int(os.getenv("GMAIL_SYNC_FALLBACK_INTERVAL_SECONDS", "60"))


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


def maybe_schedule_google_calendar_sync_jobs(
    db,
    *,
    now: datetime,
    last_run_at: datetime | None,
) -> datetime | None:
    """
    Best-effort fallback scheduler for Google Calendar/Tasks sync jobs.

    This keeps sync running even when external cron isn't configured.
    """
    if not GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED:
        return last_run_at

    interval_seconds = max(1, GOOGLE_CALENDAR_SYNC_FALLBACK_INTERVAL_SECONDS)
    if last_run_at and now < (last_run_at + timedelta(seconds=interval_seconds)):
        return last_run_at

    from app.services import google_calendar_sync_service

    counts = google_calendar_sync_service.schedule_google_calendar_sync_jobs(
        db=db,
        now=now,
    )
    logger.info(
        "Google sync fallback scheduled (connected=%s calendar_jobs=%s task_jobs=%s watch_jobs=%s)",
        counts["connected_users"],
        counts["jobs_created"],
        counts["task_jobs_created"],
        counts["watch_jobs_created"],
    )
    return now


def maybe_schedule_gmail_sync_jobs(
    db,
    *,
    now: datetime,
    last_run_at: datetime | None,
) -> datetime | None:
    """
    Best-effort fallback scheduler for Gmail mailbox history sync jobs.

    This keeps ticketing email ingestion running when external cron is not configured.
    """
    if not GMAIL_SYNC_FALLBACK_ENABLED:
        return last_run_at

    interval_seconds = max(1, GMAIL_SYNC_FALLBACK_INTERVAL_SECONDS)
    if last_run_at and now < (last_run_at + timedelta(seconds=interval_seconds)):
        return last_run_at

    from app.services import ticketing_service

    counts = ticketing_service.schedule_incremental_sync_jobs(db)
    logger.info(
        "Gmail sync fallback scheduled (mailboxes=%s jobs=%s watch_jobs=%s)",
        counts["mailboxes_checked"],
        counts["jobs_created"],
        counts.get("watch_jobs_created", 0),
    )
    return now


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


def _sync_clamav_signatures() -> None:
    if settings.ATTACHMENT_SCAN_ENABLED and not settings.is_dev:
        from app.services import clamav_signature_service

        try:
            clamav_signature_service.ensure_signatures()
        except Exception as exc:
            logger.warning("ClamAV signature sync failed: %s", exc)


async def process_job(db, job) -> None:
    """Process a single job based on its type."""
    logger.info("Processing job %s (type=%s, attempt=%s)", job.id, job.job_type, job.attempts)
    handler = resolve_job_handler(job.job_type)
    await handler(db, job)


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

    elif integration_type == IntegrationType.ZAPIER:
        webhook_id = payload.get("webhook_id")
        if webhook_id:
            keys.append(str(webhook_id))
        else:
            keys.append("outbound")

    elif integration_type == IntegrationType.WORKER:
        mailbox_id = payload.get("mailbox_id")
        if mailbox_id:
            keys.append(f"mailbox:{mailbox_id}")
        ticket_id = payload.get("ticket_id")
        if ticket_id:
            keys.append(f"ticket:{ticket_id}")
        if payload.get("mode") == "reply":
            keys.append("ticket_outbound_reply")
        elif payload.get("mode") == "compose":
            keys.append("ticket_outbound_compose")
        if not keys:
            keys.append(str(job.job_type))

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
        JobType.META_LEAD_REPROCESS_FORM.value: IntegrationType.META_LEADS,
        JobType.META_CAPI_EVENT.value: IntegrationType.META_CAPI,
        JobType.META_HIERARCHY_SYNC.value: IntegrationType.META_HIERARCHY,
        JobType.META_SPEND_SYNC.value: IntegrationType.META_SPEND,
        JobType.META_FORM_SYNC.value: IntegrationType.META_FORMS,
        JobType.ZAPIER_STAGE_EVENT.value: IntegrationType.ZAPIER,
        JobType.MAILBOX_BACKFILL.value: IntegrationType.WORKER,
        JobType.MAILBOX_HISTORY_SYNC.value: IntegrationType.WORKER,
        JobType.MAILBOX_WATCH_REFRESH.value: IntegrationType.WORKER,
        JobType.EMAIL_OCCURRENCE_FETCH_RAW.value: IntegrationType.WORKER,
        JobType.EMAIL_OCCURRENCE_PARSE.value: IntegrationType.WORKER,
        JobType.EMAIL_OCCURRENCE_STITCH.value: IntegrationType.WORKER,
        JobType.TICKET_APPLY_LINKING.value: IntegrationType.WORKER,
        JobType.TICKET_OUTBOUND_SEND.value: IntegrationType.WORKER,
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
            logger.warning("Failed to record job success: %s", e)


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
            JobType.META_LEAD_REPROCESS_FORM.value: IntegrationType.META_LEADS,
            JobType.META_CAPI_EVENT.value: IntegrationType.META_CAPI,
            JobType.META_HIERARCHY_SYNC.value: IntegrationType.META_HIERARCHY,
            JobType.META_SPEND_SYNC.value: IntegrationType.META_SPEND,
            JobType.META_FORM_SYNC.value: IntegrationType.META_FORMS,
            JobType.ZAPIER_STAGE_EVENT.value: IntegrationType.ZAPIER,
            JobType.MAILBOX_BACKFILL.value: IntegrationType.WORKER,
            JobType.MAILBOX_HISTORY_SYNC.value: IntegrationType.WORKER,
            JobType.MAILBOX_WATCH_REFRESH.value: IntegrationType.WORKER,
            JobType.EMAIL_OCCURRENCE_FETCH_RAW.value: IntegrationType.WORKER,
            JobType.EMAIL_OCCURRENCE_PARSE.value: IntegrationType.WORKER,
            JobType.EMAIL_OCCURRENCE_STITCH.value: IntegrationType.WORKER,
            JobType.TICKET_APPLY_LINKING.value: IntegrationType.WORKER,
            JobType.TICKET_OUTBOUND_SEND.value: IntegrationType.WORKER,
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
                JobType.TICKET_OUTBOUND_SEND.value: AlertType.EMAIL_SEND_FAILED,
                JobType.WEBHOOK_RETRY.value: AlertType.WEBHOOK_DELIVERY_FAILED,
                JobType.AI_CHAT.value: AlertType.AI_PROVIDER_ERROR,
                JobType.INTERVIEW_TRANSCRIPTION.value: AlertType.TRANSCRIPTION_FAILED,
                JobType.ZAPIER_STAGE_EVENT.value: AlertType.WEBHOOK_DELIVERY_FAILED,
                JobType.MAILBOX_BACKFILL.value: AlertType.INTEGRATION_API_ERROR,
                JobType.MAILBOX_HISTORY_SYNC.value: AlertType.INTEGRATION_API_ERROR,
                JobType.MAILBOX_WATCH_REFRESH.value: AlertType.INTEGRATION_API_ERROR,
                JobType.EMAIL_OCCURRENCE_FETCH_RAW.value: AlertType.INTEGRATION_API_ERROR,
                JobType.EMAIL_OCCURRENCE_PARSE.value: AlertType.INTEGRATION_API_ERROR,
                JobType.EMAIL_OCCURRENCE_STITCH.value: AlertType.INTEGRATION_API_ERROR,
                JobType.TICKET_APPLY_LINKING.value: AlertType.INTEGRATION_API_ERROR,
            }
            alert_type = alert_type_map.get(job.job_type, AlertType.WORKER_JOB_FAILED)

            # Use actual exception class name for fingerprinting
            error_class = type(exception).__name__ if exception else "UnknownError"

            alert_service.record_alert_isolated(
                org_id=job.organization_id,
                alert_type=alert_type,
                severity=AlertSeverity.ERROR,
                title=f"{job.job_type} failed after {job.attempts} attempts",
                message=error_msg[:500],
                integration_key=integration_keys[0] if integration_keys else None,
                error_class=error_class,
            )
    except Exception as e:
        logger.warning("Failed to record job failure: %s", e)


def _is_meta_rate_limit_error(job, error_msg: str) -> bool:
    from app.services import meta_token_service
    from app.db.enums import JobType

    if job.job_type not in (
        JobType.META_SPEND_SYNC.value,
        JobType.META_HIERARCHY_SYNC.value,
        JobType.META_FORM_SYNC.value,
        JobType.META_LEAD_FETCH.value,
    ):
        return False

    category = meta_token_service.classify_meta_error(Exception(error_msg))
    return category == meta_token_service.ErrorCategory.RATE_LIMIT


def _rate_limit_backoff_seconds(attempts: int) -> int:
    # Exponential backoff with jitter, capped at 1 hour
    base = 60
    delay = min(3600, base * (2 ** max(attempts - 1, 0)))
    jitter = secrets.randbelow(31)
    return delay + jitter


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
    last_google_sync_schedule: datetime | None = None
    last_gmail_sync_schedule: datetime | None = None

    while True:
        with SessionLocal() as db:
            try:
                now = datetime.now(timezone.utc)
                try:
                    last_google_sync_schedule = maybe_schedule_google_calendar_sync_jobs(
                        db,
                        now=now,
                        last_run_at=last_google_sync_schedule,
                    )
                except Exception:
                    logger.exception("Google sync fallback scheduling failed")

                try:
                    last_gmail_sync_schedule = maybe_schedule_gmail_sync_jobs(
                        db,
                        now=now,
                        last_run_at=last_gmail_sync_schedule,
                    )
                except Exception:
                    logger.exception("Gmail sync fallback scheduling failed")

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
                    logger.info("Found %s pending jobs", len(jobs))

                for job in jobs:
                    try:
                        await process_job(db, job)
                        job_service.mark_job_completed(db, job)
                        logger.info("Job %s completed successfully", job.id)

                        # Record success for integration health (Meta jobs)
                        _record_job_success(db, job)

                    except Exception as e:
                        error_msg = str(e)
                        job_service.mark_job_failed(db, job, error_msg)
                        logger.error(
                            "Job %s failed (type=%s): %s",
                            job.id,
                            job.job_type,
                            type(e).__name__,
                        )

                        # Apply rate limit backoff for Meta throttling errors
                        if job.status == JobStatus.PENDING.value and _is_meta_rate_limit_error(
                            job, error_msg
                        ):
                            delay = _rate_limit_backoff_seconds(job.attempts)
                            job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                            db.commit()
                            logger.warning(
                                "Rate limit backoff applied for job %s: retrying in %ss",
                                job.id,
                                delay,
                            )

                        # Record failure for integration health and alerts
                        _record_job_failure(db, job, error_msg, exception=e)

                        # AI: scrub encrypted message payload after final failure
                        if (
                            job.job_type == JobType.AI_CHAT.value
                            and job.status == JobStatus.FAILED.value
                        ):
                            payload = job.payload or {}
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
                logger.error("Error in worker loop: %s", e)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    """Entry point for the worker."""
    try:
        _sync_clamav_signatures()
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
