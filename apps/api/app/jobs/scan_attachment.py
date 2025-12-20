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
import subprocess
import tempfile
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Attachment
from app.db.session import SessionLocal
from app.services import attachment_service

logger = logging.getLogger(__name__)


def _download_to_temp(attachment: Attachment) -> str:
    """Download attachment to temporary file for scanning."""
    backend = attachment_service._get_storage_backend()
    
    if backend == "s3":
        import boto3
        s3 = boto3.client(
            "s3",
            region_name=getattr(settings, "S3_REGION", "us-east-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        )
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            s3.download_fileobj(bucket, attachment.storage_key, tmp)
            return tmp.name
    else:
        # Local storage - file already on disk
        return os.path.join(
            attachment_service._get_local_storage_path(),
            attachment.storage_key
        )


def _run_clamav_scan(file_path: str) -> tuple[bool, str]:
    """
    Run ClamAV scan on a file.
    
    Returns:
        (is_clean, message)
    """
    try:
        # Try clamscan (standalone) first, then clamdscan (daemon)
        for scanner in ["clamdscan", "clamscan"]:
            try:
                result = subprocess.run(
                    [scanner, "--no-summary", file_path],
                    capture_output=True,
                    text=True,
                    timeout=60,  # 60 second timeout
                )
                
                # Exit code 0 = clean, 1 = infected, 2 = error
                if result.returncode == 0:
                    return True, "clean"
                elif result.returncode == 1:
                    # Parse virus name from output
                    virus_name = result.stdout.strip().split(":")[-1].strip()
                    return False, f"infected: {virus_name}"
                else:
                    logger.warning(f"ClamAV error: {result.stderr}")
                    return True, "scan_error"  # Treat errors as clean to avoid blocking
                    
            except FileNotFoundError:
                continue
        
        # No scanner found
        logger.warning("ClamAV not installed, skipping scan")
        return True, "scanner_not_available"
        
    except subprocess.TimeoutExpired:
        logger.error(f"ClamAV scan timed out for {file_path}")
        return True, "timeout"
    except Exception as e:
        logger.error(f"ClamAV scan error: {e}")
        return True, "error"


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
        attachment = db.query(Attachment).filter(
            Attachment.id == attachment_id,
            Attachment.scan_status == "pending",
        ).first()
        
        if not attachment:
            logger.info(f"Attachment {attachment_id} not found or already scanned")
            return False
        
        # Download to temp file
        temp_file = _download_to_temp(attachment)
        
        # Run scan
        is_clean, message = _run_clamav_scan(temp_file)
        
        # Update status
        if is_clean:
            attachment_service.mark_attachment_scanned(db, attachment_id, "clean")
            logger.info(f"Attachment {attachment_id} is clean")
        else:
            attachment_service.mark_attachment_scanned(db, attachment_id, "infected")
            logger.warning(f"Attachment {attachment_id} is infected: {message}")
            # TODO: Send notification to uploader
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Failed to scan attachment {attachment_id}: {e}")
        db.rollback()
        
        # Mark as error to avoid re-processing
        try:
            attachment_service.mark_attachment_scanned(db, attachment_id, "error")
            db.commit()
        except:
            pass
        
        return False
        
    finally:
        # Clean up temp file (only if we created it for S3)
        if temp_file and attachment_service._get_storage_backend() == "s3":
            try:
                os.unlink(temp_file)
            except:
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
        pending = db.query(Attachment).filter(
            Attachment.scan_status == "pending",
            Attachment.quarantined == True,  # noqa: E712
        ).limit(100).all()
        
        count = 0
        for attachment in pending:
            if scan_attachment_job(attachment.id):
                count += 1
        
        return count
        
    finally:
        db.close()
