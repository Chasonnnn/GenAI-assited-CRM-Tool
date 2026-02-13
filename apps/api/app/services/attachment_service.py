"""Attachment service for file uploads with security features."""

import hashlib
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from botocore.client import BaseClient
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from sqlalchemy import event

from app.core.config import settings
from app.db.enums import AuditEventType, JobType
from app.db.models import Attachment
from app.services import storage_client
from app.services import audit_service, job_service

logger = logging.getLogger(__name__)


class AttachmentStorageError(RuntimeError):
    """Raised when attachment storage fails."""


# =============================================================================
# Configuration
# =============================================================================

EXTENSION_TO_MIME = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    "mp4": {"video/mp4"},
    "mov": {"video/quicktime"},
}
ALLOWED_EXTENSIONS = set(EXTENSION_TO_MIME.keys())
ALLOWED_MIME_TYPES = {mime for mimes in EXTENSION_TO_MIME.values() for mime in mimes}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes

_EXECUTABLE_SIGNATURE_PREFIXES = (
    b"MZ",  # Windows PE
    b"\x7fELF",  # Linux ELF
    b"\xfe\xed\xfa\xce",  # Mach-O (32-bit)
    b"\xfe\xed\xfa\xcf",  # Mach-O (64-bit)
    b"\xcf\xfa\xed\xfe",  # Mach-O (reverse endian)
    b"\xca\xfe\xba\xbe",  # Mach-O fat
    b"\xbe\xba\xfe\xca",  # Mach-O fat (reverse endian)
)


# =============================================================================
# Storage Backend
# =============================================================================


def _get_s3_client() -> BaseClient:
    """Get boto3 S3 client."""
    return storage_client.get_s3_client()


def _get_storage_backend() -> str:
    """Get configured storage backend."""
    return getattr(settings, "STORAGE_BACKEND", "local")


def _get_local_storage_path() -> str:
    """Get local storage directory path."""
    path = getattr(settings, "LOCAL_STORAGE_PATH", None)
    if not path:
        path = os.path.join(tempfile.gettempdir(), "crm-attachments")
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


def _read_file_prefix(file: BinaryIO, size: int) -> bytes:
    """Read bytes from the beginning of a file without consuming the stream."""
    pos = file.tell()
    try:
        file.seek(0)
        return file.read(size)
    finally:
        file.seek(pos)


def validate_file(
    filename: str,
    content_type: str,
    file_size: int,
    allowed_extensions: set[str] | None = None,
    allowed_mime_types: set[str] | None = None,
) -> tuple[bool, str | None]:
    """
    Validate file against allowlists and size limits.
    Enforces that file extension matches the provided MIME type.

    Returns (is_valid, error_message)
    """
    # Check extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = allowed_extensions or ALLOWED_EXTENSIONS
    allowed_mimes = allowed_mime_types or ALLOWED_MIME_TYPES

    if ext not in allowed_exts:
        return False, f"File extension '.{ext}' not allowed"

    # Check MIME type
    if content_type not in allowed_mimes:
        return False, f"Content type '{content_type}' not allowed"

    # Enforce strict extension <-> MIME type consistency to prevent spoofing
    # Only enforce if the extension is known in our strict mapping
    if ext in EXTENSION_TO_MIME:
        valid_mimes = EXTENSION_TO_MIME[ext]
        if content_type not in valid_mimes:
            return False, f"Content type '{content_type}' does not match extension '.{ext}'"

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
            shutil.copyfileobj(file, f)


