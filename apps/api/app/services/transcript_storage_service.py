"""Transcript storage service - S3 offloading for large transcripts."""

import json
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

# Size threshold for S3 offloading (100KB)
OFFLOAD_THRESHOLD_BYTES = 100 * 1024


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
    path = getattr(settings, "LOCAL_STORAGE_PATH", None)
    if not path:
        path = os.path.join(tempfile.gettempdir(), "crm-transcripts")
    os.makedirs(path, exist_ok=True)
    return path


def _get_bucket() -> str:
    """Get S3 bucket name."""
    return getattr(settings, "S3_BUCKET", "crm-attachments")


# =============================================================================
# Offloading Logic
# =============================================================================


def should_offload(html_content: str) -> bool:
    """Check if HTML content should be offloaded to S3."""
    if not html_content:
        return False
    return len(html_content.encode("utf-8")) > OFFLOAD_THRESHOLD_BYTES


def store_transcript(
    interview_id: UUID,
    version: int,
    html_content: str | None,
    text_content: str | None,
) -> tuple[str | None, str | None, str | None]:
    """
    Store transcript content, offloading to S3 if large.

    Args:
        interview_id: The interview UUID
        version: The version number
        html_content: The HTML content (may be offloaded)
        text_content: The plaintext content (always stored inline for search)

    Returns:
        Tuple of (html_in_db, text_in_db, storage_key)
        - html_in_db: HTML content if inline, None if offloaded
        - text_in_db: Plaintext content (always returned for inline storage)
        - storage_key: S3 key if offloaded, None if inline
    """
    if not html_content:
        return None, text_content, None

    if not should_offload(html_content):
        # Store inline
        return html_content, text_content, None

    # Offload to S3
    storage_key = f"transcripts/{interview_id}/v{version}.json"

    content = {
        "html": html_content,
        "text": text_content,
        "version": version,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }

    _upload_file(storage_key, json.dumps(content).encode("utf-8"))

    # Return None for html (offloaded), keep text for search
    return None, text_content, storage_key


def load_transcript(
    html_in_db: str | None,
    text_in_db: str | None,
    storage_key: str | None,
) -> tuple[str | None, str | None]:
    """
    Load transcript content, fetching from S3 if offloaded.

    Args:
        html_in_db: HTML content from database (None if offloaded)
        text_in_db: Text content from database
        storage_key: S3 key if offloaded

    Returns:
        Tuple of (html_content, text_content)
    """
    if storage_key:
        # Fetch from S3
        try:
            content_bytes = _download_file(storage_key)
            content = json.loads(content_bytes)
            return content.get("html"), text_in_db or content.get("text")
        except Exception:
            # Fallback to text if S3 fetch fails
            return None, text_in_db
    else:
        return html_in_db, text_in_db


def delete_transcript(storage_key: str) -> bool:
    """
    Delete offloaded transcript from storage.

    Returns True if deleted, False if not found or error.
    """
    if not storage_key:
        return False

    try:
        _delete_file(storage_key)
        return True
    except Exception:
        return False


# =============================================================================
# Low-level Storage Operations
# =============================================================================


def _upload_file(storage_key: str, content: bytes) -> None:
    """Upload content to storage backend."""
    backend = _get_storage_backend()

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = _get_bucket()
        s3.put_object(
            Bucket=bucket,
            Key=storage_key,
            Body=content,
            ContentType="application/json",
        )
    else:
        # Local storage
        path = os.path.join(_get_local_storage_path(), storage_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)


def _download_file(storage_key: str) -> bytes:
    """Download content from storage backend."""
    backend = _get_storage_backend()

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = _get_bucket()
        try:
            response = s3.get_object(Bucket=bucket, Key=storage_key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Transcript not found: {storage_key}")
            raise
    else:
        # Local storage
        path = os.path.join(_get_local_storage_path(), storage_key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Transcript not found: {storage_key}")
        with open(path, "rb") as f:
            return f.read()


def _delete_file(storage_key: str) -> None:
    """Delete file from storage backend."""
    backend = _get_storage_backend()

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = _get_bucket()
        s3.delete_object(Bucket=bucket, Key=storage_key)
    else:
        # Local storage
        path = os.path.join(_get_local_storage_path(), storage_key)
        if os.path.exists(path):
            os.remove(path)


# =============================================================================
# Cleanup Operations
# =============================================================================


def cleanup_old_versions(
    interview_id: UUID,
    keep_versions: list[int],
) -> int:
    """
    Clean up offloaded versions that are no longer needed.

    Args:
        interview_id: The interview UUID
        keep_versions: List of version numbers to keep

    Returns:
        Number of files deleted
    """
    backend = _get_storage_backend()
    prefix = f"transcripts/{interview_id}/"
    deleted_count = 0

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = _get_bucket()

        try:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                # Extract version from key (e.g., "transcripts/uuid/v3.json" -> 3)
                try:
                    version_str = key.split("/")[-1].replace("v", "").replace(".json", "")
                    version = int(version_str)
                    if version not in keep_versions:
                        s3.delete_object(Bucket=bucket, Key=key)
                        deleted_count += 1
                except (ValueError, IndexError):
                    continue
        except ClientError:
            pass
    else:
        # Local storage
        local_path = os.path.join(_get_local_storage_path(), prefix)
        if os.path.exists(local_path):
            for filename in os.listdir(local_path):
                try:
                    version_str = filename.replace("v", "").replace(".json", "")
                    version = int(version_str)
                    if version not in keep_versions:
                        os.remove(os.path.join(local_path, filename))
                        deleted_count += 1
                except (ValueError, OSError):
                    continue

    return deleted_count
