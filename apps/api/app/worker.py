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

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import UUID

from app.db.session import SessionLocal
from app.db.models import EmailLog
from app.db.enums import JobType
from app.services import job_service, email_service

# Configure logging
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


async def send_email_async(email_log: EmailLog) -> None:
    """
    Send an email using Resend API.
    
    If RESEND_API_KEY is not set, logs the email instead of sending.
    """
    if not RESEND_API_KEY:
        logger.info(
            f"[DRY RUN] Would send email to {email_log.recipient_email}: {email_log.subject}"
        )
        return
    
    # In production, use Resend or another email provider
    # For now, we'll just import and use resend if available
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        
        result = resend.Emails.send({
            "from": EMAIL_FROM,
            "to": [email_log.recipient_email],
            "subject": email_log.subject,
            "html": email_log.body,
        })
        logger.info(f"Email sent to {email_log.recipient_email}, ID: {result.get('id')}")
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
        # Placeholder for reminder logic
        logger.info(f"Processing reminder: {job.payload}")
        # TODO: Implement reminder logic (e.g., create notification, send email)
        
    elif job.job_type == JobType.WEBHOOK_RETRY.value:
        # Placeholder for webhook retry logic
        logger.info(f"Processing webhook retry: {job.payload}")
        # TODO: Implement webhook retry logic
        
    elif job.job_type == JobType.NOTIFICATION.value:
        # Placeholder for notification logic
        logger.info(f"Processing notification: {job.payload}")
        # TODO: Implement notification logic
        
    elif job.job_type == JobType.META_LEAD_FETCH.value:
        await process_meta_lead_fetch(db, job)
        
    else:
        raise Exception(f"Unknown job type: {job.job_type}")


async def process_meta_lead_fetch(db, job) -> None:
    """
    Process a Meta Lead Ads fetch job.
    
    1. Get page mapping and decrypt token
    2. Fetch lead details from Meta API
    3. Normalize field data
    4. Store in meta_leads table
    5. Update status on success/failure
    """
    from datetime import datetime
    from app.db.models import MetaPageMapping, MetaLead
    from app.core.encryption import decrypt_token
    from app.services import meta_api, meta_lead_service
    
    leadgen_id = job.payload.get("leadgen_id")
    page_id = job.payload.get("page_id")
    
    if not leadgen_id or not page_id:
        raise Exception("Missing leadgen_id or page_id in job payload")
    
    # Get page mapping
    mapping = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == page_id,
        MetaPageMapping.is_active == True,
    ).first()
    
    if not mapping:
        raise Exception(f"No active mapping for page {page_id}")
    
    # Decrypt access token
    try:
        access_token = decrypt_token(mapping.access_token_encrypted) if mapping.access_token_encrypted else ""
    except Exception as e:
        mapping.last_error = f"Token decryption failed: {str(e)[:100]}"
        mapping.last_error_at = datetime.utcnow()
        db.commit()
        raise Exception(f"Token decryption failed: {e}")
    
    # Fetch lead from Meta API
    lead_data, error = await meta_api.fetch_lead_details(leadgen_id, access_token)
    
    if error:
        # Update mapping with error
        mapping.last_error = error
        mapping.last_error_at = datetime.utcnow()
        db.commit()
        
        # Check if we have an existing meta_lead to update
        existing = db.query(MetaLead).filter(
            MetaLead.organization_id == mapping.organization_id,
            MetaLead.meta_lead_id == leadgen_id,
        ).first()
        if existing:
            existing.status = "fetch_failed"
            existing.fetch_error = error
            db.commit()
        
        raise Exception(error)
    
    # Normalize field data
    field_data = meta_api.normalize_field_data(lead_data.get("field_data", []))
    
    # Add ad_id for campaign tracking (stored in field_data for conversion)
    if lead_data.get("ad_id"):
        field_data["meta_ad_id"] = lead_data["ad_id"]
    
    # Parse Meta timestamp
    meta_created_time = meta_api.parse_meta_timestamp(lead_data.get("created_time"))
    
    # Store meta lead (handles dedupe)
    meta_lead, store_error = meta_lead_service.store_meta_lead(
        db=db,
        org_id=mapping.organization_id,
        meta_lead_id=leadgen_id,
        field_data=field_data,
        raw_payload=None,  # PII minimization - don't store raw
        meta_form_id=lead_data.get("form_id"),
        meta_page_id=page_id,
        meta_created_time=meta_created_time,
    )
    
    if store_error:
        # Likely duplicate - log and continue
        logger.info(f"Meta lead store skipped: {store_error}")
    else:
        # Update success tracking
        mapping.last_success_at = datetime.utcnow()
        mapping.last_error = None
        db.commit()
        
        # Update lead status
        meta_lead.status = "stored"
        db.commit()
        
        logger.info(f"Meta lead {leadgen_id} stored successfully for org {mapping.organization_id}")
        
        # Auto-convert to case so it appears in Cases list immediately
        # This allows case managers to see and bulk-assign new leads
        # We use a system user ID (None → will be assigned to no one initially)
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
            logger.info(f"Meta lead {leadgen_id} auto-converted to case {case.case_number}")


async def worker_loop() -> None:
    """Main worker loop - polls for and processes pending jobs."""
    logger.info(f"Worker starting (poll interval: {POLL_INTERVAL_SECONDS}s, batch size: {BATCH_SIZE})")
    
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set - emails will be logged but not sent")
    
    while True:
        with SessionLocal() as db:
            try:
                jobs = job_service.get_pending_jobs(db, limit=BATCH_SIZE)
                
                if jobs:
                    logger.info(f"Found {len(jobs)} pending jobs")
                
                for job in jobs:
                    try:
                        job_service.mark_job_running(db, job)
                        await process_job(db, job)
                        job_service.mark_job_completed(db, job)
                        logger.info(f"Job {job.id} completed successfully")
                    except Exception as e:
                        error_msg = str(e)
                        job_service.mark_job_failed(db, job, error_msg)
                        logger.error(f"Job {job.id} failed: {error_msg}")
                        
                        # Also mark email as failed if applicable
                        if job.job_type == JobType.SEND_EMAIL.value:
                            email_log_id = job.payload.get("email_log_id")
                            if email_log_id:
                                email_log = db.query(EmailLog).filter(
                                    EmailLog.id == UUID(email_log_id)
                                ).first()
                                if email_log:
                                    email_service.mark_email_failed(db, email_log, error_msg)
                                    
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
        
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    """Entry point for the worker."""
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker shutting down")


if __name__ == "__main__":
    main()
