"""Helpers for storage URL handling (public URLs + key extraction)."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings


def _base_host() -> str:
    base = (settings.S3_PUBLIC_BASE_URL or "").rstrip("/")
    if not base:
        return ""
    parsed = urlparse(base)
    return parsed.netloc or base.replace("https://", "").replace("http://", "")


def _base_scheme() -> str:
    base = (settings.S3_PUBLIC_BASE_URL or "").rstrip("/")
    if not base:
        return "https"
    parsed = urlparse(base)
    return parsed.scheme or "https"


def build_public_url(bucket: str, key: str) -> str:
    """Build a public URL for the given bucket/key."""
    base_host = _base_host()
    scheme = _base_scheme()
    style = (settings.S3_URL_STYLE or "path").lower()

    if base_host:
        if style == "virtual":
            return f"{scheme}://{bucket}.{base_host}/{key}"
        return f"{scheme}://{base_host}/{bucket}/{key}"

    if style == "virtual":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://s3.amazonaws.com/{bucket}/{key}"


def extract_storage_key(url: str, bucket: str) -> str | None:
    """Extract storage key from a public URL."""
    parsed = urlparse(url)
    host = parsed.netloc
    if not host:
        return None

    path = parsed.path.lstrip("/")
    base_host = _base_host()
    style = (settings.S3_URL_STYLE or "path").lower()

    if base_host:
        if style == "virtual":
            if host == f"{bucket}.{base_host}":
                return path
        else:
            if host == base_host and path.startswith(f"{bucket}/"):
                return path[len(bucket) + 1 :]

    # AWS fallbacks for legacy URLs
    if host.startswith(f"{bucket}.s3"):
        return path
    if host == "s3.amazonaws.com" or host.startswith("s3."):
        if path.startswith(f"{bucket}/"):
            return path[len(bucket) + 1 :]

    return None
