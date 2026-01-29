"""Shared helpers for worker job handlers."""

from __future__ import annotations

from urllib.parse import urlsplit


def mask_email(email: str | None) -> str:
    if not email:
        return ""
    try:
        from app.services import audit_service

        return audit_service.hash_email(email)
    except Exception:
        local, _, domain = email.partition("@")
        prefix = local[:3] if local else ""
        return f"{prefix}...@{domain}" if domain else f"{prefix}..."


def safe_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"
