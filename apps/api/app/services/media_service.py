"""Helpers for signing media URLs stored in S3."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from app.core.config import settings
from app.services import attachment_service, storage_url_service

if TYPE_CHECKING:
    from app.db.models import Organization

MEDIA_SIGNED_URL_TTL_SECONDS = 60 * 60 * 24  # 24 hours
LOCAL_LOGO_URL_PREFIX = "/settings/organization/signature/logo/local/"


def _prefix_api_base(path: str) -> str:
    if not path.startswith("/"):
        return path
    base = (settings.API_BASE_URL or "").rstrip("/")
    if not base:
        return path
    return f"{base}{path}"


def _extract_s3_key(url: str) -> str | None:
    bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
    return storage_url_service.extract_storage_key(url, bucket)


def get_signed_media_url(url: str | None, expires_in_seconds: int | None = None) -> str | None:
    """Return signed URL for S3-hosted media; otherwise return original."""
    if not url:
        return None

    if url.startswith("/static/"):
        storage_key = url.replace("/static/", "", 1)
        return _prefix_api_base(f"{LOCAL_LOGO_URL_PREFIX}{storage_key}")
    if url.startswith(LOCAL_LOGO_URL_PREFIX):
        return _prefix_api_base(url)
    if url.startswith("/attachments/local/"):
        return url

    storage_key = _extract_s3_key(url)
    if not storage_key:
        return url

    expires_in = expires_in_seconds or MEDIA_SIGNED_URL_TTL_SECONDS
    signed_url = attachment_service.generate_signed_url(storage_key, expires_in)
    return signed_url or None


def email_logo_url(org: Organization | None) -> str:
    """Return a logo URL for sent email that never expires.

    A presigned storage URL expires after a day, and mail clients load images when the
    recipient opens the message. The public route signs a fresh URL on each request.
    The version changes when the logo changes, so image proxies do not serve a stale copy.
    """
    if not org or not org.signature_logo_url:
        return ""
    version = hashlib.sha256(org.signature_logo_url.encode()).hexdigest()[:12]
    return _prefix_api_base(f"/forms/public/{org.id}/signature-logo?v={version}")
