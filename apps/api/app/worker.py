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
        
    else:
        raise Exception(f"Unknown job type: {job.job_type}")


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
