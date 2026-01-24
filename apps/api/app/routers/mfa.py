"""MFA router - Endpoints for multi-factor authentication management.

Provides:
- MFA status check
- TOTP setup (secret + QR URI)
- TOTP verification and enablement
- Recovery code management
- MFA verification during login
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import COOKIE_NAME, get_current_session, get_db, require_csrf_header
from app.core.csrf import CSRF_COOKIE_NAME, set_csrf_cookie
from app.core.security import create_session_token
from app.schemas.auth import UserSession
from app.services import duo_service, membership_service, mfa_service, user_service


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class MFAStatusResponse(BaseModel):
    """MFA enrollment status."""

    mfa_enabled: bool
    totp_enabled: bool
    totp_enabled_at: str | None
    duo_enabled: bool
    duo_enrolled_at: str | None
    recovery_codes_remaining: int
    mfa_required: bool


class TOTPSetupResponse(BaseModel):
    """TOTP setup data for QR code generation."""

    secret: str
    provisioning_uri: str
    qr_code_data: str  # Same as provisioning_uri (for QR libraries)


class TOTPVerifyRequest(BaseModel):
    """TOTP code verification request."""

    code: str = Field(..., min_length=6, max_length=8)


class TOTPSetupCompleteResponse(BaseModel):
    """TOTP setup completion response with recovery codes."""

    success: bool
    recovery_codes: list[str]
    message: str


class RecoveryCodesResponse(BaseModel):
    """Recovery codes response."""

    codes: list[str]
    count: int


class MFAVerifyRequest(BaseModel):
    """MFA verification during login."""

    code: str = Field(..., min_length=6, max_length=12)


class MFAVerifyResponse(BaseModel):
    """MFA verification result."""

    valid: bool
    method: str | None = None  # "totp" or "recovery"


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=MFAStatusResponse)
def get_mfa_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get MFA enrollment status for the current user."""
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return mfa_service.get_mfa_status(user)


@router.post(
    "/totp/setup",
    response_model=TOTPSetupResponse,
    dependencies=[Depends(require_csrf_header)],
)
def setup_totp(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Start TOTP setup - generates a new secret and provisioning URI.

    Returns data for displaying a QR code in authenticator apps.
    User must verify with a code before TOTP is enabled.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow re-setup if already enabled (must disable first)
    if user.mfa_enabled and user.totp_enabled_at:
        raise HTTPException(
            status_code=400,
            detail="TOTP already enabled. Disable MFA first to reconfigure.",
        )

    secret, uri = mfa_service.setup_totp_for_user(db, user)

    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_data=uri,
    )


