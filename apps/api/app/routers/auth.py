"""Authentication router with Google OAuth and session management."""

import io
import logging
import re
from urllib.parse import urlencode, urlparse
from uuid import UUID as UUIDType

import boto3
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from PIL import Image
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import COOKIE_NAME, get_current_session, get_db, require_csrf_header
from app.core.csrf import CSRF_COOKIE_NAME, set_csrf_cookie
from app.core.rate_limit import limiter
from app.core.security import (
    create_oauth_state_payload,
    decode_session_token,
    generate_oauth_nonce,
    generate_oauth_state,
    parse_oauth_state_payload,
    verify_oauth_state,
)
from app.schemas.auth import MeResponse, SessionResponse, UserSession
from app.services import (
    media_service,
    org_service,
    session_service,
    signature_template_service,
    user_service,
)
from app.services.auth_service import resolve_user_and_create_session
from app.services.google_oauth import (
    exchange_code_for_tokens,
    validate_email_domain,
    verify_id_token,
)

router = APIRouter()
logger = logging.getLogger(__name__)

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
    error_response = RedirectResponse(url=_get_error_redirect("auth_failed"), status_code=302)
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
        google_user = verify_id_token(tokens["id_token"], expected_nonce=stored_payload["nonce"])
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
    session_token, error_code = resolve_user_and_create_session(db, google_user, request=request)

    if error_code:
        error_response.headers["location"] = _get_error_redirect(error_code)
        return error_response

    # Success! Set session cookie and redirect
    base_url = None
    try:
        payload = decode_session_token(session_token)
        org_id = payload.get("org_id")
        if org_id:
            org = org_service.get_org_by_id(db, UUIDType(str(org_id)))
            base_url = org_service.get_org_portal_base_url(org)
    except Exception:
        base_url = None
    success_response = RedirectResponse(url=_get_success_redirect(base_url), status_code=302)
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
    set_csrf_cookie(success_response)
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
        avatar_url=media_service.get_signed_media_url(user.avatar_url),
        phone=user.phone,
        title=user.title,
        org_id=org.id,
        org_name=org.name,
        org_slug=org.slug,
        org_timezone=org.timezone,
        org_portal_domain=org.portal_domain if org else None,
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
        mfa_enabled=user.mfa_enabled,
        mfa_required=session.mfa_required,
        mfa_verified=session.mfa_verified,
    )


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    title: str | None = None


@router.patch("/me", dependencies=[Depends(require_csrf_header)])
def update_me(
    body: UpdateProfileRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> MeResponse:
    """
    Update current user's profile.

    Updateable fields: display_name, phone, title
    """
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)
    user = user_service.update_user_profile(
        db,
        session.user_id,
        display_name=body.display_name,
        phone=body.phone,
        title=body.title,
    )

    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=media_service.get_signed_media_url(user.avatar_url),
        phone=user.phone,
        title=user.title,
        org_id=org.id,
        org_name=org.name,
        org_slug=org.slug,
        org_timezone=org.timezone,
        org_portal_domain=org.portal_domain if org else None,
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
        mfa_enabled=user.mfa_enabled,
        mfa_required=session.mfa_required,
        mfa_verified=session.mfa_verified,
    )


# =============================================================================
# Sessions Management
# =============================================================================


@router.get("/me/sessions", response_model=list[SessionResponse])
def list_my_sessions(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    """
    List all active sessions for the current user.

    Returns session info with is_current flag to identify which session
    belongs to the current request.
    """
    sessions = session_service.list_user_sessions(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        current_token_hash=session.token_hash,
    )
    return [SessionResponse(**s) for s in sessions]


@router.delete(
    "/me/sessions/{session_id}",
    dependencies=[Depends(require_csrf_header)],
)
def revoke_session(
    session_id: UUIDType,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Revoke a specific session (logout that device).

    Cannot revoke the current session - use /logout instead.
    """
    # Check if trying to revoke current session
    target_session = session_service.get_session_by_token_hash(db, session.token_hash or "")
    if target_session and target_session.id == session_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot revoke current session. Use /logout instead.",
        )

    success = session_service.revoke_session(
        db=db,
        session_id=session_id,
        user_id=session.user_id,
        org_id=session.org_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "revoked"}


@router.delete(
    "/me/sessions",
    dependencies=[Depends(require_csrf_header)],
)
def revoke_all_sessions(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Revoke all other sessions (logout all other devices).

    Keeps the current session active.
    """
    count = session_service.revoke_all_user_sessions(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        except_token_hash=session.token_hash,
    )

    return {"status": "revoked", "count": count}


# =============================================================================
# Avatar Upload
# =============================================================================

AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
AVATAR_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
AVATAR_MAX_DIMENSION = 400


def _resize_avatar(file_content: bytes, content_type: str) -> bytes:
    """Resize avatar to max 400x400, maintaining aspect ratio."""
    img = Image.open(io.BytesIO(file_content))

    # Convert to RGB if needed (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if needed
    if img.width > AVATAR_MAX_DIMENSION or img.height > AVATAR_MAX_DIMENSION:
        img.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION), Image.Resampling.LANCZOS)

    # Save to bytes
    output = io.BytesIO()
    format_map = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
    img_format = format_map.get(content_type, "JPEG")
    img.save(output, format=img_format, quality=90)
    output.seek(0)
    return output.read()


