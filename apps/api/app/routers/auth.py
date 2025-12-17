"""Authentication router with Google OAuth and session management."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import COOKIE_NAME, get_current_session, get_db, require_csrf_header
from app.core.security import (
    create_oauth_state_payload,
    generate_oauth_nonce,
    generate_oauth_state,
    parse_oauth_state_payload,
    verify_oauth_state,
)
from app.db.models import Organization, User
from app.schemas.auth import MeResponse, UserSession
from app.services.auth_service import resolve_user_and_create_session
from app.services.google_oauth import (
    exchange_code_for_tokens,
    validate_email_domain,
    verify_id_token,
)

router = APIRouter()

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_MAX_AGE = 300  # 5 minutes


# =============================================================================
# OAuth Endpoints
# =============================================================================

@router.get("/google/login")
def google_login(request: Request):
    """
    Initiate Google OAuth flow.
    
    1. Generates cryptographic state and nonce
    2. Stores them in a short-lived cookie (with user-agent binding)
    3. Redirects to Google's authorization endpoint
    
    The state prevents CSRF attacks.
    The nonce prevents replay attacks (verified in ID token).
    User-agent binding adds another layer of protection.
    """
    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    user_agent = request.headers.get("user-agent", "")
    
    state_payload = create_oauth_state_payload(state, nonce, user_agent)
    
    # Build Google auth URL
    # Note: We skip access_type=offline and prompt=consent since we only
    # need login, not refresh tokens. This reduces friction.
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    response = RedirectResponse(url=google_auth_url, status_code=302)
    
    # Set state cookie with Path=/auth to match router mount
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state_payload,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/auth",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    
    Flow:
    1. Validate state cookie (CSRF + user-agent binding)
    2. Exchange code for tokens
    3. Verify ID token (signature, claims, nonce)
    4. Validate email domain if restricted
    5. Find existing user or create from invite
    6. Set session cookie and redirect
    """
    # Prepare error response (always cleans up state cookie)
    error_response = RedirectResponse(
        url=_get_error_redirect("auth_failed"), 
        status_code=302
    )
    error_response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    
    # Check for error from Google
    if error:
        error_response.headers["location"] = _get_error_redirect(f"google_{error}")
        return error_response
    
    if not code or not state:
        error_response.headers["location"] = _get_error_redirect("missing_params")
        return error_response
    
    # Get state cookie
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie:
        error_response.headers["location"] = _get_error_redirect("state_expired")
        return error_response
    
    # Parse and verify state
    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
    except Exception:
        error_response.headers["location"] = _get_error_redirect("invalid_state")
        return error_response
    
    user_agent = request.headers.get("user-agent", "")
    valid, _ = verify_oauth_state(stored_payload, state, user_agent)
    if not valid:
        error_response.headers["location"] = _get_error_redirect("state_mismatch")
        return error_response
    
    # Exchange code for tokens
    try:
        tokens = await exchange_code_for_tokens(code)
    except Exception:
        error_response.headers["location"] = _get_error_redirect("token_exchange_failed")
        return error_response
    
    # Verify ID token
    try:
        google_user = verify_id_token(
            tokens["id_token"], 
            expected_nonce=stored_payload["nonce"]
        )
    except ValueError:
        error_response.headers["location"] = _get_error_redirect("token_invalid")
        return error_response
    
    # Validate domain restriction
    try:
        validate_email_domain(google_user.email)
    except ValueError:
        error_response.headers["location"] = _get_error_redirect("domain_not_allowed")
        return error_response
    
    # Resolve user and create session (delegated to service layer)
    session_token, error_code = resolve_user_and_create_session(db, google_user)
    
    if error_code:
        error_response.headers["location"] = _get_error_redirect(error_code)
        return error_response
    
    # Success! Set session cookie and redirect
    success_response = RedirectResponse(url=_get_success_redirect(), status_code=302)
    success_response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    success_response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return success_response


# =============================================================================
# Session Endpoints
# =============================================================================

@router.get("/me")
def get_me(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> MeResponse:
    """
    Get current authenticated user info.
    
    Returns user profile, organization details, and role.
    Used by frontend to bootstrap auth state on page load.
    """
    user = db.query(User).filter(User.id == session.user_id).first()
    org = db.query(Organization).filter(Organization.id == session.org_id).first()
    
    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        org_id=org.id,
        org_name=org.name,
        org_slug=org.slug,
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
    )


@router.post("/logout", dependencies=[Depends(require_csrf_header)])
def logout(response: Response):
    """
    Clear session cookie.
    
    Requires X-Requested-With header for CSRF protection.
    """
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


# =============================================================================
# Helper Functions
# =============================================================================

def _get_success_redirect() -> str:
    """Safe success redirect URL - fixed path, no user input."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/dashboard"


def _get_error_redirect(error_code: str) -> str:
    """Safe error redirect URL - fixed path with error code."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/login?error={error_code}"
