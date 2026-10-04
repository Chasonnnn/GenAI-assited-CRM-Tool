"""Settings endpoints for organization and user preferences."""

import io
import mimetypes
import os
import re
import uuid as uuid_lib
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from botocore.exceptions import BotoCoreError, ClientError
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
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import (
    intelligent_suggestions_service,
    media_service,
    org_logo_service,
    org_service,
    signature_template_service,
)
from app.utils.file_upload import content_length_exceeds_limit, get_upload_file_size

router = APIRouter(prefix="/settings", tags=["settings"])


# =============================================================================
# Organization Settings
# =============================================================================


class OrgSettingsRead(BaseModel):
    """Organization settings response."""

    id: str
    name: str
    slug: str
    portal_base_url: str
    logo_url: str | None
    address: str | None
    phone: str | None
    email: str | None


class OrgSettingsUpdate(BaseModel):
    """Organization settings update request."""

    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


@router.get("/organization", response_model=OrgSettingsRead)
def get_org_settings(
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Get organization settings."""
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrgSettingsRead(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        portal_base_url=org_service.get_org_portal_base_url(org),
        logo_url=media_service.get_signed_media_url(org.logo_url),
        address=getattr(org, "address", None),
        phone=getattr(org, "phone", None),
        email=getattr(org, "contact_email", None),
    )


@router.patch(
    "/organization",
    response_model=OrgSettingsRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_org_settings(
    body: OrgSettingsUpdate,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Update organization settings.

    Requires manage_org permission (Admin only).
    Note: Slug updates are only available via platform admin (ops console).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    changed_fields: list[str] = []
    if body.name is not None and body.name != org.name:
        changed_fields.append("name")
    if body.address is not None and body.address != getattr(org, "address", None):
        changed_fields.append("address")
    if body.phone is not None and body.phone != getattr(org, "phone", None):
        changed_fields.append("phone")
    if body.email is not None and body.email != getattr(org, "contact_email", None):
        changed_fields.append("email")
    org = org_service.update_org_contact(
        db=db,
        org=org,
        name=body.name,
        address=body.address,
        phone=body.phone,
        email=body.email,
    )
    if changed_fields:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="org",
            changes={"fields": changed_fields},
            request=request,
        )
        db.commit()

    return OrgSettingsRead(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        portal_base_url=org_service.get_org_portal_base_url(org),
        logo_url=media_service.get_signed_media_url(org.logo_url),
        address=getattr(org, "address", None),
        phone=getattr(org, "phone", None),
        email=getattr(org, "contact_email", None),
    )


class IntelligentSuggestionSettingsRead(BaseModel):
    enabled: bool
    new_unread_enabled: bool
    new_unread_business_days: int
    stuck_enabled: bool
    stuck_business_days: int
    daily_digest_enabled: bool
    digest_hour_local: int


class IntelligentSuggestionSettingsUpdate(BaseModel):
    enabled: bool | None = None
    new_unread_enabled: bool | None = None
    new_unread_business_days: int | None = Field(None, ge=1, le=30)
    stuck_enabled: bool | None = None
    stuck_business_days: int | None = Field(None, ge=1, le=60)
    daily_digest_enabled: bool | None = None
    digest_hour_local: int | None = Field(None, ge=0, le=23)


class IntelligentSuggestionTemplateRead(BaseModel):
    template_key: str
    name: str
    description: str
    rule_kind: str
    default_stage_slug: str | None
    default_stage_key: str | None = None
    default_stage_label: str | None = None
    default_business_days: int
    is_default: bool


class IntelligentSuggestionRuleRead(BaseModel):
    id: str
    organization_id: str
    template_key: str
    name: str
    rule_kind: str
    stage_slug: str | None
    stage_key: str | None = None
    stage_label: str | None = None
    business_days: int
    enabled: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class IntelligentSuggestionRuleCreate(BaseModel):
    template_key: str
    name: str | None = None
    rule_kind: str | None = None
    stage_slug: str | None = None
    stage_key: str | None = None
    business_days: int | None = Field(None, ge=1, le=60)
    enabled: bool = True


class IntelligentSuggestionRuleUpdate(BaseModel):
    name: str | None = None
    stage_slug: str | None = None
    stage_key: str | None = None
    business_days: int | None = Field(None, ge=1, le=60)
    enabled: bool | None = None
    sort_order: int | None = None


@router.get(
    "/intelligent-suggestions",
    response_model=IntelligentSuggestionSettingsRead,
)
def get_intelligent_suggestion_settings(
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    settings = intelligent_suggestions_service.get_or_create_settings(db, session.org_id)
    payload = intelligent_suggestions_service.serialize_settings(settings)
    return IntelligentSuggestionSettingsRead(**payload)


@router.patch(
    "/intelligent-suggestions",
    response_model=IntelligentSuggestionSettingsRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_intelligent_suggestion_settings(
    body: IntelligentSuggestionSettingsUpdate,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    settings = intelligent_suggestions_service.update_settings(db, session.org_id, updates)
    if updates:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="intelligent_suggestions",
            changes=updates,
            request=request,
        )
        db.commit()

    payload = intelligent_suggestions_service.serialize_settings(settings)
    return IntelligentSuggestionSettingsRead(**payload)


@router.get(
    "/intelligent-suggestions/templates",
    response_model=list[IntelligentSuggestionTemplateRead],
)
def list_intelligent_suggestion_templates(
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    templates = intelligent_suggestions_service.list_rule_templates(db, session.org_id)
    return [IntelligentSuggestionTemplateRead(**template) for template in templates]


@router.get(
    "/intelligent-suggestions/rules",
    response_model=list[IntelligentSuggestionRuleRead],
)
def list_intelligent_suggestion_rules(
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    rules = intelligent_suggestions_service.list_rules(db, session.org_id)
    return [
        IntelligentSuggestionRuleRead(**rule)
        for rule in intelligent_suggestions_service.serialize_rules(db, session.org_id, rules)
    ]


@router.post(
    "/intelligent-suggestions/rules",
    response_model=IntelligentSuggestionRuleRead,
    dependencies=[Depends(require_csrf_header)],
)
def create_intelligent_suggestion_rule(
    body: IntelligentSuggestionRuleCreate,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    from app.services import audit_service

    try:
        rule = intelligent_suggestions_service.create_rule(
            db,
            session.org_id,
            body.model_dump(exclude_unset=True),
        )
    except intelligent_suggestions_service.DuplicateRuleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_settings_changed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        setting_area="intelligent_suggestions_rule",
        changes={"action": "create", "rule_id": str(rule.id)},
        request=request,
    )
    db.commit()
    return IntelligentSuggestionRuleRead(**intelligent_suggestions_service.serialize_rule(db, rule))


@router.patch(
    "/intelligent-suggestions/rules/{rule_id}",
    response_model=IntelligentSuggestionRuleRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_intelligent_suggestion_rule(
    rule_id: uuid_lib.UUID,
    body: IntelligentSuggestionRuleUpdate,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    from app.services import audit_service

    try:
        rule = intelligent_suggestions_service.update_rule(
            db,
            session.org_id,
            rule_id,
            body.model_dump(exclude_unset=True),
        )
    except intelligent_suggestions_service.DuplicateRuleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_settings_changed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        setting_area="intelligent_suggestions_rule",
        changes={"action": "update", "rule_id": str(rule.id)},
        request=request,
    )
    db.commit()
    return IntelligentSuggestionRuleRead(**intelligent_suggestions_service.serialize_rule(db, rule))


@router.delete(
    "/intelligent-suggestions/rules/{rule_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_intelligent_suggestion_rule(
    rule_id: uuid_lib.UUID,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> None:
    from app.services import audit_service

    try:
        intelligent_suggestions_service.delete_rule(db, session.org_id, rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_settings_changed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        setting_area="intelligent_suggestions_rule",
        changes={"action": "delete", "rule_id": str(rule_id)},
        request=request,
    )
    db.commit()


# =============================================================================
# Organization Signature Settings (Admin only)
# =============================================================================

# Validation patterns
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Max social links per org
MAX_SOCIAL_LINKS = 6


class SocialLinkItem(BaseModel):
    """A social link with platform name and URL."""

    platform: str = Field(min_length=1, max_length=50)
    url: str = Field(max_length=500)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        # Allow alphanumeric and spaces only (prevent XSS)
        if not re.match(r"^[\w\s]+$", v):
            raise ValueError("Platform name must be alphanumeric")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("URL must start with https://")
        parsed = urlparse(v)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Invalid URL format")
        return v


class OrgSignatureRead(BaseModel):
    """Organization signature settings response."""

    signature_template: str | None
    signature_logo_url: str | None
    logo_url: str | None
    signature_primary_color: str | None
    signature_company_name: str | None
    signature_address: str | None
    signature_phone: str | None
    signature_website: str | None
    signature_social_links: list[SocialLinkItem] | None
    signature_disclaimer: str | None
    available_templates: list[dict]


class OrgSignatureUpdate(BaseModel):
    """Organization signature settings update request (admin only)."""

    signature_template: str | None = None
    signature_primary_color: str | None = None
    signature_company_name: str | None = None
    signature_address: str | None = None
    signature_phone: str | None = None
    signature_website: str | None = None
    signature_social_links: list[SocialLinkItem] | None = None
    signature_disclaimer: str | None = Field(None, max_length=1000)

    @field_validator("signature_template")
    @classmethod
    def validate_template(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid_templates = ["classic", "modern", "minimal", "professional", "creative"]
        if v not in valid_templates:
            raise ValueError(f"Template must be one of: {', '.join(valid_templates)}")
        return v

    @field_validator("signature_primary_color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not HEX_COLOR_PATTERN.match(v):
            raise ValueError("Color must be a valid hex color (e.g., #0066cc)")
        return v

    @field_validator("signature_website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        if v.strip() != v:
            raise ValueError("Website must be a valid https:// URL")
        if any(char.isspace() for char in v):
            raise ValueError("Website must be a valid https:// URL")
        if any(char in v for char in ['"', "'", "<", ">"]):
            raise ValueError("Website must be a valid https:// URL")
        if not v.startswith("https://"):
            raise ValueError("Website must start with https://")
        parsed = urlparse(v)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Website must be a valid https:// URL")
        return v

    @field_validator("signature_social_links")
    @classmethod
    def validate_social_links(cls, v: list[SocialLinkItem] | None) -> list[SocialLinkItem] | None:
        if v is None:
            return v
        if len(v) > MAX_SOCIAL_LINKS:
            raise ValueError(f"Maximum {MAX_SOCIAL_LINKS} social links allowed")
        # Deduplicate by URL (normalize and keep first)
        seen_urls = set()
        deduped = []
        for link in v:
            normalized = link.url.lower().rstrip("/")
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                deduped.append(link)
        return deduped


class SignaturePreviewResponse(BaseModel):
    """Rendered signature HTML preview."""

    html: str


@router.get("/organization/signature", response_model=OrgSignatureRead)
def get_org_signature(
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Get organization signature settings (read-only for non-admin users).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Parse social links from JSONB
    social_links = None
    if org.signature_social_links:
        social_links = [
            SocialLinkItem(platform=link.get("platform", ""), url=link.get("url", ""))
            for link in org.signature_social_links
            if link.get("platform") and link.get("url")
        ]

    return OrgSignatureRead(
        signature_template=org.signature_template,
        signature_logo_url=media_service.get_signed_media_url(org.signature_logo_url),
        logo_url=media_service.get_signed_media_url(org.logo_url),
        signature_primary_color=org.signature_primary_color,
        signature_company_name=org.signature_company_name,
        signature_address=org.signature_address,
        signature_phone=org.signature_phone,
        signature_website=org.signature_website,
        signature_social_links=social_links,
        signature_disclaimer=org.signature_disclaimer,
        available_templates=signature_template_service.get_available_templates(),
    )


@router.patch(
    "/organization/signature",
    response_model=OrgSignatureRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_org_signature(
    body: OrgSignatureUpdate,
    request: Request,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Update organization signature settings.

    Requires manage_org permission.
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Track changes
    changed_fields: list[str] = []

    if body.signature_template is not None and body.signature_template != org.signature_template:
        org.signature_template = body.signature_template
        changed_fields.append("signature_template")

    if (
        body.signature_primary_color is not None
        and body.signature_primary_color != org.signature_primary_color
    ):
        org.signature_primary_color = body.signature_primary_color
        changed_fields.append("signature_primary_color")

    if (
        body.signature_company_name is not None
        and body.signature_company_name != org.signature_company_name
    ):
        org.signature_company_name = body.signature_company_name
        changed_fields.append("signature_company_name")

    if body.signature_address is not None and body.signature_address != org.signature_address:
        org.signature_address = body.signature_address
        changed_fields.append("signature_address")

    if body.signature_phone is not None and body.signature_phone != org.signature_phone:
        org.signature_phone = body.signature_phone
        changed_fields.append("signature_phone")

    if body.signature_website is not None and body.signature_website != org.signature_website:
        org.signature_website = body.signature_website
        changed_fields.append("signature_website")

    if body.signature_social_links is not None:
        # Convert Pydantic models to dicts for JSONB storage
        new_links = [
            {"platform": link.platform, "url": link.url} for link in body.signature_social_links
        ]
        if new_links != org.signature_social_links:
            org.signature_social_links = new_links
            changed_fields.append("signature_social_links")

    if (
        body.signature_disclaimer is not None
        and body.signature_disclaimer != org.signature_disclaimer
    ):
        org.signature_disclaimer = body.signature_disclaimer if body.signature_disclaimer else None
        changed_fields.append("signature_disclaimer")

    if changed_fields:
        from app.services import audit_service

        db.commit()
        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="signature",
            changes={"fields": changed_fields},
            request=request,
        )
        db.commit()

    # Parse social links for response
    social_links = None
    if org.signature_social_links:
        social_links = [
            SocialLinkItem(platform=link.get("platform", ""), url=link.get("url", ""))
            for link in org.signature_social_links
            if link.get("platform") and link.get("url")
        ]

    return OrgSignatureRead(
        signature_template=org.signature_template,
        signature_logo_url=media_service.get_signed_media_url(org.signature_logo_url),
        logo_url=media_service.get_signed_media_url(org.logo_url),
        signature_primary_color=org.signature_primary_color,
        signature_company_name=org.signature_company_name,
        signature_address=org.signature_address,
        signature_phone=org.signature_phone,
        signature_website=org.signature_website,
        signature_social_links=social_links,
        signature_disclaimer=org.signature_disclaimer,
        available_templates=signature_template_service.get_available_templates(),
    )


@router.get("/organization/signature/preview", response_model=SignaturePreviewResponse)
def get_org_signature_preview(
    template: str | None = None,
    mode: str | None = None,
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Get rendered HTML preview of organization signature.

    Uses sample user data (not admin's personal info) to show how
    the signature template looks with org branding.

    Optionally pass ?template=modern|minimal|professional|creative to
    preview a template before saving.
    Use ?mode=org_only for org-only preview (no user fields).

    """
    # Validate template parameter if provided
    valid_templates = ["classic", "modern", "minimal", "professional", "creative"]
    if template and template not in valid_templates:
        template = None  # Fall back to saved template

    if mode == "org_only":
        html = signature_template_service.render_org_signature_html(
            db=db,
            org_id=session.org_id,
            template_override=template,
        )
    else:
        html = signature_template_service.render_signature_preview(
            db=db,
            org_id=session.org_id,
            template_override=template,
        )

    return SignaturePreviewResponse(html=html)


# =============================================================================
# Logo Upload/Delete (Admin only)
# =============================================================================

# Logo constraints
MAX_LOGO_SIZE_BYTES = org_logo_service.MAX_LOGO_SIZE_BYTES
MAX_LOGO_UPLOAD_BYTES = org_logo_service.MAX_LOGO_UPLOAD_BYTES
MAX_LOGO_WIDTH = 200
MAX_LOGO_HEIGHT = 80
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


class LogoUploadResponse(BaseModel):
    """Response after logo upload."""

    signature_logo_url: str


class OrganizationLogoUploadResponse(BaseModel):
    logo_url: str


@router.post(
    "/organization/logo",
    response_model=OrganizationLogoUploadResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_organization_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    session: Annotated[UserSession, Depends(require_permission(POLICIES["org_settings"].default))],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationLogoUploadResponse:
    if (
        content_length_exceeds_limit(
            request.headers.get("content-length"), max_size_bytes=MAX_LOGO_UPLOAD_BYTES
        )
        or await get_upload_file_size(file) > MAX_LOGO_UPLOAD_BYTES
    ):
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")
    content = await file.read(MAX_LOGO_UPLOAD_BYTES + 1)
    try:
        new_url, old_url = await run_in_threadpool(
            org_logo_service.upload_square_logo,
            db,
            session.org_id,
            session.user_id,
            content,
            file.filename,
            request,
        )
        if old_url:
            background_tasks.add_task(org_logo_service.cleanup_logo, old_url)
        signed_url = await run_in_threadpool(media_service.get_signed_media_url, new_url)
        if not signed_url:
            raise HTTPException(status_code=503, detail="Logo storage unavailable")
        return OrganizationLogoUploadResponse(logo_url=signed_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Logo storage unavailable") from exc


@router.delete(
    "/organization/logo",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_organization_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[UserSession, Depends(require_permission(POLICIES["org_settings"].default))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    old_url = org_logo_service.delete_square_logo(db, session.org_id, session.user_id, request)
    if old_url:
        background_tasks.add_task(org_logo_service.cleanup_logo, old_url)
    return Response(status_code=204)


@router.get("/organization/signature/logo/local/{storage_key:path}")
def get_org_logo_local(
    storage_key: str,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    """Serve a currently referenced organization logo from local storage (dev only)."""
    from fastapi.responses import FileResponse

    if "\\" in storage_key:
        raise HTTPException(status_code=404, detail="Logo not found")

    normalized = os.path.normpath(storage_key)
    if not normalized.startswith("logos/"):
        raise HTTPException(status_code=404, detail="Logo not found")
    if normalized.startswith("..") or normalized.startswith("/"):
        raise HTTPException(status_code=404, detail="Logo not found")

    expected_url = org_logo_service.build_local_logo_url(normalized)
    legacy_url = f"/static/{normalized}"
    org = org_service.get_org_by_logo_urls(db, [expected_url, legacy_url])
    if not org:
        raise HTTPException(status_code=404, detail="Logo not found")

    base_dir = org_logo_service.get_local_logo_path()
    file_path = os.path.abspath(os.path.join(base_dir, normalized))
    base_abs = os.path.abspath(base_dir)
    if os.path.commonpath([file_path, base_abs]) != base_abs:
        raise HTTPException(status_code=404, detail="Logo not found")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Logo not found")

    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)


@router.post(
    "/organization/signature/logo",
    response_model=LogoUploadResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_org_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, "fastapi_param"] = File(),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Upload organization signature logo.

    - Validates format (PNG, JPG only)
    - Resizes to max 200x80px
    - Compresses to < 50KB
    - Uploads new logo, updates DB, then deletes old logo asynchronously

    Requires manage_org permission (Admin only).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    extension = file.filename.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if content_length_exceeds_limit(
        request.headers.get("content-length"),
        max_size_bytes=MAX_LOGO_UPLOAD_BYTES,
    ):
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    file_size = await get_upload_file_size(file)
    if file_size > MAX_LOGO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    # Read and validate file after size checks
    content = await file.read()

    try:
        # Open with PIL and process
        img = Image.open(io.BytesIO(content))

        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            extension = "jpg"

        # Resize if too large
        if img.width > MAX_LOGO_WIDTH or img.height > MAX_LOGO_HEIGHT:
            img.thumbnail((MAX_LOGO_WIDTH, MAX_LOGO_HEIGHT), Image.Resampling.LANCZOS)

        # Save to bytes with compression
        output = io.BytesIO()
        if extension == "png":
            img.save(output, format="PNG", optimize=True)
        else:
            # Save as JPEG with quality adjustment
            quality = 85
            while quality >= 30:
                output.seek(0)
                output.truncate()
                img.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= MAX_LOGO_SIZE_BYTES:
                    break
                quality -= 10

        final_bytes = output.getvalue()
        if len(final_bytes) > MAX_LOGO_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Image too complex to compress under 50KB")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    # Save old URL for async deletion
    old_logo_url = org.signature_logo_url

    # Upload new logo
    new_logo_url = org_logo_service.upload_logo_to_storage(session.org_id, final_bytes, extension)

    org.signature_logo_url = new_logo_url

    # Schedule async deletion of old logo
    if old_logo_url:
        background_tasks.add_task(org_logo_service.cleanup_logo, old_logo_url)

    # Audit log
    from app.services import audit_service

    audit_service.log_settings_changed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        setting_area="signature_logo",
        changes={"action": "uploaded"},
        request=request,
    )
    db.commit()

    return LogoUploadResponse(signature_logo_url=media_service.get_signed_media_url(new_logo_url))


@router.delete(
    "/organization/signature/logo",
    dependencies=[Depends(require_csrf_header)],
)
def delete_org_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    """
    Delete organization signature logo.

    Requires manage_org permission (Admin only).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not org.signature_logo_url:
        raise HTTPException(status_code=404, detail="No logo to delete")

    old_logo_url = org.signature_logo_url

    org.signature_logo_url = None

    # Schedule async deletion from storage
    background_tasks.add_task(org_logo_service.cleanup_logo, old_logo_url)

    # Audit log
    from app.services import audit_service

    audit_service.log_settings_changed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        setting_area="signature_logo",
        changes={"action": "deleted"},
        request=request,
    )
    db.commit()

    return {"status": "deleted"}
