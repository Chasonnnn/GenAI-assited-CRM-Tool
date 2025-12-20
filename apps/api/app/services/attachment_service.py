"""Attachment service for file uploads with security features."""

import hashlib
import os
import uuid
from datetime import datetime, timedelta
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Attachment, AuditLog


# =============================================================================
# Configuration
# =============================================================================

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes


# =============================================================================
# Storage Backend
# =============================================================================

def _get_s3_client():
    """Get boto3 S3 client."""
    return boto3.client(
        "s3",
        region_name=getattr(settings, "S3_REGION", "us-east-1"),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )


def _get_storage_backend() -> str:
    """Get configured storage backend."""
    return getattr(settings, "STORAGE_BACKEND", "local")


def _get_local_storage_path() -> str:
    """Get local storage directory path."""
    path = getattr(settings, "LOCAL_STORAGE_PATH", "/tmp/crm-attachments")
    os.makedirs(path, exist_ok=True)
    return path


# =============================================================================
# File Operations
# =============================================================================

def calculate_checksum(file: BinaryIO) -> str:
    """Calculate SHA-256 checksum of file."""
    sha256 = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


def validate_file(filename: str, content_type: str, file_size: int) -> tuple[bool, str | None]:
    """
    Validate file against allowlists and size limits.
    
    Returns (is_valid, error_message)
    """
    # Check extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '.{ext}' not allowed"
    
    # Check MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        return False, f"Content type '{content_type}' not allowed"
    
    # Check size
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return False, f"File size exceeds {max_mb:.0f} MB limit"
    
    return True, None


def store_file(storage_key: str, file: BinaryIO) -> None:
    """Store file to configured backend."""
    backend = _get_storage_backend()
    
    if backend == "s3":
        s3 = _get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        s3.upload_fileobj(file, bucket, storage_key)
    else:
        # Local storage
        path = os.path.join(_get_local_storage_path(), storage_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            file.seek(0)
            f.write(file.read())


def generate_signed_url(storage_key: str) -> str:
    """Generate signed download URL."""
    backend = _get_storage_backend()
    
    if backend == "s3":
        s3 = _get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": storage_key},
                ExpiresIn=SIGNED_URL_EXPIRY_SECONDS,
            )
            return url
        except ClientError:
            return ""
    else:
        # Local: return file path (for dev only)
        return f"/api/attachments/local/{storage_key}"


def delete_file(storage_key: str) -> None:
    """Delete file from storage (for permanent deletion)."""
    backend = _get_storage_backend()
    
    if backend == "s3":
        s3 = _get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        s3.delete_object(Bucket=bucket, Key=storage_key)
    else:
        path = os.path.join(_get_local_storage_path(), storage_key)
        if os.path.exists(path):
            os.remove(path)


# =============================================================================
# Service Functions
# =============================================================================

def upload_attachment(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content_type: str,
    file: BinaryIO,
    file_size: int,
) -> Attachment:
    """
    Upload and store an attachment.
    
    File is quarantined until virus scan passes.
    """
    # Validate
    is_valid, error = validate_file(filename, content_type, file_size)
    if not is_valid:
        raise ValueError(error)
    
    # Calculate checksum
    checksum = calculate_checksum(file)
    
    # Generate storage key
    attachment_id = uuid.uuid4()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    storage_key = f"{org_id}/{case_id}/{attachment_id}.{ext}"
    
    # Store file
    store_file(storage_key, file)
    
    # Create record
    attachment = Attachment(
        id=attachment_id,
        organization_id=org_id,
        case_id=case_id,
        uploaded_by_user_id=user_id,
        filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending",
        quarantined=True,
    )
    db.add(attachment)
    
    # Audit log
    audit = AuditLog(
        organization_id=org_id,
        user_id=user_id,
        action="attachment.upload",
        entity_type="attachment",
        entity_id=attachment_id,
        changes={"filename": filename, "size": file_size},
    )
    db.add(audit)
    
    db.flush()
    return attachment


def list_attachments(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
    include_quarantined: bool = False,
) -> list[Attachment]:
    """List attachments for a case (excludes deleted)."""
    query = db.query(Attachment).filter(
        Attachment.organization_id == org_id,
        Attachment.case_id == case_id,
        Attachment.deleted_at.is_(None),
    )
    
    if not include_quarantined:
        query = query.filter(Attachment.quarantined == False)  # noqa: E712
    
    return query.order_by(Attachment.created_at.desc()).all()


def get_attachment(
    db: Session,
    org_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> Attachment | None:
    """Get single attachment by ID."""
    return db.query(Attachment).filter(
        Attachment.organization_id == org_id,
        Attachment.id == attachment_id,
        Attachment.deleted_at.is_(None),
    ).first()


def get_download_url(
    db: Session,
    org_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """Get signed download URL and log access."""
    attachment = get_attachment(db, org_id, attachment_id)
    if not attachment or attachment.quarantined:
        return None
    
    # Audit log
    audit = AuditLog(
        organization_id=org_id,
        user_id=user_id,
        action="attachment.download",
        entity_type="attachment",
        entity_id=attachment_id,
        changes={"filename": attachment.filename},
    )
    db.add(audit)
    db.flush()
    
    return generate_signed_url(attachment.storage_key)


def soft_delete_attachment(
    db: Session,
    org_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Soft-delete an attachment."""
    attachment = get_attachment(db, org_id, attachment_id)
    if not attachment:
        return False
    
    attachment.deleted_at = datetime.utcnow()
    attachment.deleted_by_user_id = user_id
    
    # Audit log
    audit = AuditLog(
        organization_id=org_id,
        user_id=user_id,
        action="attachment.delete",
        entity_type="attachment",
        entity_id=attachment_id,
        changes={"filename": attachment.filename},
    )
    db.add(audit)
    
    db.flush()
    return True


# =============================================================================
# Virus Scan (called by async worker)
# =============================================================================

def mark_attachment_scanned(
    db: Session,
    attachment_id: uuid.UUID,
    scan_result: str,  # clean | infected | error
) -> None:
    """Update attachment scan status (called by worker)."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        return
    
    attachment.scan_status = scan_result
    attachment.scanned_at = datetime.utcnow()
    
    if scan_result == "clean":
        attachment.quarantined = False
    
    db.flush()
