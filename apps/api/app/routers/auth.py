"""Authentication router with Google OAuth and session management."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
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
from app.schemas.auth import MeResponse, UserSession
from app.services.auth_service import resolve_user_and_create_session
from app.services import org_service, user_service
from app.services.google_oauth import (
    exchange_code_for_tokens,
    validate_email_domain,
    verify_id_token,
)

# Rate limiting
from app.core.rate_limit import limiter

router = APIRouter()

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_MAX_AGE = 300  # 5 minutes


# =============================================================================
# OAuth Endpoints
# =============================================================================


@router.get("/google/login")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
def google_login(request: Request, login_hint: str | None = None):
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
    if login_hint and "@" in login_hint:
        params["login_hint"] = login_hint
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    )

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
        url=_get_error_redirect("auth_failed"), status_code=302
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
        error_response.headers["location"] = _get_error_redirect(
            "token_exchange_failed"
        )
        return error_response

    # Verify ID token
    try:
        google_user = verify_id_token(
            tokens["id_token"], expected_nonce=stored_payload["nonce"]
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
    session_token, error_code = resolve_user_and_create_session(
        db, google_user, request=request
    )

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

    Returns user profile, organization details, role, and MFA status.
    Used by frontend to bootstrap auth state on page load.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)

    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        org_id=org.id,
        org_name=org.name,
        org_slug=org.slug,
        org_timezone=org.timezone,
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
        mfa_enabled=user.mfa_enabled,
        mfa_required=session.mfa_required,
        mfa_verified=session.mfa_verified,
    )


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None


@router.patch("/me", dependencies=[Depends(require_csrf_header)])
def update_me(
    body: UpdateProfileRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> MeResponse:
    """
    Update current user's profile.

    Updateable fields: display_name
    """
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)
    user = user_service.update_user_profile(
        db,
        session.user_id,
        display_name=body.display_name,
    )

    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        org_id=org.id,
        org_name=org.name,
        org_slug=org.slug,
        org_timezone=org.timezone,
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
    )


# =============================================================================
# Email Signature (User Social Links Only)
# =============================================================================

import re
from urllib.parse import urlparse
from pydantic import field_validator
from app.services import signature_template_service

# URL validation pattern
HTTPS_URL_PATTERN = re.compile(r"^https://")


class UserSignatureResponse(BaseModel):
    """User signature social links and org branding preview."""

    # User-editable social links
    signature_linkedin: str | None = None
    signature_twitter: str | None = None
    signature_instagram: str | None = None

    # Org branding (read-only for users)
    org_signature_template: str | None = None
    org_signature_logo_url: str | None = None
    org_signature_primary_color: str | None = None
    org_signature_company_name: str | None = None
    org_signature_address: str | None = None
    org_signature_phone: str | None = None
    org_signature_website: str | None = None


class UserSignatureUpdate(BaseModel):
    """Update user social links only - org branding fields are ignored."""

    signature_linkedin: str | None = None
    signature_twitter: str | None = None
    signature_instagram: str | None = None

    @field_validator("signature_linkedin", "signature_twitter", "signature_instagram")
    @classmethod
    def validate_social_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v.strip() != v:
            raise ValueError("Social links must be a valid https:// URL")
        if any(char.isspace() for char in v):
            raise ValueError("Social links must be a valid https:// URL")
        if any(char in v for char in ['"', "'", "<", ">"]):
            raise ValueError("Social links must be a valid https:// URL")
        if not HTTPS_URL_PATTERN.match(v):
            raise ValueError("Social links must start with https://")
        parsed = urlparse(v)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Social links must be a valid https:// URL")
        return v


class SignaturePreviewResponse(BaseModel):
    """Rendered signature HTML preview."""

    html: str


@router.get("/me/signature", response_model=UserSignatureResponse)
def get_my_signature(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> UserSignatureResponse:
    """Get current user's signature social links and org branding."""
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)

    return UserSignatureResponse(
        # User social links
        signature_linkedin=user.signature_linkedin,
        signature_twitter=user.signature_twitter,
        signature_instagram=user.signature_instagram,
        # Org branding (read-only)
        org_signature_template=org.signature_template if org else None,
        org_signature_logo_url=org.signature_logo_url if org else None,
        org_signature_primary_color=org.signature_primary_color if org else None,
        org_signature_company_name=org.signature_company_name if org else None,
        org_signature_address=org.signature_address if org else None,
        org_signature_phone=org.signature_phone if org else None,
        org_signature_website=org.signature_website if org else None,
    )


@router.patch(
    "/me/signature",
    response_model=UserSignatureResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_my_signature(
    body: UserSignatureUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> UserSignatureResponse:
    """
    Update user's signature social links.

    Only social links can be updated - org branding is controlled by admins.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)

    # Update social links only
    if body.signature_linkedin is not None:
        user.signature_linkedin = body.signature_linkedin if body.signature_linkedin else None
    if body.signature_twitter is not None:
        user.signature_twitter = body.signature_twitter if body.signature_twitter else None
    if body.signature_instagram is not None:
        user.signature_instagram = body.signature_instagram if body.signature_instagram else None

    db.commit()

    return UserSignatureResponse(
        signature_linkedin=user.signature_linkedin,
        signature_twitter=user.signature_twitter,
        signature_instagram=user.signature_instagram,
        org_signature_template=org.signature_template if org else None,
        org_signature_logo_url=org.signature_logo_url if org else None,
        org_signature_primary_color=org.signature_primary_color if org else None,
        org_signature_company_name=org.signature_company_name if org else None,
        org_signature_address=org.signature_address if org else None,
        org_signature_phone=org.signature_phone if org else None,
        org_signature_website=org.signature_website if org else None,
    )


@router.get("/me/signature/preview", response_model=SignaturePreviewResponse)
def get_my_signature_preview(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> SignaturePreviewResponse:
    """
    Get rendered HTML preview of user's email signature.

    Uses org branding + user profile + user social links.
    This is the same HTML that would be appended to outgoing emails.
    """
    html = signature_template_service.render_signature_html(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
    )

    return SignaturePreviewResponse(html=html)


@router.post("/logout", dependencies=[Depends(require_csrf_header)])
def logout(
    request: Request,
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Clear session cookie and log logout event.

    Requires X-Requested-With header for CSRF protection.
    """
    # Audit log before clearing cookie
    from app.services import audit_service

    audit_service.log_logout(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        request=request,
    )
    db.commit()

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
