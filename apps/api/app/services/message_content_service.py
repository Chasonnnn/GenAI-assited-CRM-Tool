"""Immutable messaging templates and scan-gated outbound media assets."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import PurePath
from typing import BinaryIO, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.enums import JobStatus, JobType
from app.db.models import Job, MessageMediaAsset, MessageTemplate, TwilioSettings
from app.services import attachment_service, job_service

MessagingPurpose = Literal["operational", "promotional"]
ContentClassification = Literal["no_phi", "phi"]
TemplateStatus = Literal["draft", "published", "retired"]

MAX_TEMPLATE_BODY_CHARACTERS = 1_600
MAX_MEDIA_ASSET_BYTES = 5 * 1024 * 1024
MAX_MEDIA_ASSETS_PER_MESSAGE = 10
MEDIA_ACCESS_TTL_SECONDS = 300
MAX_MEDIA_ACCESS_TTL_SECONDS = 600

_MEDIA_MIME_TO_EXTENSIONS: dict[str, frozenset[str]] = {
    "image/gif": frozenset({"gif"}),
    "image/jpeg": frozenset({"jpg", "jpeg"}),
    "image/png": frozenset({"png"}),
}
_MEDIA_CANONICAL_EXTENSION = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
}
_IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
_VALID_PURPOSES = frozenset({"operational", "promotional"})
_VALID_CLASSIFICATIONS = frozenset({"no_phi", "phi"})
_VALID_SCAN_RESULTS = frozenset({"clean", "quarantined", "rejected"})
_WORD_HELP = re.compile(r"\bHELP\b", re.IGNORECASE)
_WORD_STOP = re.compile(r"\bSTOP\b", re.IGNORECASE)
_MESSAGE_DATA_RATE = re.compile(
    r"\b(?:message(?:s)?\s+and\s+data|msg\s*&\s*data)\s+rates?\s+may\s+apply\b",
    re.IGNORECASE,
)


class MessageContentError(ValueError):
    """Base class for safe client-facing content errors."""


class TemplateNotFound(MessageContentError):
    """The requested template family or version was not found in the organization."""


class TemplateStateConflict(MessageContentError):
    """The requested template transition is not allowed."""


class TemplateDisclosureError(MessageContentError):
    """An enrollment confirmation is missing required disclosure language."""


class PhiMessagingBlocked(MessageContentError):
    """PHI content is blocked by the organization's current Twilio gate."""


class MessagingMediaValidationError(MessageContentError):
    """An outbound media upload failed validation."""


class MessagingMediaNotFound(MessageContentError):
    """A media asset was not found within the organization."""


class MessagingMediaUnavailable(MessageContentError):
    """A media asset has not passed scanning or is quarantined."""


class MessagingMediaStorageError(RuntimeError):
    """A validated media asset could not be stored or loaded."""


class InvalidMediaAccessSignature(ValueError):
    """A media capability is invalid or expired."""


@dataclass(frozen=True, slots=True)
class MediaUpload:
    filename: str
    content_type: str
    file: BinaryIO


@dataclass(frozen=True, slots=True)
class MediaAccessGrant:
    asset_id: uuid.UUID
    expires_at: datetime
    signature: str


@dataclass(frozen=True, slots=True)
class MediaContent:
    asset: MessageMediaAsset
    content: bytes


def _normalized_spaces(value: str) -> str:
    return " ".join(value.casefold().split())


def _validate_template_fields(
    *,
    name: str,
    purpose: str,
    body: str,
    content_classification: str,
) -> tuple[str, str]:
    normalized_name = name.strip()
    normalized_body = body.strip()
    if not normalized_name:
        raise MessageContentError("Template name is required")
    if len(normalized_name) > 160:
        raise MessageContentError("Template name must not exceed 160 characters")
    if purpose not in _VALID_PURPOSES:
        raise MessageContentError("Unsupported messaging purpose")
    if not normalized_body:
        raise MessageContentError("Template body is required")
    if len(normalized_body) > MAX_TEMPLATE_BODY_CHARACTERS:
        raise MessageContentError(
            f"Template body must not exceed {MAX_TEMPLATE_BODY_CHARACTERS} characters"
        )
    if content_classification not in _VALID_CLASSIFICATIONS:
        raise MessageContentError("Unsupported content classification")
    return normalized_name, normalized_body