def strip_exif_data(file: BinaryIO, content_type: str) -> BinaryIO:
    """
    Strip EXIF metadata from image files for privacy.

    Returns the same file object if not an image or if stripping fails.
    """
    if content_type not in ("image/jpeg", "image/png"):
        return file

    try:
        from PIL import Image
        from io import BytesIO

        file.seek(0)
        img = Image.open(file)

        # Create new image without EXIF
        data = list(img.getdata())
        img_no_exif = Image.new(img.mode, img.size)
        img_no_exif.putdata(data)

        # Save to new buffer
        output = BytesIO()
        img_format = "JPEG" if content_type == "image/jpeg" else "PNG"
        img_no_exif.save(output, format=img_format, quality=95)
        output.seek(0)

        return output

    except ImportError:
        # Pillow not installed, skip stripping
        file.seek(0)
        return file
    except Exception:
        # Failed to process, return original
        file.seek(0)
        return file


def generate_signed_url(storage_key: str, expires_in_seconds: int | None = None) -> str:
    """Generate signed download URL."""
    backend = _get_storage_backend()
    expires_in = expires_in_seconds or SIGNED_URL_EXPIRY_SECONDS

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": storage_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError:
            return ""
    else:
        # Local: return file path (for dev only)
        return f"/attachments/local/{storage_key}"


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


def _cleanup_storage_keys(session: Session, delete_files: bool) -> None:
    keys = session.info.pop("storage_cleanup_keys", set())
    session.info.pop("storage_cleanup_listener", None)
    if not delete_files:
        return
    for key in keys:
        try:
            delete_file(key)
        except Exception as exc:
            logger.debug("Failed to delete storage key %s: %s", key, exc, exc_info=exc)


def _after_commit_cleanup(session: Session) -> None:
    _cleanup_storage_keys(session, delete_files=False)


def _after_rollback_cleanup(session: Session) -> None:
    _cleanup_storage_keys(session, delete_files=True)


def register_storage_cleanup_on_rollback(db: Session, storage_key: str) -> None:
    """Delete stored files if the enclosing transaction rolls back."""
    keys = db.info.setdefault("storage_cleanup_keys", set())
    keys.add(storage_key)
    if db.info.get("storage_cleanup_listener"):
        return
    db.info["storage_cleanup_listener"] = True
    event.listen(db, "after_commit", _after_commit_cleanup, once=True)
    event.listen(db, "after_rollback", _after_rollback_cleanup, once=True)


# =============================================================================
# Service Functions
# =============================================================================


def upload_attachment(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content_type: str,
    file: BinaryIO,
    file_size: int,
    surrogate_id: uuid.UUID | None = None,
    intended_parent_id: uuid.UUID | None = None,
    allowed_extensions: set[str] | None = None,
    allowed_mime_types: set[str] | None = None,
) -> Attachment:
    """
    Upload and store an attachment.

    File is scanned asynchronously; only infected/failed scans are quarantined.
    Either surrogate_id or intended_parent_id should be provided.
    """
    # Validate
    is_valid, error = validate_file(
        filename,
        content_type,
        file_size,
        allowed_extensions=allowed_extensions,
        allowed_mime_types=allowed_mime_types,
    )
    if not is_valid:
        raise ValueError(error)

    scan_enabled = getattr(settings, "ATTACHMENT_SCAN_ENABLED", False)

    head = _read_file_prefix(file, 8)
    if head.startswith(_EXECUTABLE_SIGNATURE_PREFIXES):
        raise ValueError("Executable files are not allowed")

    # Calculate checksum
    checksum = calculate_checksum(file)

    # Strip EXIF data from images for privacy
    processed_file = strip_exif_data(file, content_type)

    # Generate storage key
    attachment_id = uuid.uuid4()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    entity_id = surrogate_id or intended_parent_id
    storage_key = f"{org_id}/{entity_id}/{attachment_id}.{ext}"

    # Store file
    try:
        store_file(storage_key, processed_file)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to callers
        logger.exception("Failed to store attachment for key %s", storage_key)
        raise AttachmentStorageError("Failed to store attachment. Please try again.") from exc
    register_storage_cleanup_on_rollback(db, storage_key)

    # Create record
    attachment = Attachment(
        id=attachment_id,
        organization_id=org_id,
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        uploaded_by_user_id=user_id,
        filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=False,
    )
    db.add(attachment)

    # Audit log
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.ATTACHMENT_UPLOADED,
        actor_user_id=user_id,
        target_type="attachment",
        target_id=attachment_id,
        details={
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "intended_parent_id": str(intended_parent_id) if intended_parent_id else None,
            "file_ext": ext,
            "file_size": file_size,
        },
    )

    db.flush()

    # Enqueue virus scan job if scanning is enabled
    if scan_enabled:
        job_service.enqueue_job(
            db=db,
            org_id=org_id,
            job_type=JobType.ATTACHMENT_SCAN,
            payload={"attachment_id": str(attachment_id)},
            run_at=datetime.now(timezone.utc),
            commit=False,
        )

    return attachment


