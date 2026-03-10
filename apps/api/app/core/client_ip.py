"""Helpers for extracting the end-user client IP from requests."""

from fastapi import Request

from app.core.config import settings


def get_client_ip(request: Request | None) -> str | None:
    """Extract the client IP, honoring trusted proxy headers when enabled."""
    if not request:
        return None

    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None