def _twilio_phi_gate_is_valid(settings: TwilioSettings | None) -> bool:
    return bool(
        settings is not None
        and settings.phi_enabled
        and settings.twilio_edition == "hipaa_eligible"
        and settings.baa_verified_at is not None
        and settings.compliance_approved_at is not None
    )


def require_phi_gate(db: Session, organization_id: uuid.UUID) -> TwilioSettings:
    """Require the same complete PHI gate enforced by Twilio settings updates."""
    settings = db.execute(
        select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
    ).scalar_one_or_none()
    if not _twilio_phi_gate_is_valid(settings):
        raise PhiMessagingBlocked(
            "PHI messaging requires phi_enabled with a verified HIPAA-eligible Twilio edition, "
            "signed BAA, and compliance approval"
        )
    return settings


def _require_phi_gate_for_classification(
    db: Session,
    organization_id: uuid.UUID,
    content_classification: str,
) -> None:
    if content_classification == "phi":
        require_phi_gate(db, organization_id)


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def create_template_draft(
    db: Session,
    *,
    organization_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    name: str,
    purpose: MessagingPurpose,
    body: str,
    is_enrollment_confirmation: bool,
    content_classification: ContentClassification,
) -> MessageTemplate:
    """Create version one of a new immutable organization template family."""
    normalized_name, normalized_body = _validate_template_fields(
        name=name,
        purpose=purpose,
        body=body,
        content_classification=content_classification,
    )
    _require_phi_gate_for_classification(db, organization_id, content_classification)
    template = MessageTemplate(
        id=uuid.uuid4(),
        organization_id=organization_id,
        template_key=uuid.uuid4(),
        version=1,
        name=normalized_name,
        purpose=purpose,
        body=normalized_body,
        content_hash=_body_hash(normalized_body),
        status="draft",
        is_enrollment_confirmation=is_enrollment_confirmation,
        content_classification=content_classification,
        created_by_user_id=created_by_user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def create_next_template_version(
    db: Session,
    *,
    organization_id: uuid.UUID,
    template_key: uuid.UUID,
    created_by_user_id: uuid.UUID,
    name: str | None = None,
    purpose: MessagingPurpose | None = None,
    body: str | None = None,
    is_enrollment_confirmation: bool | None = None,
    content_classification: ContentClassification | None = None,
) -> MessageTemplate:
    """Fork the latest immutable row into the next draft version."""
    latest = db.execute(
        select(MessageTemplate)
        .where(
            MessageTemplate.organization_id == organization_id,
            MessageTemplate.template_key == template_key,
        )
        .order_by(MessageTemplate.version.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if latest is None:
        raise TemplateNotFound("Messaging template was not found")

    next_name = latest.name if name is None else name
    next_purpose = latest.purpose if purpose is None else purpose
    next_body = latest.body if body is None else body
    next_confirmation = (
        latest.is_enrollment_confirmation
        if is_enrollment_confirmation is None
        else is_enrollment_confirmation
    )
    next_classification = (
        latest.content_classification
        if content_classification is None
        else content_classification
    )
    normalized_name, normalized_body = _validate_template_fields(
        name=next_name,
        purpose=next_purpose,
        body=next_body,
        content_classification=next_classification,
    )
    _require_phi_gate_for_classification(db, organization_id, next_classification)
    template = MessageTemplate(
        id=uuid.uuid4(),
        organization_id=organization_id,
        template_key=template_key,
        version=latest.version + 1,
        name=normalized_name,
        purpose=next_purpose,
        body=normalized_body,
        content_hash=_body_hash(normalized_body),
        status="draft",
        is_enrollment_confirmation=next_confirmation,
        content_classification=next_classification,
        created_by_user_id=created_by_user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(
    db: Session,
    organization_id: uuid.UUID,
    template_id: uuid.UUID,
) -> MessageTemplate | None:
    """Get one exact version without crossing the organization boundary."""
    return db.execute(
        select(MessageTemplate).where(
            MessageTemplate.organization_id == organization_id,
            MessageTemplate.id == template_id,
        )
    ).scalar_one_or_none()


def list_templates(
    db: Session,
    organization_id: uuid.UUID,
    *,
    purpose: MessagingPurpose | None = None,
    status: TemplateStatus | None = None,
) -> list[MessageTemplate]:
    """List immutable versions, newest version first, within one organization."""
    query = select(MessageTemplate).where(MessageTemplate.organization_id == organization_id)
    if purpose is not None:
        query = query.where(MessageTemplate.purpose == purpose)
    if status is not None:
        query = query.where(MessageTemplate.status == status)
    return list(
        db.execute(
            query.order_by(
                MessageTemplate.created_at.desc(),
                MessageTemplate.template_key,
                MessageTemplate.version.desc(),
            )
        ).scalars()
    )


def _validate_enrollment_disclosure(
    template: MessageTemplate,
    settings: TwilioSettings | None,
) -> None:
    if not template.is_enrollment_confirmation:
        return
    body = template.body
    normalized_body = _normalized_spaces(body)
    missing: list[str] = []
    legal_brand = settings.legal_messaging_brand.strip() if settings else ""
    expected_frequency = settings.expected_frequency.strip() if settings else ""
    if not legal_brand or _normalized_spaces(legal_brand) not in normalized_body:
        missing.append("configured legal brand")
    if template.purpose.casefold() not in normalized_body:
        missing.append("program/purpose")
    if not expected_frequency or _normalized_spaces(expected_frequency) not in normalized_body:
        missing.append("configured expected frequency")
    if not _MESSAGE_DATA_RATE.search(body):
        missing.append("message/data rate language")
    if not _WORD_HELP.search(body):
        missing.append("HELP")
    if not _WORD_STOP.search(body):
        missing.append("STOP")
    if missing:
        raise TemplateDisclosureError(
            "Enrollment confirmation is missing: " + ", ".join(missing)
        )


def publish_template(
    db: Session,
    *,
    organization_id: uuid.UUID,
    template_id: uuid.UUID,
) -> MessageTemplate:
    """Atomically publish one exact draft and retire the prior published version."""
    target = db.execute(
        select(MessageTemplate)
        .where(
            MessageTemplate.organization_id == organization_id,
            MessageTemplate.id == template_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise TemplateNotFound("Messaging template was not found")
    if target.status == "published":
        return target
    if target.status != "draft":
        raise TemplateStateConflict("Only a draft template version can be published")
    if target.content_classification == "phi":
        settings = require_phi_gate(db, organization_id)
    else:
        settings = db.execute(
            select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
        ).scalar_one_or_none()
    _validate_enrollment_disclosure(target, settings)

    family = list(
        db.execute(
            select(MessageTemplate)
            .where(
                MessageTemplate.organization_id == organization_id,
                MessageTemplate.template_key == target.template_key,
            )
            .with_for_update()
        ).scalars()
    )
    now = datetime.now(UTC)
    for version in family:
        if version.status == "published" and version.id != target.id:
            version.status = "retired"
    target.status = "published"
    target.published_at = now
    db.commit()
    db.refresh(target)
    return target


def _normalize_media_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return "image/jpeg" if normalized == "image/jpg" else normalized


def _validated_media_bytes(upload: MediaUpload) -> tuple[str, bytes]:
    filename = upload.filename.strip()
    if not filename or len(filename) > 255:
        raise MessagingMediaValidationError("Media filename must be between 1 and 255 characters")
    content_type = _normalize_media_type(upload.content_type)
    allowed_extensions = _MEDIA_MIME_TO_EXTENSIONS.get(content_type)
    if allowed_extensions is None:
        raise MessagingMediaValidationError(
            "Only Twilio-safe GIF, JPEG, and PNG image media is supported"
        )
    suffix = PurePath(filename).suffix.lower().lstrip(".")
    if suffix not in allowed_extensions:
        raise MessagingMediaValidationError("Media filename extension does not match its MIME type")

    upload.file.seek(0)
    raw = upload.file.read(MAX_MEDIA_ASSET_BYTES + 1)
    upload.file.seek(0)
    if not raw:
        raise MessagingMediaValidationError("Media file must not be empty")
    if len(raw) > MAX_MEDIA_ASSET_BYTES:
        raise MessagingMediaValidationError("Media file exceeds the 5 MB limit")
    if not raw.startswith(_IMAGE_SIGNATURES[content_type]):
        raise MessagingMediaValidationError("Media bytes do not match the declared image type")

    try:
        processed = attachment_service.strip_exif_data(BytesIO(raw), content_type)
        processed.seek(0)
        content = processed.read(MAX_MEDIA_ASSET_BYTES + 1)
    except ValueError as exc:
        raise MessagingMediaValidationError(str(exc)) from exc
    if len(content) > MAX_MEDIA_ASSET_BYTES:
        raise MessagingMediaValidationError("Processed media file exceeds the 5 MB limit")
    return content_type, content


def validate_media_asset_count(count: int) -> None:
    if count < 1:
        raise MessagingMediaValidationError("At least one media asset is required")
    if count > MAX_MEDIA_ASSETS_PER_MESSAGE:
        raise MessagingMediaValidationError(
            f"A message can include at most {MAX_MEDIA_ASSETS_PER_MESSAGE} media assets"
        )


def _ensure_media_scan_job(
    db: Session,
    *,
    organization_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> None:
    idempotency_key = f"message_media_scan:{asset_id}"
    existing = db.execute(
        select(Job.id).where(Job.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        return
    job_service.enqueue_job(
        db=db,
        org_id=organization_id,
        job_type=JobType.MESSAGE_MEDIA_SCAN,
        payload={"media_asset_id": str(asset_id)},
        idempotency_key=idempotency_key,
        commit=False,
    )


def upload_media_assets(
    db: Session,
    *,
    organization_id: uuid.UUID,
    uploads: list[MediaUpload],
    content_classification: ContentClassification,
) -> list[MessageMediaAsset]:
    """Validate, store, checksum, and enqueue an atomic batch of outbound media."""
    validate_media_asset_count(len(uploads))
    if content_classification not in _VALID_CLASSIFICATIONS:
        raise MessagingMediaValidationError("Unsupported content classification")
    _require_phi_gate_for_classification(db, organization_id, content_classification)
    validated_uploads = [
        (upload, *_validated_media_bytes(upload))
        for upload in uploads
    ]

    assets: list[MessageMediaAsset] = []
    try:
        for upload, content_type, content in validated_uploads:
            checksum = hashlib.sha256(content).hexdigest()
            existing = db.execute(
                select(MessageMediaAsset).where(
                    MessageMediaAsset.organization_id == organization_id,
                    MessageMediaAsset.checksum_sha256 == checksum,
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.content_classification != content_classification:
                    raise MessagingMediaValidationError(
                        "Existing media has a different content classification"
                    )
                assets.append(existing)
                continue

            asset_id = uuid.uuid4()
            extension = _MEDIA_CANONICAL_EXTENSION[content_type]
            storage_key = f"messaging/{organization_id}/{asset_id.hex}.{extension}"
            try:
                attachment_service.store_file(storage_key, BytesIO(content), content_type)
            except Exception as exc:  # noqa: BLE001 - preserve storage implementation boundary
                raise MessagingMediaStorageError("Failed to store messaging media") from exc
            attachment_service.register_storage_cleanup_on_rollback(db, storage_key)
            asset = MessageMediaAsset(
                id=asset_id,
                organization_id=organization_id,
                storage_key=storage_key,
                original_filename=upload.filename.strip(),
                content_type=content_type,
                byte_size=len(content),
                checksum_sha256=checksum,
                scan_status="pending",
                content_classification=content_classification,
            )
            db.add(asset)
            db.flush()
            _ensure_media_scan_job(
                db,
                organization_id=organization_id,
                asset_id=asset.id,
            )
            assets.append(asset)
        db.commit()
        for asset in assets:
            db.refresh(asset)
        return assets
    except Exception:
        db.rollback()
        raise


def get_media_asset(
    db: Session,
    organization_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> MessageMediaAsset | None:
    return db.execute(
        select(MessageMediaAsset).where(
            MessageMediaAsset.organization_id == organization_id,
            MessageMediaAsset.id == asset_id,
        )
    ).scalar_one_or_none()


def list_media_assets(
    db: Session,
    organization_id: uuid.UUID,
    *,
    scan_status: str | None = None,
) -> list[MessageMediaAsset]:
    query = select(MessageMediaAsset).where(
        MessageMediaAsset.organization_id == organization_id
    )
    if scan_status is not None:
        query = query.where(MessageMediaAsset.scan_status == scan_status)
    return list(db.execute(query.order_by(MessageMediaAsset.created_at.desc())).scalars())


def mark_media_asset_scanned(
    db: Session,
    *,
    asset_id: uuid.UUID,
    scan_result: str,
    quarantine_reason: str | None = None,
) -> MessageMediaAsset | None:
    """Apply a terminal scan result without changing immutable media metadata."""
    if scan_result not in _VALID_SCAN_RESULTS:
        raise ValueError("Unsupported messaging media scan result")
    asset = db.execute(
        select(MessageMediaAsset)
        .where(MessageMediaAsset.id == asset_id)
        .with_for_update()
    ).scalar_one_or_none()
    if asset is None:
        return None
    if asset.scan_status != "pending":
        return asset
    asset.scan_status = scan_result
    asset.quarantine_reason = None if scan_result == "clean" else (quarantine_reason or "unsafe")[:120]
    db.flush()
    return asset


def _media_signature_payload(asset_id: uuid.UUID, expires_at: int) -> bytes:
    return f"messaging-media-v1\n{asset_id}\n{expires_at}".encode()


def _sign_media_access(asset_id: uuid.UUID, expires_at: int, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        _media_signature_payload(asset_id, expires_at),
        hashlib.sha256,
    ).hexdigest()


def issue_media_access(
    db: Session,
    *,
    organization_id: uuid.UUID,
    asset_id: uuid.UUID,
    now: datetime | None = None,
) -> MediaAccessGrant:
    """Issue a short-lived GET+HEAD capability only for clean media."""
    asset = get_media_asset(db, organization_id, asset_id)
    if asset is None:
        raise MessagingMediaNotFound("Messaging media was not found")
    if asset.scan_status != "clean":
        raise MessagingMediaUnavailable("Messaging media is unavailable until scanning passes")
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=MEDIA_ACCESS_TTL_SECONDS)
    expires_epoch = int(expires_at.timestamp())
    signature = _sign_media_access(asset.id, expires_epoch, app_settings.jwt_secrets[0])
    return MediaAccessGrant(
        asset_id=asset.id,
        expires_at=datetime.fromtimestamp(expires_epoch, tz=UTC),
        signature=signature,
    )


def validate_media_access(
    *,
    asset_id: uuid.UUID,
    expires_at: int,
    signature: str,
    now: datetime | None = None,
) -> None:
    """Validate one method-neutral media capability for both HEAD and GET."""
    checked_at = now or datetime.now(UTC)
    now_epoch = int(checked_at.timestamp())
    if expires_at <= now_epoch or expires_at - now_epoch > MAX_MEDIA_ACCESS_TTL_SECONDS:
        raise InvalidMediaAccessSignature("Media access signature is invalid or expired")
    for secret in app_settings.jwt_secrets:
        expected = _sign_media_access(asset_id, expires_at, secret)
        if hmac.compare_digest(expected, signature):
            return
    raise InvalidMediaAccessSignature("Media access signature is invalid or expired")


def load_signed_media(
    db: Session,
    *,
    asset_id: uuid.UUID,
    expires_at: int,
    signature: str,
) -> MediaContent:
    """Validate a capability and return only clean media bytes and safe metadata."""
    validate_media_access(
        asset_id=asset_id,
        expires_at=expires_at,
        signature=signature,
    )
    asset = db.execute(
        select(MessageMediaAsset).where(MessageMediaAsset.id == asset_id)
    ).scalar_one_or_none()
    if asset is None or asset.scan_status != "clean":
        raise MessagingMediaNotFound("Messaging media was not found")
    try:
        content = attachment_service.load_file_bytes(asset.storage_key)
    except (FileNotFoundError, OSError) as exc:
        raise MessagingMediaStorageError("Messaging media storage object is unavailable") from exc
    if len(content) != asset.byte_size or hashlib.sha256(content).hexdigest() != asset.checksum_sha256:
        raise MessagingMediaStorageError("Messaging media storage integrity check failed")
    return MediaContent(asset=asset, content=content)


def pending_media_scan_job(
    db: Session,
    *,
    organization_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> Job | None:
    """Return the current in-flight media scan job, if any."""
    jobs = db.execute(
        select(Job)
        .where(
            Job.organization_id == organization_id,
            Job.job_type == JobType.MESSAGE_MEDIA_SCAN.value,
            Job.status.in_((JobStatus.PENDING.value, JobStatus.RUNNING.value)),
        )
        .order_by(Job.created_at.desc())
    ).scalars()
    expected = str(asset_id)
    return next((job for job in jobs if (job.payload or {}).get("media_asset_id") == expected), None)
