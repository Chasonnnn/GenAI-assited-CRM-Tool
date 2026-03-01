"""Authentication router with Google OAuth and session management."""

import io
import logging
import re
from urllib.parse import urlencode, urlparse
from uuid import UUID as UUIDType
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
from app.core.csrf import CSRF_COOKIE_NAME
from app.core.rate_limit import limiter
from app.core.security import (
    create_oauth_state_payload,
    generate_oauth_nonce,
    generate_oauth_state,
)
from app.schemas.auth import MeResponse, SessionResponse, UserSession
from app.services import (
    auth_callback_service,
    media_service,
    org_service,
    storage_client,
    storage_url_service,
    session_service,
    signature_template_service,
    user_service,
)
from app.utils.file_upload import content_length_exceeds_limit, get_upload_file_size

router = APIRouter()
logger = logging.getLogger(__name__)

OAUTH_STATE_COOKIE = auth_callback_service.OAUTH_STATE_COOKIE
OAUTH_STATE_MAX_AGE = 300  # 5 minutes

# Allowlist for return_to parameter (prevents open redirect)
ALLOWED_RETURN_TO = auth_callback_service.ALLOWED_RETURN_TO


# =============================================================================
# OAuth Endpoints
# =============================================================================


@router.get("/google/login")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
def google_login(
    request: Request,
    login_hint: str | None = None,
    return_to: str = "app",
):
    """
    Initiate Google OAuth flow.

    1. Generates cryptographic state and nonce
    2. Stores them in a short-lived cookie (with user-agent binding)
    3. Redirects to Google's authorization endpoint

    The state prevents CSRF attacks.
    The nonce prevents replay attacks (verified in ID token).
    User-agent binding adds another layer of protection.

    Args:
        return_to: Target app after auth. Strict allowlist: "app" or "ops".
    """
    # Validate return_to against strict allowlist
    host = request.headers.get("host", "").split(":")[0].lower()
    ops_host = f"ops.{settings.PLATFORM_BASE_DOMAIN}" if settings.PLATFORM_BASE_DOMAIN else ""
    if return_to not in ALLOWED_RETURN_TO:
        return_to = "ops" if host == ops_host else "app"
    elif host == ops_host:
        return_to = "ops"

    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    user_agent = request.headers.get("user-agent", "")

    state_payload = create_oauth_state_payload(state, nonce, user_agent, return_to=return_to)

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
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/auth",
    )
    return response


@router.get("/google/callback")
# Security: Rate limit OAuth callbacks to prevent brute-force attacks and abuse.
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
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
    return await auth_callback_service.handle_google_callback(
        request=request,
        db=db,
        code=code,
        state=state,
        error=error,
    )


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
        org_display_name=org_service.get_org_display_name(org),
        org_slug=org.slug,
        org_timezone=org.timezone,
        org_portal_base_url=org_service.get_org_portal_base_url(org),
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
        mfa_enabled=user.mfa_enabled,
        mfa_required=session.mfa_required,
        mfa_verified=session.mfa_verified,
        profile_complete=bool(user.display_name and user.title),
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
        org_display_name=org_service.get_org_display_name(org),
        org_slug=org.slug,
        org_timezone=org.timezone,
        org_portal_base_url=org_service.get_org_portal_base_url(org),
        role=session.role,
        ai_enabled=org.ai_enabled if org else False,
        mfa_enabled=user.mfa_enabled,
        mfa_required=session.mfa_required,
        mfa_verified=session.mfa_verified,
        profile_complete=bool(user.display_name and user.title),
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
    if not avatar_url:
        return

    try:
        from app.core.config import settings as app_settings

        bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")
        key = storage_url_service.extract_storage_key(avatar_url, bucket)
        if not key or not key.startswith("avatars/"):
            return

        s3 = storage_client.get_s3_client()
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception as exc:
        logger.debug("Failed to delete old avatar %s: %s", avatar_url, exc, exc_info=exc)


class AvatarResponse(BaseModel):
    avatar_url: str | None


@router.post(
    "/me/avatar",
    response_model=AvatarResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_avatar(
    background_tasks: BackgroundTasks,
    request: Request,
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

    if content_length_exceeds_limit(
        request.headers.get("content-length"),
        max_size_bytes=AVATAR_MAX_SIZE,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    file_size = await get_upload_file_size(file)
    if file_size > AVATAR_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    # Read after size validation
    content = await file.read()

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

    s3 = storage_client.get_s3_client()
    bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=resized_content,
        ContentType=file.content_type,
    )

    # Get public URL
    avatar_url = storage_url_service.build_public_url(bucket, key)

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
    if not photo_url:
        return

    try:
        from app.core.config import settings as app_settings

        bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")
        key = storage_url_service.extract_storage_key(photo_url, bucket)
        if not key or not key.startswith("signatures/"):
            return

        s3 = storage_client.get_s3_client()
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception as exc:
        logger.debug("Failed to delete old signature photo %s: %s", photo_url, exc, exc_info=exc)


@router.post(
    "/me/signature/photo",
    response_model=SignaturePhotoResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_signature_photo(
    background_tasks: BackgroundTasks,
    request: Request,
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

    if content_length_exceeds_limit(
        request.headers.get("content-length"),
        max_size_bytes=AVATAR_MAX_SIZE,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    file_size = await get_upload_file_size(file)
    if file_size > AVATAR_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE // 1024 // 1024}MB",
        )

    # Read after size validation
    content = await file.read()

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

    s3 = storage_client.get_s3_client()
    bucket = getattr(app_settings, "S3_BUCKET", "crm-attachments")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=resized_content,
        ContentType=file.content_type,
    )

    # Get public URL
    photo_url = storage_url_service.build_public_url(bucket, key)

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

    return SignaturePhotoResponse(signature_photo_url=media_service.get_signed_media_url(photo_url))


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
# Security: Rate limit logout to prevent DoS attacks.
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
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

    # Clear domain cookies (new) for cross-subdomain logout
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")

    # Clear host-only cookies (legacy migration safety)
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_success_redirect(
    base_url: str | None = None,
    return_to: str = "app",
    mfa_pending: bool = False,
) -> str:
    """
    Safe success redirect URL - fixed path, no user input.

    Args:
        base_url: Optional org portal base URL (takes precedence for app redirects).
        return_to: Target app ("app" or "ops").
        mfa_pending: If true, redirect to MFA instead of the post-login landing page.
    """
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


def _get_error_redirect(
    error_code: str, base_url: str | None = None, return_to: str = "app"
) -> str:
    """
    Safe error redirect URL - fixed path with error code.

    Args:
        error_code: Error code to include in query string.
        base_url: Optional org portal base URL (takes precedence for app redirects).
        return_to: Target app ("app" or "ops").
    """
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
