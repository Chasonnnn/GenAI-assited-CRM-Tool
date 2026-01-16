"""Helpers for signing media URLs stored in S3."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services import attachment_service


MEDIA_SIGNED_URL_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def _extract_s3_key(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc
    if not host:
        return None

    bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
    path = parsed.path.lstrip("/")

    # Virtual-hosted style: <bucket>.s3.amazonaws.com/<key>
    if host.startswith(f"{bucket}.s3"):
        return path

    # Path style: s3.amazonaws.com/<bucket>/<key>
    if host == "s3.amazonaws.com" or host.startswith("s3."):
        if path.startswith(f"{bucket}/"):
            return path[len(bucket) + 1 :]

    return None


def get_signed_media_url(url: Optional[str], expires_in_seconds: Optional[int] = None) -> Optional[str]:
    """Return signed URL for S3-hosted media; otherwise return original."""
    if not url:
        return None

    if url.startswith("/static/") or url.startswith("/attachments/local/"):
        return url

    storage_key = _extract_s3_key(url)
    if not storage_key:
        return url

    expires_in = expires_in_seconds or MEDIA_SIGNED_URL_TTL_SECONDS
    signed_url = attachment_service.generate_signed_url(storage_key, expires_in)
    return signed_url or None
