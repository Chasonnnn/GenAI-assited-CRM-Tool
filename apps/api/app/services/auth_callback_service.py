"""Google OAuth callback orchestration service."""

from __future__ import annotations

from uuid import UUID as UUIDType

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, set_csrf_cookie
from app.core.deps import COOKIE_NAME
from app.core.security import (
    decode_session_token,
    parse_oauth_state_payload,
    verify_oauth_state,
)
from app.services import org_service
from app.services.auth_service import resolve_user_and_create_session
from app.services.google_oauth import (
    exchange_code_for_tokens,
    validate_email_domain,
    verify_id_token,
)

OAUTH_STATE_COOKIE = "oauth_state"
ALLOWED_RETURN_TO = {"app", "ops"}


def get_success_redirect(
    base_url: str | None = None,
    return_to: str = "app",
    mfa_pending: bool = False,
) -> str:
    """Compute a safe post-auth success redirect."""
    if return_to == "ops":
        base = (base_url or "").rstrip("/")
        if not base and settings.PLATFORM_BASE_DOMAIN:
            base = f"https://ops.{settings.PLATFORM_BASE_DOMAIN}"
        if not base and settings.is_dev and settings.FRONTEND_URL:
            base = settings.FRONTEND_URL.rstrip("/")
    else:
        base = (base_url or settings.FRONTEND_URL or "").rstrip("/")
    if return_to == "ops" and not base and settings.PLATFORM_BASE_DOMAIN:
        base = f"https://ops.{settings.PLATFORM_BASE_DOMAIN}"

    def _join(path: str) -> str:
        return f"{base}{path}" if base else path

    if mfa_pending:
        if return_to == "ops":
            return _join("/mfa?return_to=ops")
        return _join("/mfa")

    if return_to == "ops":
        return _join("/ops")
    return _join("/dashboard")


def get_error_redirect(
    error_code: str,
    base_url: str | None = None,
    return_to: str = "app",
) -> str:
    """Compute a safe post-auth error redirect."""
    if return_to == "ops":
        base = (base_url or "").rstrip("/")
        if not base and settings.PLATFORM_BASE_DOMAIN:
            base = f"https://ops.{settings.PLATFORM_BASE_DOMAIN}"
        if not base and settings.is_dev and settings.FRONTEND_URL:
            base = settings.FRONTEND_URL.rstrip("/")
    else:
        base = (base_url or settings.FRONTEND_URL or "").rstrip("/")
    if return_to == "ops" and not base and settings.PLATFORM_BASE_DOMAIN:
        base = f"https://ops.{settings.PLATFORM_BASE_DOMAIN}"

    def _join(path: str) -> str:
        return f"{base}{path}" if base else path

    if return_to == "ops":
        return _join(f"/ops/login?error={error_code}")
    return _join(f"/login?error={error_code}")


def _error_response(error_code: str, return_to: str) -> RedirectResponse:
    response = RedirectResponse(
        url=get_error_redirect(error_code, return_to=return_to),
        status_code=302,
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    return response


async def handle_google_callback(
    request: Request,
    db: Session,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
) -> RedirectResponse:
    """Handle full Google OAuth callback flow and return a redirect response."""
    return_to = "app"

    if error:
        return _error_response(f"google_{error}", return_to=return_to)

    if not code or not state:
        return _error_response("missing_params", return_to=return_to)

    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie:
        return _error_response("state_expired", return_to=return_to)

    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
        return_to = stored_payload.get("return_to", "app")
        if return_to not in ALLOWED_RETURN_TO:
            return_to = "app"
    except Exception:
        return _error_response("invalid_state", return_to=return_to)

    user_agent = request.headers.get("user-agent", "")
    valid, _ = verify_oauth_state(stored_payload, state, user_agent)
    if not valid:
        return _error_response("state_mismatch", return_to=return_to)

    try:
        tokens = await exchange_code_for_tokens(code)
    except Exception:
        return _error_response("token_exchange_failed", return_to=return_to)

    try:
        google_user = verify_id_token(tokens["id_token"], expected_nonce=stored_payload["nonce"])
    except ValueError:
        return _error_response("token_invalid", return_to=return_to)

    try:
        validate_email_domain(google_user.email)
    except ValueError:
        return _error_response("domain_not_allowed", return_to=return_to)

    session_token, error_code = resolve_user_and_create_session(db, google_user, request=request)
    if error_code:
        return _error_response(error_code, return_to=return_to)

    base_url = None
    mfa_pending = False
    try:
        payload = decode_session_token(session_token)
        mfa_required = bool(payload.get("mfa_required", False))
        mfa_verified = bool(payload.get("mfa_verified", False))
        mfa_pending = mfa_required and not mfa_verified
        if return_to == "ops":
            if settings.is_dev and settings.FRONTEND_URL:
                base_url = settings.FRONTEND_URL.rstrip("/")
            else:
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
                base_url = f"{scheme}://ops.{settings.PLATFORM_BASE_DOMAIN}"
        else:
            org_id = payload.get("org_id")
            if org_id:
                org = org_service.get_org_by_id(db, UUIDType(str(org_id)))
                base_url = org_service.get_org_portal_base_url(org)
    except Exception:
        base_url = None

    success_response = RedirectResponse(
        url=get_success_redirect(base_url, return_to=return_to, mfa_pending=mfa_pending),
        status_code=302,
    )
    success_response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")

    success_response.set_cookie(
        key="auth_return_to",
        value=return_to,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=600,
        httponly=False,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )

    if settings.COOKIE_DOMAIN:
        success_response.delete_cookie(COOKIE_NAME, path="/")
        success_response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    success_response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    set_csrf_cookie(success_response)
    return success_response