def list_attachments(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID | None = None,
    intended_parent_id: uuid.UUID | None = None,
    include_quarantined: bool = False,
    content_type_prefix: str | None = None,
) -> list[Attachment]:
    """List attachments for a case or intended parent (excludes deleted).

    Args:
        content_type_prefix: Filter by content type prefix (e.g., "image/" for all images)
    """
    query = db.query(Attachment).filter(
        Attachment.organization_id == org_id,
        Attachment.deleted_at.is_(None),
    )

    if surrogate_id:
        query = query.filter(Attachment.surrogate_id == surrogate_id)
    elif intended_parent_id:
        query = query.filter(Attachment.intended_parent_id == intended_parent_id)

    if not include_quarantined:
        query = query.filter(Attachment.scan_status.notin_(["infected", "error"]))

    if content_type_prefix:
        query = query.filter(Attachment.content_type.startswith(content_type_prefix))

    return query.order_by(Attachment.created_at.desc()).all()


def get_attachment(
    db: Session,
    org_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> Attachment | None:
    """Get single attachment by ID."""
    return (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == org_id,
            Attachment.id == attachment_id,
            Attachment.deleted_at.is_(None),
        )
        .first()
    )


def get_attachment_by_storage_key(
    db: Session,
    org_id: uuid.UUID,
    storage_key: str,
) -> Attachment | None:
    """Get attachment by storage key (org-scoped)."""
    return (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == org_id,
            Attachment.storage_key == storage_key,
            Attachment.deleted_at.is_(None),
        )
        .first()
    )


def get_download_url(
    db: Session,
    org_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """Get signed download URL and log access."""
    attachment = get_attachment(db, org_id, attachment_id)
    if not attachment or attachment.scan_status in ("infected", "error"):
        return None
    if getattr(settings, "ATTACHMENT_SCAN_ENABLED", False) and attachment.scan_status != "clean":
        return None

    # Audit log
    ext = attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.ATTACHMENT_DOWNLOADED,
        actor_user_id=user_id,
        target_type="attachment",
        target_id=attachment_id,
        details={
            "surrogate_id": str(attachment.surrogate_id) if attachment.surrogate_id else None,
            "intended_parent_id": str(attachment.intended_parent_id)
            if attachment.intended_parent_id
            else None,
            "file_ext": ext,
            "file_size": attachment.file_size,
        },
    )
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

    attachment.deleted_at = datetime.now(timezone.utc)
    attachment.deleted_by_user_id = user_id

    # Audit log
    ext = attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.ATTACHMENT_DELETED,
        actor_user_id=user_id,
        target_type="attachment",
        target_id=attachment_id,
        details={
            "surrogate_id": str(attachment.surrogate_id) if attachment.surrogate_id else None,
            "file_ext": ext,
            "file_size": attachment.file_size,
        },
    )

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
    attachment.scanned_at = datetime.now(timezone.utc)

    if scan_result == "clean":
        attachment.quarantined = False
        # Trigger workflow after scan passes (document is now accessible)
        from app.services.workflow_triggers import trigger_document_uploaded

        db.flush()  # Ensure attachment is saved before trigger
        trigger_document_uploaded(db, attachment)
    else:
        attachment.quarantined = True

    db.flush()
