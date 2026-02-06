"""Platform admin router for ops console operations.

All endpoints require platform admin access via require_platform_admin dependency.
Platform admins can manage organizations, users, and subscriptions across all tenants.
"""

import io
import logging
import mimetypes
import os
import uuid as uuid_lib
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from PIL import Image
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    require_platform_admin,
    require_csrf_header,
    PlatformUserSession,
    COOKIE_NAME,
)
from app.core.csrf import set_csrf_cookie, CSRF_COOKIE_NAME, get_csrf_cookie
from app.core.config import settings
from app.services import platform_service, session_service, storage_client, storage_url_service
from app.db.enums import Role
from app.schemas.platform_templates import (
    PlatformEmailTemplateCreate,
    PlatformEmailTemplateUpdate,
    PlatformEmailTemplateRead,
    PlatformEmailTemplateListItem,
    PlatformFormTemplateCreate,
    PlatformFormTemplateUpdate,
    PlatformFormTemplateRead,
    PlatformFormTemplateListItem,
    PlatformWorkflowTemplateCreate,
    PlatformWorkflowTemplateUpdate,
    PlatformWorkflowTemplateRead,
    PlatformWorkflowTemplateListItem,
    TemplatePublishRequest,
    PlatformEmailTemplateDraft,
    PlatformFormTemplateDraft,
    PlatformWorkflowTemplateDraft,
)
from app.schemas.email import (
    EmailTemplateTestSendResponse,
    PlatformEmailTemplateTestSendRequest,
    TemplateVariableRead,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateOrgRequest(BaseModel):
    name: str
    slug: str
    timezone: str = "America/Los_Angeles"
    admin_email: EmailStr

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        # Basic format validation (detailed validation in org_service.validate_slug)
        import re

        if not re.match(r"^[a-z0-9-]+$", v.lower()):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        if len(v) < 2 or len(v) > 50:
            raise ValueError("Slug must be between 2 and 50 characters")
        return v.lower()


class UpdateSubscriptionRequest(BaseModel):
    plan_key: str | None = None
    status: str | None = None
    auto_renew: bool | None = None
    notes: str | None = None


class ExtendSubscriptionRequest(BaseModel):
    days: int = 30

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError("Days must be between 1 and 365")
        return v


class UpdateMemberRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class CreateInviteRequest(BaseModel):
    email: EmailStr
    role: str


class UpdateOrgRequest(BaseModel):
    """Update org name and/or slug."""

    name: str | None = None
    slug: str | None = None


class CreateSupportSessionRequest(BaseModel):
    org_id: UUID
    role: str
    reason_code: str
    reason_text: str | None = None
    mode: str = "write"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if not Role.has_value(v):
            raise ValueError("Invalid role")
        return v

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        if v not in platform_service.SUPPORT_SESSION_REASON_CODES:
            raise ValueError("Invalid reason_code")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in platform_service.SUPPORT_SESSION_ALLOWED_MODES:
            raise ValueError("Invalid mode")
        return v

    @field_validator("reason_text")
    @classmethod
    def validate_reason_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        text = v.strip()
        if len(text) > 500:
            raise ValueError("Reason text must be 500 characters or less")
        return text


# =============================================================================
# Platform Email (System Sender + Templates)
# =============================================================================


class PlatformEmailStatusResponse(BaseModel):
    configured: bool
    from_email: str | None
    provider: str


class SystemEmailTemplateRead(BaseModel):
    system_key: str
    name: str
    subject: str
    from_email: str | None = None
    body: str
    is_active: bool
    current_version: int
    updated_at: str | None


class PlatformEmailBrandingRead(BaseModel):
    logo_url: str | None = None


class PlatformEmailBrandingUpdate(BaseModel):
    logo_url: str | None = None


class UpdateSystemEmailTemplateRequest(BaseModel):
    subject: str
    from_email: str | None = None
    body: str
    is_active: bool = True
    expected_version: int | None = None


class SendTestSystemEmailRequest(BaseModel):
    to_email: EmailStr
    org_id: UUID | None = None


class SystemEmailCampaignTarget(BaseModel):
    org_id: UUID
    user_ids: list[UUID]

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, v: list[UUID]) -> list[UUID]:
        if not v:
            raise ValueError("user_ids must include at least one user")
        return v


class SystemEmailCampaignRequest(BaseModel):
    targets: list[SystemEmailCampaignTarget]

    @field_validator("targets")
    @classmethod
    def validate_targets(
        cls, v: list[SystemEmailCampaignTarget]
    ) -> list[SystemEmailCampaignTarget]:
        if not v:
            raise ValueError("targets must include at least one organization")
        return v


# =============================================================================
# Platform User Info
# =============================================================================


@router.get("/me")
def get_platform_me(
    session: PlatformUserSession = Depends(require_platform_admin),
) -> dict:
    """
    Get current platform admin info.

    Used by ops console frontend to verify platform admin access
    and display user info in the header.
    """
    return {
        "user_id": str(session.user_id),
        "email": session.email,
        "display_name": session.display_name,
        "is_platform_admin": session.is_platform_admin,
    }


@router.get("/email/status", response_model=PlatformEmailStatusResponse)
def get_platform_email_status(
    session: PlatformUserSession = Depends(require_platform_admin),
) -> PlatformEmailStatusResponse:
    """Get platform/system email sender status (Resend)."""
    from app.services import platform_email_service

    configured = platform_email_service.platform_sender_configured()
    return PlatformEmailStatusResponse(
        configured=configured,
        from_email=settings.PLATFORM_EMAIL_FROM or None,
        provider="resend",
    )


