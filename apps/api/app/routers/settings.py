"""Settings endpoints for organization and user preferences."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import org_service

router = APIRouter(prefix="/settings", tags=["settings"])


# =============================================================================
# Organization Settings
# =============================================================================


class OrgSettingsRead(BaseModel):
    """Organization settings response."""

    id: str
    name: str
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
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get organization settings."""
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrgSettingsRead(
        id=str(org.id),
        name=org.name,
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
    session: UserSession = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Session = Depends(get_db),
):
    """
    Update organization settings.

    Requires manage_org permission (Admin only).
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
        address=getattr(org, "address", None),
        phone=getattr(org, "phone", None),
        email=getattr(org, "contact_email", None),
    )


# =============================================================================
# Organization Signature Settings (Admin only)
# =============================================================================

import re
from urllib.parse import urlparse
from pydantic import field_validator
from app.services import signature_template_service

# Validation patterns
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class OrgSignatureRead(BaseModel):
    """Organization signature settings response."""

    signature_template: str | None
    signature_logo_url: str | None
    signature_primary_color: str | None
    signature_company_name: str | None
    signature_address: str | None
    signature_phone: str | None
    signature_website: str | None
    available_templates: list[dict]


class OrgSignatureUpdate(BaseModel):
    """Organization signature settings update request (admin only)."""

    signature_template: str | None = None
    signature_primary_color: str | None = None
    signature_company_name: str | None = None
    signature_address: str | None = None
    signature_phone: str | None = None
    signature_website: str | None = None

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


@router.get("/organization/signature", response_model=OrgSignatureRead)
def get_org_signature(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get organization signature settings."""
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrgSignatureRead(
        signature_template=org.signature_template,
        signature_logo_url=org.signature_logo_url,
        signature_primary_color=org.signature_primary_color,
        signature_company_name=org.signature_company_name,
        signature_address=org.signature_address,
        signature_phone=org.signature_phone,
        signature_website=org.signature_website,
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
    session: UserSession = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Session = Depends(get_db),
):
    """
    Update organization signature settings.

    Requires manage_org permission (Admin only).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Track changes
    changed_fields: list[str] = []

    if body.signature_template is not None and body.signature_template != org.signature_template:
        org.signature_template = body.signature_template
        changed_fields.append("signature_template")

    if body.signature_primary_color is not None and body.signature_primary_color != org.signature_primary_color:
        org.signature_primary_color = body.signature_primary_color
        changed_fields.append("signature_primary_color")

    if body.signature_company_name is not None and body.signature_company_name != org.signature_company_name:
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

    return OrgSignatureRead(
        signature_template=org.signature_template,
        signature_logo_url=org.signature_logo_url,
        signature_primary_color=org.signature_primary_color,
        signature_company_name=org.signature_company_name,
        signature_address=org.signature_address,
        signature_phone=org.signature_phone,
        signature_website=org.signature_website,
        available_templates=signature_template_service.get_available_templates(),
    )


# =============================================================================
# Logo Upload/Delete (Admin only)
# =============================================================================

import io
import os
import uuid as uuid_lib
from fastapi import UploadFile, File, BackgroundTasks
from PIL import Image

# Logo constraints
MAX_LOGO_SIZE_BYTES = 50 * 1024  # 50KB
MAX_LOGO_UPLOAD_BYTES = 1 * 1024 * 1024  # 1MB
MAX_LOGO_WIDTH = 200
MAX_LOGO_HEIGHT = 80
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


class LogoUploadResponse(BaseModel):
    """Response after logo upload."""

    signature_logo_url: str


def _get_logo_storage_backend() -> str:
    """Get storage backend for logos."""
    from app.core.config import settings
    return getattr(settings, "STORAGE_BACKEND", "local")


def _get_local_logo_path() -> str:
    """Get local logo storage directory."""
    from app.core.config import settings
    import tempfile
    path = getattr(settings, "LOCAL_STORAGE_PATH", None)
    if not path:
        path = os.path.join(tempfile.gettempdir(), "crm-logos")
    os.makedirs(path, exist_ok=True)
    return path


def _upload_logo_to_storage(org_id: uuid_lib.UUID, file_bytes: bytes, extension: str) -> str:
    """
    Upload logo to storage and return public URL.
    """
    backend = _get_logo_storage_backend()
    filename = f"logos/{org_id}/{uuid_lib.uuid4()}.{extension}"

    if backend == "s3":
        import boto3
        from app.core.config import settings
        s3 = boto3.client(
            "s3",
            region_name=getattr(settings, "S3_REGION", "us-east-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        )
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        s3.put_object(
            Bucket=bucket,
            Key=filename,
            Body=file_bytes,
            ContentType=f"image/{extension}",
            ACL="public-read",
        )
        # Return public S3 URL
        region = getattr(settings, "S3_REGION", "us-east-1")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"
    else:
        # Local storage - serve from public directory or temp
        local_path = os.path.join(_get_local_logo_path(), filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        # Return relative path (assumes static file serving is configured)
        return f"/static/{filename}"


def _delete_logo_from_storage(logo_url: str) -> None:
    """Delete logo from storage (called asynchronously after new upload)."""
    if not logo_url:
        return

    backend = _get_logo_storage_backend()

    try:
        if backend == "s3" and ".s3." in logo_url:
            import boto3
            from app.core.config import settings
            # Extract key from S3 URL
            key = logo_url.split(".amazonaws.com/")[-1]
            s3 = boto3.client(
                "s3",
                region_name=getattr(settings, "S3_REGION", "us-east-1"),
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            )
            bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
            s3.delete_object(Bucket=bucket, Key=key)
        elif logo_url.startswith("/static/"):
            # Local file
            local_path = os.path.join(_get_local_logo_path(), logo_url.replace("/static/", ""))
            if os.path.exists(local_path):
                os.remove(local_path)
    except Exception:
        pass  # Best effort delete


@router.post(
    "/organization/signature/logo",
    response_model=LogoUploadResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_org_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: UserSession = Depends(require_permission(POLICIES["org_settings"].default)),
    db: Session = Depends(get_db),
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

    # Read and validate file
    content = await file.read()
    if len(content) > MAX_LOGO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

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
    new_logo_url = _upload_logo_to_storage(session.org_id, final_bytes, extension)

    # Update database
    org.signature_logo_url = new_logo_url
    db.commit()

    # Schedule async deletion of old logo
    if old_logo_url:
        background_tasks.add_task(_delete_logo_from_storage, old_logo_url)

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

    return LogoUploadResponse(signature_logo_url=new_logo_url)


@router.delete(
    "/organization/signature/logo",
    dependencies=[Depends(require_csrf_header)],
)
async def delete_org_logo(
    request: Request,
    background_tasks: BackgroundTasks,
    session: UserSession = Depends(require_permission(POLICIES["org_settings"].default)),
    db: Session = Depends(get_db),
):
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

    # Clear from database first
    org.signature_logo_url = None
    db.commit()

    # Schedule async deletion from storage
    background_tasks.add_task(_delete_logo_from_storage, old_logo_url)

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
