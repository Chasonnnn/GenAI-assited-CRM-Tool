"""CSRF utilities for double-submit cookie protection."""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request, Response

from app.core.config import settings

CSRF_COOKIE_NAME = "crm_csrf"
CSRF_HEADER = "X-CSRF-Token"


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    return secrets.token_urlsafe(32)


def get_csrf_cookie(request: Request) -> Optional[str]:
    """Fetch CSRF token from cookie."""
    return request.cookies.get(CSRF_COOKIE_NAME)


def set_csrf_cookie(response: Response, token: Optional[str] = None) -> str:
    """Set CSRF cookie and return the token used."""
    csrf_token = token or generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=False,  # Must be readable by JS for X-CSRF-Token header.
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    return csrf_token


def validate_csrf(request: Request) -> bool:
    """Validate CSRF header against cookie."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)