def _delete_old_avatar(avatar_url: str):
    """Background task to delete old avatar from S3."""
    if not avatar_url or "avatars/" not in avatar_url:
        return

    try:
        from app.core.config import settings as app_settings

        # Extract key from URL
        key = avatar_url.split("/avatars/")[-1]
        key = f"avatars/{key}"

        s3 = boto3.client(
            "s3",
            region_name=getattr(app_settings, "S3_REGION", "us-east-1"),
            aws_access_key_id=getattr(app_settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(app_settings, "AWS_SECRET_ACCESS_KEY", None),
        )
        bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass  # Best effort


class AvatarResponse(BaseModel):
    avatar_url: str | None


@router.post(
    "/me/avatar",
    response_model=AvatarResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_avatar(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> AvatarResponse:
    """
    Upload a new avatar image.

    - Max size: 2MB
    - Allowed types: PNG, JPEG, WebP
    - Will be resized to max 400x400
    """
    # Validate content type
    if file.content_type not in AVATAR_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(AVATAR_ALLOWED_TYPES)}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    # Resize image
    try:
        resized_content = _resize_avatar(content, file.content_type)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Upload to S3
    import uuid as uuid_module
    from app.core.config import settings as app_settings

    file_id = str(uuid_module.uuid4())
    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if file.filename and "." in file.filename
        else "jpg"
    )
    key = f"avatars/{session.org_id}/{session.user_id}/{file_id}.{ext}"

    s3 = boto3.client(
        "s3",
        region_name=getattr(app_settings, "S3_REGION", "us-east-1"),
        aws_access_key_id=getattr(app_settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(app_settings, "AWS_SECRET_ACCESS_KEY", None),
    )
    bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=resized_content,
        ContentType=file.content_type,
    )

    # Get public URL
    s3_url_style = getattr(app_settings, "S3_URL_STYLE", "path")
    if s3_url_style == "virtual":
        avatar_url = f"https://{bucket}.s3.amazonaws.com/{key}"
    else:
        avatar_url = f"https://s3.amazonaws.com/{bucket}/{key}"

    # Get old avatar URL for deletion
    user = user_service.get_user_by_id(db, session.user_id)
    old_avatar_url = user.avatar_url

    # Update user record
    user.avatar_url = avatar_url
    db.commit()

    # Delete old avatar in background (safe: upload succeeded, DB updated)
    if old_avatar_url:
        background_tasks.add_task(_delete_old_avatar, old_avatar_url)

    return AvatarResponse(avatar_url=media_service.get_signed_media_url(avatar_url))


@router.delete(
    "/me/avatar",
    response_model=AvatarResponse,
    dependencies=[Depends(require_csrf_header)],
)
def delete_avatar(
    background_tasks: BackgroundTasks,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> AvatarResponse:
    """Delete current user's avatar."""
    user = user_service.get_user_by_id(db, session.user_id)
    old_avatar_url = user.avatar_url

    if not old_avatar_url:
        raise HTTPException(status_code=404, detail="No avatar to delete")

    # Clear avatar URL in DB first
    user.avatar_url = None
    db.commit()

    # Delete from S3 in background
    background_tasks.add_task(_delete_old_avatar, old_avatar_url)

    return AvatarResponse(avatar_url=None)


# =============================================================================
# Email Signature (User Social Links Only)
# =============================================================================

# URL validation pattern
HTTPS_URL_PATTERN = re.compile(r"^https://")


class UserSignatureResponse(BaseModel):
    """User signature overrides, social links, profile defaults, and org branding."""

    # Signature overrides (user-editable, NULL = use profile)
    signature_name: str | None = None
    signature_title: str | None = None
    signature_phone: str | None = None
    signature_photo_url: str | None = None

    # User social links (existing)
    signature_linkedin: str | None = None
    signature_twitter: str | None = None
    signature_instagram: str | None = None

    # Profile defaults (for UI placeholders)
    profile_name: str
    profile_title: str | None = None
    profile_phone: str | None = None
    profile_photo_url: str | None = None

    # Org branding (read-only for users)
    org_signature_template: str | None = None
    org_signature_logo_url: str | None = None
    org_signature_primary_color: str | None = None
    org_signature_company_name: str | None = None
    org_signature_address: str | None = None
    org_signature_phone: str | None = None
    org_signature_website: str | None = None


class UserSignatureUpdate(BaseModel):
    """Update user signature overrides and social links. Photo uses dedicated endpoint."""

    # Signature overrides (NULL = reset to profile default)
    signature_name: str | None = None
    signature_title: str | None = None
    signature_phone: str | None = None
    # NOTE: No signature_photo_url - use POST/DELETE /me/signature/photo

    # Social links (existing)
    signature_linkedin: str | None = None
    signature_twitter: str | None = None
    signature_instagram: str | None = None

    @field_validator("signature_name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if len(v) > 255:
            raise ValueError("Name must be 255 characters or less")
        return v.strip()

    @field_validator("signature_title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if len(v) > 100:
            raise ValueError("Title must be 100 characters or less")
        return v.strip()

    @field_validator("signature_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if len(v) > 50:
            raise ValueError("Phone must be 50 characters or less")
        return v.strip()

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
    """Get user's signature overrides, profile defaults, and org branding."""
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)

    return UserSignatureResponse(
        # Signature overrides (user-editable)
        signature_name=user.signature_name,
        signature_title=user.signature_title,
        signature_phone=user.signature_phone,
        signature_photo_url=media_service.get_signed_media_url(user.signature_photo_url),
        # User social links
        signature_linkedin=user.signature_linkedin,
        signature_twitter=user.signature_twitter,
        signature_instagram=user.signature_instagram,
        # Profile defaults (for UI placeholders)
        profile_name=user.display_name,
        profile_title=user.title,
        profile_phone=user.phone,
        profile_photo_url=media_service.get_signed_media_url(user.avatar_url),
        # Org branding (read-only)
        org_signature_template=org.signature_template if org else None,
        org_signature_logo_url=media_service.get_signed_media_url(
            org.signature_logo_url if org else None
        ),
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
    Update user's signature overrides and social links.

    Signature overrides allow customizing name/title/phone for email signatures
    independent of profile values. Set to empty string to reset to profile default.
    Org branding is read-only and controlled by admins.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    org = org_service.get_org_by_id(db, session.org_id)

    # Track changed fields for audit log (don't log actual values for PII)
    changed_fields: list[str] = []

    # Update signature overrides (empty string → None → use profile default)
    if body.signature_name is not None:
        new_val = body.signature_name if body.signature_name else None
        if user.signature_name != new_val:
            changed_fields.append("signature_name")
        user.signature_name = new_val

    if body.signature_title is not None:
        new_val = body.signature_title if body.signature_title else None
        if user.signature_title != new_val:
            changed_fields.append("signature_title")
        user.signature_title = new_val

    if body.signature_phone is not None:
        new_val = body.signature_phone if body.signature_phone else None
        if user.signature_phone != new_val:
            changed_fields.append("signature_phone")
        user.signature_phone = new_val

    # Update social links
    if body.signature_linkedin is not None:
        new_val = body.signature_linkedin if body.signature_linkedin else None
        if user.signature_linkedin != new_val:
            changed_fields.append("signature_linkedin")
        user.signature_linkedin = new_val

    if body.signature_twitter is not None:
        new_val = body.signature_twitter if body.signature_twitter else None
        if user.signature_twitter != new_val:
            changed_fields.append("signature_twitter")
        user.signature_twitter = new_val

    if body.signature_instagram is not None:
        new_val = body.signature_instagram if body.signature_instagram else None
        if user.signature_instagram != new_val:
            changed_fields.append("signature_instagram")
        user.signature_instagram = new_val

    db.commit()

    # Audit log (fields changed only, no PII values)
    if changed_fields:
        logger.info(
            "Signature updated for user %s: fields=%s",
            session.user_id,
            changed_fields,
        )

    return UserSignatureResponse(
        # Signature overrides
        signature_name=user.signature_name,
        signature_title=user.signature_title,
        signature_phone=user.signature_phone,
        signature_photo_url=media_service.get_signed_media_url(user.signature_photo_url),
        # Social links
        signature_linkedin=user.signature_linkedin,
        signature_twitter=user.signature_twitter,
        signature_instagram=user.signature_instagram,
        # Profile defaults
        profile_name=user.display_name,
        profile_title=user.title,
        profile_phone=user.phone,
        profile_photo_url=media_service.get_signed_media_url(user.avatar_url),
        # Org branding
        org_signature_template=org.signature_template if org else None,
        org_signature_logo_url=media_service.get_signed_media_url(
            org.signature_logo_url if org else None
        ),
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


# =============================================================================
# Signature Photo Upload/Delete
# =============================================================================


class SignaturePhotoResponse(BaseModel):
    """Response for signature photo upload/delete."""

    signature_photo_url: str | None


def _delete_old_signature_photo(photo_url: str):
    """Background task to delete old signature photo from S3."""
    if not photo_url or "signatures/" not in photo_url:
        return

    try:
        from app.core.config import settings as app_settings

        # Extract key from URL
        key = photo_url.split("/signatures/")[-1]
        key = f"signatures/{key}"

        s3 = boto3.client(
            "s3",
            region_name=getattr(app_settings, "S3_REGION", "us-east-1"),
            aws_access_key_id=getattr(app_settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(app_settings, "AWS_SECRET_ACCESS_KEY", None),
        )
        bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass  # Best effort


@router.post(
    "/me/signature/photo",
    response_model=SignaturePhotoResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_signature_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> SignaturePhotoResponse:
    """
    Upload a signature-specific photo (separate from profile avatar).

    - Max size: 2MB
    - Allowed types: PNG, JPEG, WebP
    - Will be resized to max 400x400
    - Falls back to profile avatar if deleted
    """
    # Validate content type
    if file.content_type not in AVATAR_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(AVATAR_ALLOWED_TYPES)}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    # Resize image (re-use avatar resize logic)
    try:
        resized_content = _resize_avatar(content, file.content_type)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Upload to S3 under signatures/ prefix
    import uuid as uuid_module
    from app.core.config import settings as app_settings

    file_id = str(uuid_module.uuid4())
    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if file.filename and "." in file.filename
        else "jpg"
    )
    key = f"signatures/{session.org_id}/{session.user_id}/{file_id}.{ext}"

    s3 = boto3.client(
        "s3",
        region_name=getattr(app_settings, "S3_REGION", "us-east-1"),
        aws_access_key_id=getattr(app_settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(app_settings, "AWS_SECRET_ACCESS_KEY", None),
    )
    bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=resized_content,
        ContentType=file.content_type,
    )

    # Get public URL
    s3_url_style = getattr(app_settings, "S3_URL_STYLE", "path")
    if s3_url_style == "virtual":
        photo_url = f"https://{bucket}.s3.amazonaws.com/{key}"
    else:
        photo_url = f"https://s3.amazonaws.com/{bucket}/{key}"

    # Get old photo URL for deletion
    user = user_service.get_user_by_id(db, session.user_id)
    old_photo_url = user.signature_photo_url

    # Update user record
    user.signature_photo_url = photo_url
    db.commit()

    # Delete old photo in background (safe: upload succeeded, DB updated)
    if old_photo_url:
        background_tasks.add_task(_delete_old_signature_photo, old_photo_url)

    logger.info("Signature photo uploaded for user %s", session.user_id)

    return SignaturePhotoResponse(
        signature_photo_url=media_service.get_signed_media_url(photo_url)
    )


@router.delete(
    "/me/signature/photo",
    response_model=SignaturePhotoResponse,
    dependencies=[Depends(require_csrf_header)],
)
def delete_signature_photo(
    background_tasks: BackgroundTasks,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> SignaturePhotoResponse:
    """
    Delete signature photo (falls back to profile avatar).

    Sets signature_photo_url to NULL, so signature rendering
    will use the user's profile avatar instead.
    """
    user = user_service.get_user_by_id(db, session.user_id)
    old_photo_url = user.signature_photo_url

    if not old_photo_url:
        raise HTTPException(status_code=404, detail="No signature photo to delete")

    # Clear photo URL in DB first
    user.signature_photo_url = None
    db.commit()

    # Delete from S3 in background
    background_tasks.add_task(_delete_old_signature_photo, old_photo_url)

    logger.info("Signature photo deleted for user %s", session.user_id)

    return SignaturePhotoResponse(signature_photo_url=None)


@router.post("/logout", dependencies=[Depends(require_csrf_header)])
def logout(
    request: Request,
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Clear session cookie, delete session from DB, and log logout event.

    Requires X-CSRF-Token header for CSRF protection.
    """
    # Delete session from database (enables revocation)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session_service.delete_session_by_token(db, token)

    # Audit log
    from app.services import audit_service

    audit_service.log_logout(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        request=request,
    )
    db.commit()

    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_success_redirect(base_url: str | None = None) -> str:
    """Safe success redirect URL - fixed path, no user input."""
    base = base_url or settings.FRONTEND_URL.rstrip("/")
    return f"{base}/dashboard"


def _get_error_redirect(error_code: str, base_url: str | None = None) -> str:
    """Safe error redirect URL - fixed path with error code."""
    base = base_url or settings.FRONTEND_URL.rstrip("/")
    return f"{base}/login?error={error_code}"