@router.post(
    "/totp/verify",
    response_model=TOTPSetupCompleteResponse,
    dependencies=[Depends(require_csrf_header)],
)
def verify_totp_setup(
    body: TOTPVerifyRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Complete TOTP setup by verifying the first code.

    On success:
    - Enables MFA for the user
    - Returns one-time display of recovery codes

    IMPORTANT: Recovery codes are only shown once. User must save them.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.totp_secret:
        raise HTTPException(
            status_code=400,
            detail="No TOTP setup in progress. Call /mfa/totp/setup first.",
        )

    success, recovery_codes = mfa_service.complete_totp_setup(db, user, body.code)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid code. Please try again.")

    return TOTPSetupCompleteResponse(
        success=True,
        recovery_codes=recovery_codes or [],
        message="MFA enabled successfully. Save your recovery codes securely.",
    )


@router.post(
    "/recovery/regenerate",
    response_model=RecoveryCodesResponse,
    dependencies=[Depends(require_csrf_header)],
)
def regenerate_recovery_codes(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Generate new recovery codes, replacing existing ones.

    Requires MFA to be enabled. This invalidates all previous codes.
    Returns plaintext codes for one-time display.
    """
    if session.mfa_required and not session.mfa_verified:
        raise HTTPException(status_code=403, detail="MFA verification required")

    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA must be enabled first")

    codes = mfa_service.regenerate_recovery_codes(db, user)

    return RecoveryCodesResponse(codes=codes, count=len(codes))


@router.post(
    "/verify",
    response_model=MFAVerifyResponse,
    dependencies=[Depends(require_csrf_header)],
)
def verify_mfa_code(
    body: MFAVerifyRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Verify an MFA code (TOTP or recovery).

    This endpoint is used during login flow when MFA challenge is required.
    For recovery codes, the code is consumed (single-use).
    """
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA not enabled for this user")

    is_valid, method = mfa_service.verify_mfa_code(user, body.code)

    if is_valid and method == "recovery":
        # Consume the recovery code
        mfa_service.consume_recovery_code(db, user, body.code)

    return MFAVerifyResponse(valid=is_valid, method=method if is_valid else None)


class MFACompleteResponse(BaseModel):
    """MFA completion response."""

    success: bool
    message: str


@router.post(
    "/complete",
    response_model=MFACompleteResponse,
    dependencies=[Depends(require_csrf_header)],
)
def complete_mfa_challenge(
    body: MFAVerifyRequest,
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Complete MFA challenge and upgrade session.

    On successful MFA verification:
    1. Issues new session token with mfa_verified=True
    2. Sets updated cookie

    Frontend should redirect to dashboard after success.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA not enabled for this user")

    # Verify the code
    is_valid, method = mfa_service.verify_mfa_code(user, body.code)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid MFA code")

    # Consume recovery code if used
    if method == "recovery":
        mfa_service.consume_recovery_code(db, user, body.code)

    # Get membership for new token
    membership = membership_service.get_membership_by_user_id(db, user.id)

    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")

    # Issue new session with mfa_verified=True

    new_token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
        mfa_verified=True,  # Now verified!
        mfa_required=True,
    )

    # Set new cookie
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    response.set_cookie(
        key=COOKIE_NAME,
        value=new_token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    set_csrf_cookie(response)

    return MFACompleteResponse(
        success=True,
        message=f"MFA verified successfully via {method}",
    )


@router.post(
    "/disable",
    dependencies=[Depends(require_csrf_header)],
)
def disable_mfa(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Disable MFA for the current user.

    This removes TOTP secret and recovery codes.
    User can re-enroll later.

    Note: In production, you may want to require password or recovery code
    verification before allowing MFA disable.
    """
    if session.mfa_required and not session.mfa_verified:
        raise HTTPException(status_code=403, detail="MFA verification required")

    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    mfa_service.disable_mfa(db, user)

    return {"message": "MFA disabled successfully"}


# =============================================================================
# Duo Endpoints
# =============================================================================


class DuoStatusResponse(BaseModel):
    """Duo availability status."""

    available: bool
    enrolled: bool
    enrolled_at: str | None = None


class DuoInitiateResponse(BaseModel):
    """Duo auth initiation response."""

    auth_url: str
    state: str


class DuoCallbackRequest(BaseModel):
    """Duo callback verification request."""

    code: str
    state: str


@router.get("/duo/status", response_model=DuoStatusResponse)
def get_duo_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Check if Duo is available and user's enrollment status."""
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return DuoStatusResponse(
        available=duo_service.is_available(),
        enrolled=user.duo_enrolled_at is not None,
        enrolled_at=user.duo_enrolled_at.isoformat() if user.duo_enrolled_at else None,
    )


@router.get("/duo/health")
def duo_health_check():
    """Check Duo API connectivity."""
    is_healthy, message = duo_service.health_check()
    return {"healthy": is_healthy, "message": message}


@router.post(
    "/duo/initiate",
    response_model=DuoInitiateResponse,
    dependencies=[Depends(require_csrf_header)],
)
def initiate_duo_auth(
    request: Request,
    return_to: str | None = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Start Duo authentication flow.

    Returns a URL to redirect the user to for Duo Universal Prompt.
    The state token should be stored in session for verification.
    """
    if not duo_service.is_available():
        raise HTTPException(status_code=503, detail="Duo is not configured")

    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate secure state token for CSRF protection
    state = secrets.token_urlsafe(32)

    allowed_return_to = {"app", "ops"}
    return_to = return_to if return_to in allowed_return_to else None

    if return_to == "ops" and settings.OPS_FRONTEND_URL:
        base_url = settings.OPS_FRONTEND_URL.rstrip("/")
    elif return_to == "app" and settings.FRONTEND_URL:
        base_url = settings.FRONTEND_URL.rstrip("/")
    else:
        host = (request.headers.get("host") or "").lower()
        if host.startswith("ops.") and settings.OPS_FRONTEND_URL:
            base_url = settings.OPS_FRONTEND_URL.rstrip("/")
        elif settings.FRONTEND_URL:
            base_url = settings.FRONTEND_URL.rstrip("/")
        else:
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
            base_url = f"{scheme}://{host}".rstrip("/")

    redirect_uri = f"{base_url}/auth/duo/callback"

    # Create auth URL with user's email
    auth_url = duo_service.create_auth_url(
        user_id=user.id,
        username=user.email,
        state=state,
        redirect_uri=redirect_uri,
    )

    return DuoInitiateResponse(auth_url=auth_url, state=state)


@router.post(
    "/duo/callback",
    dependencies=[Depends(require_csrf_header)],
)
def verify_duo_callback(
    body: DuoCallbackRequest,
    response: Response,
    expected_state: str,  # Should come from session in production
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Verify Duo callback after user completes authentication.

    On success, marks the user as Duo-enrolled and enables MFA.
    """
    if not duo_service.is_available():
        raise HTTPException(status_code=503, detail="Duo is not configured")

    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify the callback
    is_valid, auth_result = duo_service.verify_callback(
        code=body.code,
        state=body.state,
        expected_state=expected_state,
        username=user.email,
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Duo verification failed")

    # Mark user as Duo enrolled and enable MFA
    from datetime import datetime, timezone

    user.duo_enrolled_at = datetime.now(timezone.utc)
    user.duo_user_id = auth_result.get("sub") if auth_result else None

    recovery_codes: list[str] | None = None
    if not user.mfa_enabled:
        user.mfa_enabled = True
        user.mfa_required_at = datetime.now(timezone.utc)

        # Generate recovery codes if not already present
        if not user.mfa_recovery_codes:
            recovery_codes = mfa_service.generate_recovery_codes()
            user.mfa_recovery_codes = mfa_service.hash_recovery_codes(recovery_codes)

    db.commit()

    # Issue new session with mfa_verified=True
    membership = membership_service.get_membership_by_user_id(db, user.id)
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")

    new_token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )

    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    response.set_cookie(
        key=COOKIE_NAME,
        value=new_token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    set_csrf_cookie(response)

    payload = {
        "success": True,
        "message": "Duo authentication successful",
    }
    if recovery_codes:
        payload["recovery_codes"] = recovery_codes
    return payload
