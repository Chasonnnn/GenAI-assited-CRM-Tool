"""Organization logo storage, square image processing, and audited updates."""

import io
import logging
import os
import tempfile
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Organization
from app.services import audit_service, storage_cleanup_service, storage_client, storage_url_service

logger = logging.getLogger(__name__)

MAX_LOGO_SIZE_BYTES = 50 * 1024
MAX_LOGO_UPLOAD_BYTES = 1024 * 1024
MAX_LOGO_PIXELS = 4096 * 4096
LOCAL_LOGO_URL_PREFIX = "/settings/organization/signature/logo/local/"
ALLOWED_SQUARE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def get_local_logo_path() -> str:
    path = settings.LOCAL_STORAGE_PATH or os.path.join(tempfile.gettempdir(), "crm-logos")
    os.makedirs(path, exist_ok=True)
    return path


def build_local_logo_url(storage_key: str) -> str:
    return f"{LOCAL_LOGO_URL_PREFIX}{storage_key}"


def extract_local_logo_storage_key(logo_url: str) -> str | None:
    for prefix in (LOCAL_LOGO_URL_PREFIX, "/static/"):
        if logo_url.startswith(prefix):
            return logo_url.removeprefix(prefix)
    return None


def upload_logo_to_storage(org_id: UUID, file_bytes: bytes, extension: str) -> str:
    filename = f"logos/{org_id}/{uuid4()}.{extension}"
    if settings.STORAGE_BACKEND == "s3":
        s3 = storage_client.get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=filename,
            Body=file_bytes,
            ContentType=f"image/{'jpeg' if extension in {'jpg', 'jpeg'} else extension}",
        )
        return storage_url_service.build_public_url(settings.S3_BUCKET, filename)

    local_path = os.path.join(get_local_logo_path(), filename)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as file:
        file.write(file_bytes)
    return build_local_logo_url(filename)


def delete_logo_from_storage(logo_url: str) -> None:
    if settings.STORAGE_BACKEND == "s3":
        key = storage_url_service.extract_storage_key(logo_url, settings.S3_BUCKET)
        if key:
            storage_client.get_s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
        return

    storage_key = extract_local_logo_storage_key(logo_url)
    if storage_key:
        base = os.path.realpath(get_local_logo_path())
        local_path = os.path.realpath(os.path.join(base, storage_key))
        if os.path.commonpath([local_path, base]) != base:
            raise ValueError("Invalid local logo storage path")
        try:
            os.remove(local_path)
        except FileNotFoundError:
            pass


def cleanup_logo(logo_url: str) -> None:
    """Best-effort cleanup after replacement; do not log storage URLs or credentials."""
    try:
        delete_logo_from_storage(logo_url)
    except Exception as exc:
        logger.warning("Organization logo cleanup failed (%s)", type(exc).__name__)


def process_square_logo(content: bytes, filename: str | None) -> tuple[bytes, str]:
    if not filename:
        raise ValueError("No filename provided")
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_SQUARE_EXTENSIONS:
        raise ValueError("Invalid file type. Allowed: png, jpg, jpeg, webp")
    if len(content) > MAX_LOGO_UPLOAD_BYTES:
        raise ValueError("File too large (max 1MB)")

    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > MAX_LOGO_PIXELS:
                raise ValueError(f"Image exceeds the maximum of {MAX_LOGO_PIXELS} pixels")
            if source.format not in {"PNG", "JPEG", "MPO", "WEBP"}:
                raise ValueError("Invalid image file. Allowed: PNG, JPG, WebP")
            if min(source.size) < 64:
                raise ValueError("Image must be at least 64x64 pixels")
            # JPEG/MPO opens on the first frame; reduce its decode before loading pixels.
            if source.format in {"JPEG", "MPO"}:
                source.draft(None, (256, 256))
            ImageOps.exif_transpose(source, in_place=True)
            mode = (
                "RGBA"
                if source.has_transparency_data and extension not in {"jpg", "jpeg"}
                else "RGB"
            )
            side = min(source.size)
            left = (source.width - side) // 2
            top = (source.height - side) // 2
            image = source.crop((left, top, left + side, top + side))

        # Release the decoded source before resizing. Palette images need conversion
        # first because Pillow otherwise forces nearest-neighbor resampling.
        if image.mode in {"P", "1"}:
            image = image.convert(mode)
        image = image.resize((256, 256), Image.Resampling.LANCZOS)
        if image.mode != mode:
            image = image.convert(mode)
        # The stored image contains only pixels, without uploaded metadata.
        image.info.clear()
        output = io.BytesIO()
        if extension == "png":
            image.save(output, format="PNG", optimize=True)
        else:
            format = "WEBP" if extension == "webp" else "JPEG"
            extension = "webp" if format == "WEBP" else "jpg"
            for quality in range(85, 29, -10):
                output.seek(0)
                output.truncate()
                image.save(output, format=format, quality=quality, optimize=True)
                if output.tell() <= MAX_LOGO_SIZE_BYTES:
                    break
        if output.tell() > MAX_LOGO_SIZE_BYTES:
            raise ValueError("Image too complex to compress under 50KB")
        return output.getvalue(), extension
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid image file") from exc


def _lock_org(db: Session, org_id: UUID) -> Organization:
    org = (
        db.query(Organization)
        .filter(Organization.id == org_id, Organization.deleted_at.is_(None))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _schedule_cleanup(db: Session, org_id: UUID, logo_url: str | None) -> None:
    if not logo_url:
        return
    storage_key = extract_local_logo_storage_key(
        logo_url
    ) or storage_url_service.extract_storage_key(logo_url, settings.S3_BUCKET)
    if storage_key:
        storage_cleanup_service.enqueue_storage_deletions(
            db, org_id=org_id, storage_keys=[storage_key]
        )


def upload_square_logo(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    content: bytes,
    filename: str | None,
    request: Request,
) -> tuple[str, str | None]:
    image_bytes, extension = process_square_logo(content, filename)
    new_url = upload_logo_to_storage(org_id, image_bytes, extension)
    try:
        org = _lock_org(db, org_id)
        old_url = org.logo_url
        org.logo_url = new_url
        _schedule_cleanup(db, org_id, old_url)
        audit_service.log_settings_changed(
            db=db,
            org_id=org_id,
            user_id=user_id,
            setting_area="logo",
            changes={"action": "uploaded"},
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        cleanup_logo(new_url)
        raise
    return new_url, old_url


def delete_square_logo(db: Session, org_id: UUID, user_id: UUID, request: Request) -> str | None:
    try:
        org = _lock_org(db, org_id)
        if not org.logo_url:
            return None
        old_url = org.logo_url
        org.logo_url = None
        _schedule_cleanup(db, org_id, old_url)
        audit_service.log_settings_changed(
            db=db,
            org_id=org_id,
            user_id=user_id,
            setting_area="logo",
            changes={"action": "deleted"},
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return old_url
