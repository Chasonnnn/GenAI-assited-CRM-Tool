"""
Virus scan worker job for attachments.

This module provides a ClamAV-based virus scanning job that can be run
asynchronously to scan uploaded attachments.

Usage:
    # In a worker process or background task:
    from app.jobs.scan_attachment import scan_attachment_job
    scan_attachment_job(attachment_id)
"""

import logging
import os
import shutil
import subprocess
import tempfile
from uuid import UUID


from app.core.config import settings
from app.db.models import Attachment, FormSubmissionFile
from app.db.session import SessionLocal
from app.services import attachment_service, notification_service, alert_service
from app.db.enums import AlertSeverity, AlertType

logger = logging.getLogger(__name__)


def _download_storage_key_to_temp(storage_key: str) -> str:
    """Download storage key to a temporary file for scanning."""
    backend = attachment_service._get_storage_backend()

    if backend == "s3":
        from app.services import storage_client

        s3 = storage_client.get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            s3.download_fileobj(bucket, storage_key, tmp)
            return tmp.name

    # Local storage - file already on disk
    return os.path.join(attachment_service._get_local_storage_path(), storage_key)


def _download_to_temp(attachment: Attachment) -> str:
    """Download attachment to temporary file for scanning."""
    return _download_storage_key_to_temp(attachment.storage_key)


def get_available_scanner() -> str | None:
    """Return the first available ClamAV scanner binary."""
    for scanner in ["clamdscan", "clamscan"]:
        if shutil.which(scanner):
            return scanner
    return None


def _run_clamav_scan(file_path: str) -> tuple[str, str]:
    """
    Run ClamAV scan on a file.

    Returns:
        (status, message)
    """
    try:
        scanner = get_available_scanner()
        if not scanner:
            logger.warning("ClamAV not installed, skipping scan")
            return "scanner_not_available", "scanner_not_available"

        result = subprocess.run(
            [scanner, "--no-summary", file_path],
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
        )

        # Exit code 0 = clean, 1 = infected, 2 = error
        if result.returncode == 0:
            return "clean", "clean"
        if result.returncode == 1:
            virus_name = result.stdout.strip().split(":")[-1].strip()
            return "infected", f"infected: {virus_name}"

        logger.warning(f"ClamAV error: {result.stderr}")
        return "scan_error", result.stderr.strip() or "scan_error"

    except subprocess.TimeoutExpired:
        logger.error(f"ClamAV scan timed out for {file_path}")
        return "timeout", "timeout"
    except FileNotFoundError:
        logger.warning("ClamAV scanner not available")
        return "scanner_not_available", "scanner_not_available"
    except Exception as e:
        logger.error(f"ClamAV scan error: {e}")
        return "error", str(e)


def scan_attachment_job(attachment_id: UUID) -> bool:
    """
    Scan an attachment for viruses and update its status.

    This is designed to be called from a background worker (Celery, RQ, etc.)

    Returns:
        True if scan completed (regardless of result), False on error
    """
    if not getattr(settings, "ATTACHMENT_SCAN_ENABLED", False):
        logger.info(f"Scanning disabled, marking {attachment_id} as clean")
        # Mark as clean without scanning
        db = SessionLocal()
        try:
            attachment_service.mark_attachment_scanned(db, attachment_id, "clean")
            db.commit()
            return True
        finally:
            db.close()

    db = SessionLocal()
    temp_file = None
    try:
        # Get attachment
        attachment = (
            db.query(Attachment)
            .filter(
                Attachment.id == attachment_id,
                Attachment.scan_status == "pending",
            )
            .first()
        )

        if not attachment:
            logger.info(f"Attachment {attachment_id} not found or already scanned")
            return False

        # Download to temp file
        temp_file = _download_to_temp(attachment)

        # Run scan
        scan_status, message = _run_clamav_scan(temp_file)

        # Update status
        if scan_status == "clean":
            attachment_service.mark_attachment_scanned(db, attachment_id, "clean")
            logger.info(f"Attachment {attachment_id} is clean")
        elif scan_status == "infected":
            attachment_service.mark_attachment_scanned(db, attachment_id, "infected")
            logger.warning(f"Attachment {attachment_id} is infected: {message}")
            try:
                notification_service.notify_attachment_infected(db, attachment)
            except Exception as notify_error:
                logger.warning(
                    f"Failed to notify uploader for attachment {attachment_id}: {notify_error}"
                )
        else:
            if settings.is_dev:
                attachment_service.mark_attachment_scanned(db, attachment_id, "clean")
                logger.warning(
                    "Attachment scan unavailable in dev/test (%s); treating as clean",
                    scan_status,
                )
            else:
                attachment_service.mark_attachment_scanned(db, attachment_id, "error")
                logger.error(
                    "Attachment scan failed (%s) for %s: %s",
                    scan_status,
                    attachment_id,
                    message,
                )
                try:
                    alert_service.create_or_update_alert(
                        db=db,
                        org_id=attachment.organization_id,
                        alert_type=AlertType.WORKER_JOB_FAILED,
                        severity=AlertSeverity.ERROR,
                        title="Attachment scan failed",
                        message=f"Attachment scan failed ({scan_status}): {message}",
                        integration_key="attachment_scan",
                        error_class=scan_status,
                        details={
                            "attachment_id": str(attachment.id),
                            "storage_key": attachment.storage_key,
                        },
                    )
                except Exception as alert_error:
                    logger.warning(
                        "Failed to create scan failure alert for %s: %s",
                        attachment_id,
                        alert_error,
                    )

        db.commit()
        return True

    except Exception as e:
        logger.error(f"Failed to scan attachment {attachment_id}: {e}")
        db.rollback()

        # Mark as error to avoid re-processing
        try:
            attachment_service.mark_attachment_scanned(db, attachment_id, "error")
            db.commit()
        except Exception:
            pass

        return False

    finally:
        # Clean up temp file (only if we created it for S3)
        if temp_file and attachment_service._get_storage_backend() == "s3":
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        db.close()