# =============================================================================
# Platform Stats
# =============================================================================


@router.get("/stats")
def get_platform_stats(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get platform-wide statistics for ops dashboard."""
    return platform_service.get_platform_stats(db)


# =============================================================================
# Support Sessions (Role Override)
# =============================================================================


@router.post("/support-sessions", dependencies=[Depends(require_csrf_header)])
def create_support_session(
    body: CreateSupportSessionRequest,
    request: Request,
    response: Response,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a support session with role override and set session cookies."""
    try:
        data, token, ttl_seconds = platform_service.create_support_session(
            db=db,
            actor_id=session.user_id,
            org_id=body.org_id,
            role=body.role,
            reason_code=body.reason_code,
            reason_text=body.reason_text,
            mode=body.mode,
            token_version=session.token_version,
            mfa_verified=session.mfa_verified,
            mfa_required=session.mfa_required,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Revoke the previous session token to prevent fallback to old org context.
    previous_token = request.cookies.get(COOKIE_NAME)
    if previous_token:
        session_service.delete_session_by_token(db, previous_token)

    # Clear host-only cookies when using domain cookies (migration safety)
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=ttl_seconds,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    # Preserve existing CSRF token to avoid invalidating the current header.
    set_csrf_cookie(response, token=get_csrf_cookie(request))

    return data


@router.post(
    "/support-sessions/{session_id}/revoke",
    dependencies=[Depends(require_csrf_header)],
)
def revoke_support_session(
    session_id: UUID,
    request: Request,
    response: Response,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Revoke a support session."""
    result = platform_service.revoke_support_session(
        db=db,
        session_id=session_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Support session not found")

    # Revoke current session token and clear cookies to enforce support session exit.
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session_service.delete_session_by_token(db, token)
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    return {"status": "revoked"}


# =============================================================================
# Organization Management
# =============================================================================


@router.get("/orgs")
def list_organizations(
    search: str | None = Query(None, description="Search by name or slug"),
    status: str | None = Query(None, description="Filter by subscription status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all organizations with summary info."""
    items, total = platform_service.list_organizations(
        db, search=search, status=status, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.post("/orgs", dependencies=[Depends(require_csrf_header)])
def create_organization(
    body: CreateOrgRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new organization with subscription and first admin invite."""
    try:
        return platform_service.create_organization(
            db=db,
            actor_id=session.user_id,
            name=body.name,
            slug=body.slug,
            timezone_str=body.timezone,
            admin_email=body.admin_email,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}")
def get_organization(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get organization detail."""
    result = platform_service.get_organization_detail(db, org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Organization not found")
    return result


@router.patch("/orgs/{org_id}", dependencies=[Depends(require_csrf_header)])
def update_organization(
    org_id: UUID,
    body: UpdateOrgRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """
    Update organization name and/or slug.

    Slug changes have significant impact:
    - Portal URL changes to https://{new_slug}.surrogacyforce.com
    - Existing sessions on the old subdomain become invalid
    - Users must re-login on the new subdomain
    - Old slug immediately returns 404 (no redirect)
    """
    from app.services import org_service

    org = org_service.get_org_by_id(db, org_id, include_deleted=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    old_slug = org.slug
    changed_fields: list[str] = []

    # Update name
    if body.name is not None and body.name != org.name:
        org.name = body.name
        changed_fields.append("name")

    # Update slug
    slug = body.slug
    if slug is not None:
        new_slug = slug.lower()
        if new_slug != org.slug:
            try:
                org, old_slug = org_service.update_org_slug(db, org, new_slug)
                changed_fields.append("slug")
            except ValueError as e:
                # Return 409 for conflicts, 400 for validation errors
                error_msg = str(e)
                status_code = 409 if "already in use" in error_msg else 400
                raise HTTPException(status_code=status_code, detail=error_msg)

    if not changed_fields:
        # No changes
        return platform_service.get_organization_detail(db, org_id)

    # Commit name change if only name changed (slug update already committed)
    if "name" in changed_fields and "slug" not in changed_fields:
        db.commit()

    # Audit log
    log_metadata = {"changed_fields": changed_fields}
    if "slug" in changed_fields:
        log_metadata["old_slug"] = old_slug
        log_metadata["new_slug"] = org.slug

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="org.update",
        target_org_id=org_id,
        metadata=log_metadata,
        request=request,
    )
    db.commit()

    return platform_service.get_organization_detail(db, org_id)


@router.post("/orgs/{org_id}/delete", dependencies=[Depends(require_csrf_header)])
def delete_organization(
    org_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Soft delete an organization and schedule hard delete."""
    try:
        return platform_service.request_organization_deletion(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orgs/{org_id}/restore", dependencies=[Depends(require_csrf_header)])
def restore_organization(
    org_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Restore a soft-deleted organization."""
    try:
        return platform_service.restore_organization_deletion(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orgs/{org_id}/purge", dependencies=[Depends(require_csrf_header)])
def purge_organization(
    org_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Immediately hard delete an organization (no grace period)."""
    try:
        return platform_service.force_delete_organization(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Subscription Management
# =============================================================================


@router.get("/orgs/{org_id}/subscription")
def get_subscription(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get organization subscription details."""
    result = platform_service.get_subscription(db, org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return result


@router.put("/orgs/{org_id}/subscription", dependencies=[Depends(require_csrf_header)])
def update_subscription(
    org_id: UUID,
    body: UpdateSubscriptionRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update organization subscription."""
    try:
        return platform_service.update_subscription(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            plan_key=body.plan_key,
            status=body.status,
            auto_renew=body.auto_renew,
            notes=body.notes,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orgs/{org_id}/subscription/extend", dependencies=[Depends(require_csrf_header)])
def extend_subscription(
    org_id: UUID,
    body: ExtendSubscriptionRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Extend subscription by N days."""
    try:
        return platform_service.extend_subscription(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            days=body.days,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Member Management
# =============================================================================


@router.get("/orgs/{org_id}/members")
def list_members(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List organization members."""
    return platform_service.list_members(db, org_id)


@router.patch("/orgs/{org_id}/members/{member_id}", dependencies=[Depends(require_csrf_header)])
def update_member(
    org_id: UUID,
    member_id: UUID,
    body: UpdateMemberRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update member role or status."""
    try:
        return platform_service.update_member(
            db=db,
            org_id=org_id,
            member_id=member_id,
            actor_id=session.user_id,
            role=body.role,
            is_active=body.is_active,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orgs/{org_id}/members/{member_id}/mfa/reset",
    dependencies=[Depends(require_csrf_header)],
)
def reset_member_mfa(
    org_id: UUID,
    member_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Reset MFA for a member and revoke their sessions."""
    try:
        return platform_service.reset_member_mfa(
            db=db,
            org_id=org_id,
            member_id=member_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Invite Management
# =============================================================================


@router.get("/orgs/{org_id}/invites")
def list_invites(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List organization invites."""
    return platform_service.list_invites(db, org_id)


@router.post("/orgs/{org_id}/invites", dependencies=[Depends(require_csrf_header)])
def create_invite(
    org_id: UUID,
    body: CreateInviteRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new invite."""
    try:
        return platform_service.create_invite(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            email=body.email,
            role=body.role,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orgs/{org_id}/invites/{invite_id}/revoke", dependencies=[Depends(require_csrf_header)]
)
def revoke_invite(
    org_id: UUID,
    invite_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Revoke an invite."""
    try:
        platform_service.revoke_invite(
            db=db,
            org_id=org_id,
            invite_id=invite_id,
            actor_id=session.user_id,
            request=request,
        )
        return {"status": "revoked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orgs/{org_id}/invites/{invite_id}/resend", dependencies=[Depends(require_csrf_header)]
)
def resend_invite(
    org_id: UUID,
    invite_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Resend an invite."""
    try:
        return platform_service.resend_invite(
            db=db,
            org_id=org_id,
            invite_id=invite_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Platform Email Branding
# =============================================================================

PLATFORM_LOGO_MAX_SIZE_BYTES = 50 * 1024  # 50KB
PLATFORM_LOGO_UPLOAD_BYTES = 1 * 1024 * 1024  # 1MB
PLATFORM_LOGO_MAX_WIDTH = 200
PLATFORM_LOGO_MAX_HEIGHT = 80
PLATFORM_LOGO_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
PLATFORM_LOGO_LOCAL_PREFIX = "/platform/email/branding/logo/local/"


def _platform_logo_prefix_api_base(path: str) -> str:
    if not path.startswith("/"):
        return path
    base = (settings.API_BASE_URL or "").rstrip("/")
    if not base:
        return path
    return f"{base}{path}"


def _platform_logo_strip_api_base(url: str) -> str:
    base = (settings.API_BASE_URL or "").rstrip("/")
    if base and url.startswith(base):
        return url.removeprefix(base)
    return url


def _platform_logo_build_local_url(storage_key: str) -> str:
    return _platform_logo_prefix_api_base(f"{PLATFORM_LOGO_LOCAL_PREFIX}{storage_key}")


def _platform_logo_extract_local_storage_key(logo_url: str) -> str | None:
    path = _platform_logo_strip_api_base(logo_url)
    if path.startswith(PLATFORM_LOGO_LOCAL_PREFIX):
        return path.replace(PLATFORM_LOGO_LOCAL_PREFIX, "", 1)
    return None


def _get_platform_logo_storage_backend() -> str:
    return getattr(settings, "STORAGE_BACKEND", "local")


def _get_platform_logo_local_path() -> str:
    import tempfile

    path = getattr(settings, "LOCAL_STORAGE_PATH", None)
    if not path:
        path = os.path.join(tempfile.gettempdir(), "crm-logos")
    os.makedirs(path, exist_ok=True)
    return path


def _upload_platform_logo_to_storage(file_bytes: bytes, extension: str) -> str:
    backend = _get_platform_logo_storage_backend()
    filename = f"logos/platform/{uuid_lib.uuid4()}.{extension}"

    if backend == "s3":
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        s3 = storage_client.get_s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=filename,
            Body=file_bytes,
            ContentType=f"image/{extension}",
        )
        return storage_url_service.build_public_url(bucket, filename)

    local_path = os.path.join(_get_platform_logo_local_path(), filename)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return _platform_logo_build_local_url(filename)


def _delete_platform_logo_from_storage(logo_url: str) -> None:
    if not logo_url:
        return

    backend = _get_platform_logo_storage_backend()
    try:
        if backend == "s3":
            bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
            key = storage_url_service.extract_storage_key(logo_url, bucket)
            if not key:
                return
            s3 = storage_client.get_s3_client()
            s3.delete_object(Bucket=bucket, Key=key)
        else:
            storage_key = _platform_logo_extract_local_storage_key(logo_url)
            if storage_key:
                local_path = os.path.join(_get_platform_logo_local_path(), storage_key)
                if os.path.exists(local_path):
                    os.remove(local_path)
    except Exception as exc:
        logger.debug("Failed to delete platform logo %s: %s", logo_url, exc, exc_info=exc)


@router.get("/email/branding", response_model=PlatformEmailBrandingRead)
def get_platform_email_branding(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailBrandingRead:
    from app.services import platform_branding_service

    branding = platform_branding_service.get_branding(db)
    return PlatformEmailBrandingRead(logo_url=branding.logo_url)


@router.get("/email/branding/logo/local/{storage_key:path}")
async def get_platform_logo_local(
    storage_key: str,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse
    from app.services import platform_branding_service

    if "\\" in storage_key:
        raise HTTPException(status_code=404, detail="Logo not found")

    normalized = os.path.normpath(storage_key)
    if not normalized.startswith("logos/platform/"):
        raise HTTPException(status_code=404, detail="Logo not found")
    if normalized.startswith("..") or normalized.startswith("/"):
        raise HTTPException(status_code=404, detail="Logo not found")

    branding = platform_branding_service.get_branding(db)
    stored_url = branding.logo_url or ""
    expected_url = f"{PLATFORM_LOGO_LOCAL_PREFIX}{normalized}"
    if _platform_logo_strip_api_base(stored_url) != expected_url:
        raise HTTPException(status_code=404, detail="Logo not found")

    base_dir = _get_platform_logo_local_path()
    file_path = os.path.abspath(os.path.join(base_dir, normalized))
    base_abs = os.path.abspath(base_dir)
    if os.path.commonpath([file_path, base_abs]) != base_abs:
        raise HTTPException(status_code=404, detail="Logo not found")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Logo not found")

    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)


@router.post(
    "/email/branding/logo",
    response_model=PlatformEmailBrandingRead,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_platform_email_branding_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailBrandingRead:
    from app.services import platform_branding_service

    branding = platform_branding_service.get_branding(db)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    extension = file.filename.rsplit(".", 1)[-1].lower()
    if extension not in PLATFORM_LOGO_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(PLATFORM_LOGO_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > PLATFORM_LOGO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    try:
        img = Image.open(io.BytesIO(bytes(content)))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            extension = "jpg"

        if img.width > PLATFORM_LOGO_MAX_WIDTH or img.height > PLATFORM_LOGO_MAX_HEIGHT:
            img.thumbnail(
                (PLATFORM_LOGO_MAX_WIDTH, PLATFORM_LOGO_MAX_HEIGHT),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()
        if extension == "png":
            img.save(output, format="PNG", optimize=True)
        else:
            quality = 85
            while quality >= 30:
                output.seek(0)
                output.truncate()
                img.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= PLATFORM_LOGO_MAX_SIZE_BYTES:
                    break
                quality -= 10

        final_bytes = output.getvalue()
        if len(final_bytes) > PLATFORM_LOGO_MAX_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Image too complex to compress under 50KB")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(exc)}")

    old_logo_url = branding.logo_url
    try:
        new_logo_url = _upload_platform_logo_to_storage(final_bytes, extension)
    except Exception as exc:
        logger.exception("Failed to upload platform email branding logo", exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to upload logo")
    branding.logo_url = new_logo_url
    db.commit()

    if old_logo_url:
        background_tasks.add_task(_delete_platform_logo_from_storage, old_logo_url)

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_platform_branding.logo_upload",
        target_org_id=None,
        metadata={"logo_url_set": True},
        request=request,
    )
    db.commit()

    return PlatformEmailBrandingRead(logo_url=branding.logo_url)


@router.put("/email/branding", dependencies=[Depends(require_csrf_header)])
def update_platform_email_branding(
    body: PlatformEmailBrandingUpdate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailBrandingRead:
    from app.services import platform_branding_service

    logo_url = body.logo_url
    if logo_url:
        logo_url = logo_url.strip()
        if logo_url.startswith(PLATFORM_LOGO_LOCAL_PREFIX):
            logo_url = _platform_logo_prefix_api_base(logo_url)
    branding = platform_branding_service.update_branding(db, logo_url=logo_url or None)
    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_platform_branding.update",
        target_org_id=None,
        metadata={"logo_url_set": bool(body.logo_url)},
        request=request,
    )
    db.commit()

    return PlatformEmailBrandingRead(logo_url=branding.logo_url)


# =============================================================================
# System Email Templates (Platform-Scoped, Managed by Ops)
# =============================================================================


@router.get("/email/system-templates", response_model=list[SystemEmailTemplateRead])
def list_platform_system_email_templates(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[SystemEmailTemplateRead]:
    from app.services import system_email_template_service

    def _to_read(template) -> SystemEmailTemplateRead:
        return SystemEmailTemplateRead(
            system_key=template.system_key,
            name=template.name,
            subject=template.subject,
            from_email=template.from_email,
            body=template.body,
            is_active=template.is_active,
            current_version=template.current_version,
            updated_at=template.updated_at.isoformat() if template.updated_at else None,
        )

    templates = []
    for system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES.keys():
        template = system_email_template_service.ensure_system_template(db, system_key=system_key)
        templates.append(_to_read(template))
    return templates


@router.get(
    "/email/system-templates/{system_key}",
    response_model=SystemEmailTemplateRead,
)
def get_platform_system_email_template(
    system_key: str,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Get (and ensure) the platform system email template by system_key."""
    from app.services import system_email_template_service

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)
    db.commit()
    db.refresh(template)

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.put(
    "/email/system-templates/{system_key}",
    dependencies=[Depends(require_csrf_header)],
    response_model=SystemEmailTemplateRead,
)
def update_platform_system_email_template(
    system_key: str,
    body: UpdateSystemEmailTemplateRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Update the platform system email template by system_key."""
    from app.services import system_email_template_service

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)

    try:
        if body.expected_version is not None and template.current_version != body.expected_version:
            raise ValueError("Template version mismatch")
        template.subject = body.subject
        from app.services import email_service

        template.body = email_service.sanitize_template_html(body.body)
        template.is_active = body.is_active
        if "from_email" in body.model_fields_set:
            template.from_email = body.from_email
        template.current_version += 1
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_template.system.update",
        target_org_id=None,
        metadata={"system_key": system_key},
        request=request,
    )
    db.commit()

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.post(
    "/email/system-templates/{system_key}/test",
    dependencies=[Depends(require_csrf_header)],
)
async def send_test_platform_system_email_template(
    system_key: str,
    body: SendTestSystemEmailRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Send a test email using the platform system template + platform sender."""
    test_org_id = body.org_id
    if test_org_id is None:
        raise HTTPException(status_code=400, detail="org_id is required to render the test email")
    return await _send_test_system_template(
        db=db,
        system_key=system_key,
        to_email=str(body.to_email),
        org_id=test_org_id,
        request=request,
        session=session,
    )


@router.post(
    "/email/system-templates/{system_key}/campaign",
    dependencies=[Depends(require_csrf_header)],
)
async def send_platform_system_email_campaign(
    system_key: str,
    body: SystemEmailCampaignRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Send a system email template to selected org/users."""
    try:
        return await platform_service.send_system_email_campaign(
            db=db,
            system_key=system_key,
            targets=[target.model_dump() for target in body.targets],
            actor_id=session.user_id,
            actor_display_name=session.display_name,
            request=request,
        )
    except platform_service.MissingTargetsError as exc:
        raise HTTPException(status_code=400, detail=exc.detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def _send_test_system_template(
    *,
    db: Session,
    system_key: str,
    to_email: str,
    org_id: UUID,
    request: Request,
    session: PlatformUserSession,
) -> dict:
    from app.services import (
        audit_service,
        email_service,
        org_service,
        platform_branding_service,
        platform_email_service,
        system_email_template_service,
    )

    if not platform_email_service.platform_sender_configured():
        raise HTTPException(status_code=400, detail="Platform email sender is not configured")

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)
    resolved_from = (template.from_email or "").strip() or (
        settings.PLATFORM_EMAIL_FROM or ""
    ).strip()
    if not resolved_from:
        raise HTTPException(
            status_code=400,
            detail="Template From address is not configured (set from_email in Ops before sending test emails)",
        )

    org = org_service.get_org_by_id(db, org_id, include_deleted=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_name = org_service.get_org_display_name(org)
    org_slug = org.slug
    base_url = org_service.get_org_portal_base_url(org)
    invite_url = f"{base_url.rstrip('/')}/invite/EXAMPLE"
    inviter_text = ""

    branding = platform_branding_service.get_branding(db)
    platform_logo_url = (branding.logo_url or "").strip()
    platform_logo_block = (
        f'<img src="{platform_logo_url}" alt="Platform logo" style="max-width: 180px; height: auto; display: block; margin: 0 auto 6px auto;" />'
        if platform_logo_url
        else ""
    )

    variables = {
        "org_name": org_name,
        "org_slug": org_slug,
        "invite_url": invite_url,
        "role_title": "Admin",
        "inviter_text": inviter_text,
        "expires_block": "<p>This is a test email. Expiration text would appear here.</p>",
        "platform_logo_url": platform_logo_url,
        "platform_logo_block": platform_logo_block,
    }

    rendered_subject, rendered_body = email_service.render_template(
        template.subject,
        template.body,
        variables,
        safe_html_vars={"expires_block", "platform_logo_block"},
    )

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=org_id,
        to_email=str(to_email),
        subject=rendered_subject,
        from_email=resolved_from,
        html=rendered_body,
        text=(f"Test email for {org_name}\nInvite URL: {invite_url}\nRole: Admin\n"),
        template_id=None,
        surrogate_id=None,
        idempotency_key=None,
    )

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_template.system.test_send",
        target_org_id=org_id,
        metadata={
            "system_key": system_key,
            "email_hash": audit_service.hash_email(str(to_email)),
        },
        request=request,
    )
    db.commit()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=str(result.get("error") or "Send failed"))

    return {
        "sent": True,
        "message_id": result.get("message_id"),
        "email_log_id": result.get("email_log_id"),
    }


@router.get(
    "/orgs/{org_id}/email/system-templates/{system_key}",
    response_model=SystemEmailTemplateRead,
)
def get_org_system_email_template(
    org_id: UUID,
    system_key: str,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Get (and ensure) the platform system email template by system_key."""
    from app.services import system_email_template_service

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)
    db.commit()
    db.refresh(template)

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.put(
    "/orgs/{org_id}/email/system-templates/{system_key}",
    dependencies=[Depends(require_csrf_header)],
    response_model=SystemEmailTemplateRead,
)
def update_org_system_email_template(
    org_id: UUID,
    system_key: str,
    body: UpdateSystemEmailTemplateRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Update the platform system email template by system_key."""
    from app.services import system_email_template_service

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)

    try:
        if body.expected_version is not None and template.current_version != body.expected_version:
            raise ValueError("Template version mismatch")
        template.subject = body.subject
        from app.services import email_service

        template.body = email_service.sanitize_template_html(body.body)
        template.is_active = body.is_active
        if "from_email" in body.model_fields_set:
            template.from_email = body.from_email
        template.current_version += 1
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_template.system.update",
        target_org_id=None,
        metadata={"system_key": system_key},
        request=request,
    )
    db.commit()

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.post(
    "/orgs/{org_id}/email/system-templates/{system_key}/test",
    dependencies=[Depends(require_csrf_header)],
)
async def send_test_org_system_email_template(
    org_id: UUID,
    system_key: str,
    body: SendTestSystemEmailRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Send a test email using the platform system template + platform sender."""
    return await _send_test_system_template(
        db=db,
        system_key=system_key,
        to_email=str(body.to_email),
        org_id=org_id,
        request=request,
        session=session,
    )


# =============================================================================
# Admin Action Logs
# =============================================================================


@router.get("/orgs/{org_id}/admin-actions")
def get_org_admin_actions(
    org_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get admin action logs for an organization."""
    items, total = platform_service.get_admin_action_logs(
        db, org_id=org_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


# =============================================================================
# Platform Alerts (Cross-Org)
# =============================================================================


@router.get("/alerts")
def list_alerts(
    status: str | None = Query(None, description="Filter by status (open, acknowledged, resolved)"),
    severity: str | None = Query(
        None, description="Filter by severity (critical, error, warn, info)"
    ),
    org_id: UUID | None = Query(None, description="Filter by organization"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all alerts across organizations with optional filters."""
    items, total = platform_service.list_platform_alerts(
        db,
        status=status,
        severity=severity,
        org_id=org_id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.post("/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_csrf_header)])
def acknowledge_alert(
    alert_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Acknowledge an alert."""
    result = platform_service.acknowledge_alert(
        db=db,
        alert_id=alert_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/alerts/{alert_id}/resolve", dependencies=[Depends(require_csrf_header)])
def resolve_alert(
    alert_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve an alert."""
    result = platform_service.resolve_alert(
        db=db,
        alert_id=alert_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# =============================================================================
# Platform Template Studio (Email / Forms / Workflows)
# =============================================================================


def _email_draft_from_model(template) -> PlatformEmailTemplateDraft:
    return PlatformEmailTemplateDraft(
        name=template.name,
        subject=template.subject,
        body=template.body,
        from_email=template.from_email,
        category=template.category,
    )


def _email_published_from_model(template) -> PlatformEmailTemplateDraft | None:
    if not template.published_version:
        return None
    if not template.published_subject or not template.published_body:
        return None
    return PlatformEmailTemplateDraft(
        name=template.published_name or template.name,
        subject=template.published_subject,
        body=template.published_body,
        from_email=template.published_from_email,
        category=template.published_category,
    )


def _email_read(template, db: Session) -> PlatformEmailTemplateRead:
    from app.services import platform_template_service

    target_org_ids = platform_template_service.get_platform_email_template_target_org_ids(
        db, template.id
    )
    return PlatformEmailTemplateRead(
        id=template.id,
        status=template.status,
        current_version=template.current_version,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        target_org_ids=target_org_ids,
        published_at=template.published_at,
        draft=_email_draft_from_model(template),
        published=_email_published_from_model(template),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _email_list_item(template) -> PlatformEmailTemplateListItem:
    return PlatformEmailTemplateListItem(
        id=template.id,
        status=template.status,
        current_version=template.current_version,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        draft=_email_draft_from_model(template),
        published_at=template.published_at,
        updated_at=template.updated_at,
    )


def _form_draft_from_model(template) -> PlatformFormTemplateDraft:
    return PlatformFormTemplateDraft(
        name=template.name,
        description=template.description,
        form_schema=template.schema_json,
        settings_json=template.settings_json,
    )


def _form_published_from_model(template) -> PlatformFormTemplateDraft | None:
    if not template.published_version:
        return None
    return PlatformFormTemplateDraft(
        name=template.published_name or template.name,
        description=template.published_description,
        form_schema=template.published_schema_json,
        settings_json=template.published_settings_json,
    )


def _form_read(template, db: Session) -> PlatformFormTemplateRead:
    from app.services import platform_template_service

    target_org_ids = platform_template_service.get_platform_form_template_target_org_ids(
        db, template.id
    )
    return PlatformFormTemplateRead(
        id=template.id,
        status=template.status,
        current_version=template.current_version,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        target_org_ids=target_org_ids,
        published_at=template.published_at,
        draft=_form_draft_from_model(template),
        published=_form_published_from_model(template),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _form_list_item(template) -> PlatformFormTemplateListItem:
    return PlatformFormTemplateListItem(
        id=template.id,
        status=template.status,
        current_version=template.current_version,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        draft=_form_draft_from_model(template),
        published_at=template.published_at,
        updated_at=template.updated_at,
    )


def _workflow_payload_from_model(template) -> dict:
    return {
        "name": template.name,
        "description": template.description,
        "icon": template.icon,
        "category": template.category,
        "trigger_type": template.trigger_type,
        "trigger_config": template.trigger_config or {},
        "conditions": template.conditions or [],
        "condition_logic": template.condition_logic,
        "actions": template.actions or [],
    }


def _workflow_draft_from_model(template) -> PlatformWorkflowTemplateDraft:
    payload = template.draft_config or _workflow_payload_from_model(template)
    return PlatformWorkflowTemplateDraft(**payload)


def _workflow_published_from_model(template) -> PlatformWorkflowTemplateDraft | None:
    if not template.published_version:
        return None
    payload = _workflow_payload_from_model(template)
    return PlatformWorkflowTemplateDraft(**payload)


def _workflow_read(template, db: Session) -> PlatformWorkflowTemplateRead:
    from app.services import platform_template_service

    target_org_ids = platform_template_service.get_platform_workflow_template_target_org_ids(
        db, template.id
    )
    return PlatformWorkflowTemplateRead(
        id=template.id,
        status=template.status,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        target_org_ids=target_org_ids,
        published_at=template.published_at,
        draft=_workflow_draft_from_model(template),
        published=_workflow_published_from_model(template),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _workflow_list_item(template) -> PlatformWorkflowTemplateListItem:
    return PlatformWorkflowTemplateListItem(
        id=template.id,
        status=template.status,
        published_version=template.published_version,
        is_published_globally=template.is_published_globally,
        draft=_workflow_draft_from_model(template),
        published_at=template.published_at,
        updated_at=template.updated_at,
    )


@router.get("/templates/email/variables", response_model=list[TemplateVariableRead])
def list_platform_email_template_variables(
    session: PlatformUserSession = Depends(require_platform_admin),  # noqa: ARG001
):
    """List supported template variables for Ops platform email templates."""
    from app.services import template_variable_catalog

    return [
        TemplateVariableRead(
            name=v.name,
            description=v.description,
            category=v.category,
            required=v.required,
            value_type=v.value_type,
            html_safe=v.html_safe,
        )
        for v in template_variable_catalog.list_platform_email_template_variables()
    ]


@router.get(
    "/email/system-templates/{system_key}/variables",
    response_model=list[TemplateVariableRead],
)
def list_platform_system_template_variables(
    system_key: str,
    session: PlatformUserSession = Depends(require_platform_admin),  # noqa: ARG001
):
    """List supported template variables for a platform system template."""
    from app.services import template_variable_catalog

    try:
        vars_ = template_variable_catalog.list_platform_system_template_variables(system_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return [
        TemplateVariableRead(
            name=v.name,
            description=v.description,
            category=v.category,
            required=v.required,
            value_type=v.value_type,
            html_safe=v.html_safe,
        )
        for v in vars_
    ]


@router.get("/templates/email", response_model=list[PlatformEmailTemplateListItem])
def list_platform_email_templates(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[PlatformEmailTemplateListItem]:
    from app.services import platform_template_service

    templates = platform_template_service.list_platform_email_templates(db)
    return [_email_list_item(template) for template in templates]


@router.post(
    "/templates/email",
    response_model=PlatformEmailTemplateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_platform_email_template(
    body: PlatformEmailTemplateCreate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.create_platform_email_template(
        db,
        name=body.name,
        subject=body.subject,
        body=body.body,
        from_email=body.from_email,
        category=body.category,
    )
    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.email.create",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _email_read(template, db)


@router.get("/templates/email/{template_id}", response_model=PlatformEmailTemplateRead)
def get_platform_email_template(
    template_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_email_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _email_read(template, db)


@router.patch(
    "/templates/email/{template_id}",
    response_model=PlatformEmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_platform_email_template(
    template_id: UUID,
    body: PlatformEmailTemplateUpdate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_email_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template = platform_template_service.update_platform_email_template(
            db,
            template,
            name=body.name,
            subject=body.subject,
            body=body.body,
            from_email=body.from_email
            if "from_email" in body.model_fields_set
            else platform_template_service._UNSET,
            category=body.category
            if "category" in body.model_fields_set
            else platform_template_service._UNSET,
            expected_version=body.expected_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.email.update",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _email_read(template, db)


@router.post(
    "/templates/email/{template_id}/publish",
    response_model=PlatformEmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def publish_platform_email_template(
    template_id: UUID,
    body: TemplatePublishRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformEmailTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_email_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        template = platform_template_service.publish_platform_email_template(
            db,
            template,
            publish_all=body.publish_all,
            org_ids=body.org_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.email.publish",
        metadata={
            "template_id": str(template.id),
            "publish_all": body.publish_all,
            "org_ids": [str(org_id) for org_id in body.org_ids or []],
        },
        request=request,
    )
    db.commit()
    return _email_read(template, db)


@router.post(
    "/templates/email/{template_id}/test",
    response_model=EmailTemplateTestSendResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def test_send_platform_email_template(
    template_id: UUID,
    body: PlatformEmailTemplateTestSendRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> EmailTemplateTestSendResponse:
    """Send a test email using a platform email template for a specific org.

    The send uses the target org's configured workflow email provider (Resend vs org Gmail).
    """
    from app.services import (
        audit_service,
        email_service,
        email_test_send_service,
        platform_template_service,
    )

    template = platform_template_service.get_platform_email_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    variables_used = email_test_send_service.extract_variables(template.subject, template.body)
    base_vars = email_test_send_service.build_sample_variables(
        db=db,
        org_id=body.org_id,
        to_email=str(body.to_email),
        actor_display_name=session.display_name,
    )
    base_vars = email_test_send_service.apply_unknown_variable_fallbacks(
        variables_used=variables_used, variables=base_vars
    )
    final_vars = {**base_vars, **(body.variables or {})}

    rendered_subject, rendered_body = email_service.render_template(
        template.subject,
        template.body,
        final_vars,
    )

    result = await email_test_send_service.send_test_via_org_provider(
        db=db,
        org_id=body.org_id,
        to_email=str(body.to_email),
        subject=rendered_subject,
        html=rendered_body,
        template_id=None,
        idempotency_key=body.idempotency_key,
        template_from_email=template.from_email,
    )

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.email.test_send",
        target_org_id=body.org_id,
        metadata={
            "template_id": str(template.id),
            "email_hash": audit_service.hash_email(str(body.to_email)),
            "success": bool(result.get("success")),
            "provider_used": result.get("provider_used"),
        },
        request=request,
    )
    db.commit()

    return EmailTemplateTestSendResponse(**result)


@router.get("/templates/forms", response_model=list[PlatformFormTemplateListItem])
def list_platform_form_templates(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[PlatformFormTemplateListItem]:
    from app.services import platform_template_service

    templates = platform_template_service.list_platform_form_templates(db)
    return [_form_list_item(template) for template in templates]


@router.post(
    "/templates/forms",
    response_model=PlatformFormTemplateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_platform_form_template(
    body: PlatformFormTemplateCreate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformFormTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.create_platform_form_template(
        db,
        name=body.name,
        description=body.description,
        schema_json=body.form_schema.model_dump() if body.form_schema else None,
        settings_json=body.settings_json,
    )
    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.form.create",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _form_read(template, db)


@router.get("/templates/forms/{template_id}", response_model=PlatformFormTemplateRead)
def get_platform_form_template(
    template_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformFormTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_form_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _form_read(template, db)


@router.patch(
    "/templates/forms/{template_id}",
    response_model=PlatformFormTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_platform_form_template(
    template_id: UUID,
    body: PlatformFormTemplateUpdate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformFormTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_form_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template = platform_template_service.update_platform_form_template(
            db,
            template,
            name=body.name,
            description=body.description,
            schema_json=(
                body.form_schema.model_dump()
                if "form_schema" in body.model_fields_set
                else platform_template_service._UNSET
            ),
            settings_json=(
                body.settings_json
                if "settings_json" in body.model_fields_set
                else platform_template_service._UNSET
            ),
            expected_version=body.expected_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.form.update",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _form_read(template, db)


@router.post(
    "/templates/forms/{template_id}/publish",
    response_model=PlatformFormTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def publish_platform_form_template(
    template_id: UUID,
    body: TemplatePublishRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformFormTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_form_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        template = platform_template_service.publish_platform_form_template(
            db,
            template,
            publish_all=body.publish_all,
            org_ids=body.org_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.form.publish",
        metadata={
            "template_id": str(template.id),
            "publish_all": body.publish_all,
            "org_ids": [str(org_id) for org_id in body.org_ids or []],
        },
        request=request,
    )
    db.commit()
    return _form_read(template, db)


@router.get("/templates/workflows", response_model=list[PlatformWorkflowTemplateListItem])
def list_platform_workflow_templates(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[PlatformWorkflowTemplateListItem]:
    from app.services import platform_template_service

    templates = platform_template_service.list_platform_workflow_templates(db)
    return [_workflow_list_item(template) for template in templates]


@router.post(
    "/templates/workflows",
    response_model=PlatformWorkflowTemplateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_platform_workflow_template(
    body: PlatformWorkflowTemplateCreate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformWorkflowTemplateRead:
    from app.services import platform_template_service

    payload = body.model_dump()
    template = platform_template_service.create_platform_workflow_template(
        db,
        user_id=session.user_id,
        payload=payload,
    )
    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.workflow.create",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _workflow_read(template, db)


@router.get("/templates/workflows/{template_id}", response_model=PlatformWorkflowTemplateRead)
def get_platform_workflow_template(
    template_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformWorkflowTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_workflow_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _workflow_read(template, db)


@router.patch(
    "/templates/workflows/{template_id}",
    response_model=PlatformWorkflowTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_platform_workflow_template(
    template_id: UUID,
    body: PlatformWorkflowTemplateUpdate,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformWorkflowTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_workflow_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    payload = {
        k: v for k, v in body.model_dump().items() if v is not None and k != "expected_version"
    }
    try:
        template = platform_template_service.update_platform_workflow_template(
            db,
            template,
            payload=payload,
            expected_version=body.expected_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.workflow.update",
        metadata={"template_id": str(template.id)},
        request=request,
    )
    db.commit()
    return _workflow_read(template, db)


@router.post(
    "/templates/workflows/{template_id}/publish",
    response_model=PlatformWorkflowTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def publish_platform_workflow_template(
    template_id: UUID,
    body: TemplatePublishRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformWorkflowTemplateRead:
    from app.services import platform_template_service

    template = platform_template_service.get_platform_workflow_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        template = platform_template_service.publish_platform_workflow_template(
            db,
            template,
            publish_all=body.publish_all,
            org_ids=body.org_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="platform_template.workflow.publish",
        metadata={
            "template_id": str(template.id),
            "publish_all": body.publish_all,
            "org_ids": [str(org_id) for org_id in body.org_ids or []],
        },
        request=request,
    )
    db.commit()
    return _workflow_read(template, db)