def scan_form_submission_file_job(file_id: UUID) -> bool:
    """
    Scan a form submission file for viruses and update its status.

    Returns:
        True if scan completed (regardless of result), False on error
    """
    if not getattr(settings, "ATTACHMENT_SCAN_ENABLED", False):
        logger.info("Scanning disabled, marking form submission file %s as clean", file_id)
        db = SessionLocal()
        try:
            from app.services import form_submission_service

            form_submission_service.mark_submission_file_scanned(db, file_id, "clean")
            db.commit()
            return True
        finally:
            db.close()

    db = SessionLocal()
    temp_file = None
    try:
        file_record = (
            db.query(FormSubmissionFile)
            .filter(
                FormSubmissionFile.id == file_id,
                FormSubmissionFile.scan_status == "pending",
            )
            .first()
        )

        if not file_record:
            logger.info("Form submission file %s not found or already scanned", file_id)
            return False

        temp_file = _download_storage_key_to_temp(file_record.storage_key)
        scan_status, message = _run_clamav_scan(temp_file)

        from app.services import form_submission_service

        if scan_status == "clean":
            form_submission_service.mark_submission_file_scanned(db, file_id, "clean")
            logger.info("Form submission file %s is clean", file_id)
        elif scan_status == "infected":
            form_submission_service.mark_submission_file_scanned(db, file_id, "infected")
            logger.warning("Form submission file %s is infected: %s", file_id, message)
        else:
            if settings.is_dev:
                form_submission_service.mark_submission_file_scanned(db, file_id, "clean")
                logger.warning(
                    "Form submission scan unavailable in dev/test (%s); treating as clean",
                    scan_status,
                )
            else:
                form_submission_service.mark_submission_file_scanned(db, file_id, "error")
                logger.error(
                    "Form submission scan failed (%s) for %s: %s",
                    scan_status,
                    file_id,
                    message,
                )
                try:
                    alert_service.create_or_update_alert(
                        db=db,
                        org_id=file_record.organization_id,
                        alert_type=AlertType.WORKER_JOB_FAILED,
                        severity=AlertSeverity.ERROR,
                        title="Form submission file scan failed",
                        message=f"Form submission file scan failed ({scan_status}): {message}",
                        integration_key="form_submission_file_scan",
                        error_class=scan_status,
                        details={
                            "submission_file_id": str(file_record.id),
                            "storage_key": file_record.storage_key,
                        },
                    )
                except Exception as alert_error:
                    logger.warning(
                        "Failed to create scan failure alert for %s: %s",
                        file_id,
                        alert_error,
                    )

        db.commit()
        return True

    except Exception as e:
        logger.error("Failed to scan form submission file %s: %s", file_id, e)
        db.rollback()
        try:
            from app.services import form_submission_service

            form_submission_service.mark_submission_file_scanned(db, file_id, "error")
            db.commit()
        except Exception:
            pass
        return False

    finally:
        if temp_file and attachment_service._get_storage_backend() == "s3":
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        db.close()


def scan_pending_attachments() -> int:
    """
    Scan all pending attachments. Useful for batch processing.

    Returns:
        Number of attachments scanned
    """
    if not getattr(settings, "ATTACHMENT_SCAN_ENABLED", False):
        logger.info("Attachment scanning is disabled")
        return 0

    db = SessionLocal()
    try:
        pending = (
            db.query(Attachment)
            .filter(
                Attachment.scan_status == "pending",
            )
            .limit(100)
            .all()
        )

        count = 0
        for attachment in pending:
            if scan_attachment_job(attachment.id):
                count += 1

        return count

    finally:
        db.close()
