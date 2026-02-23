"""Form submission service for tokens, submissions, and review flows."""

import logging
import mimetypes
import re
import secrets
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import UnionType
from typing import Any, Union, get_args, get_origin

from fastapi import UploadFile
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import (
    AuditEventType,
    FormLinkMode,
    FormPurpose,
    FormStatus,
    FormSubmissionMatchStatus,
    FormSubmissionStatus,
    JobType,
    OwnerType,
    SurrogateActivityType,
)
from app.db.models import (
    Form,
    FormFieldMapping,
    FormSubmission,
    FormSubmissionFile,
    FormSubmissionToken,
    Surrogate,
)
from app.schemas.forms import FormField, FormFieldCondition, FormFieldColumn, FormSchema
from app.schemas.surrogate import SurrogateUpdate
from app.services.attachment_service import (
    calculate_checksum,
    generate_signed_url,
    register_storage_cleanup_on_rollback,
    store_file,
    strip_exif_data,
)
from app.services.import_transformers import transform_height_flexible
from app.services import job_service


DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FILE_COUNT = 10
PER_FILE_FIELD_MAX_COUNT = 5
DEFAULT_TOKEN_EXPIRES_IN_DAYS = 14

# Extensions that are always blocked for security
BLOCKED_EXTENSIONS = {
    "exe",
    "dll",
    "com",
    "bat",
    "cmd",
    "sh",
    "vbs",
    "js",
    "jsp",
    "php",
    "pl",
    "py",
    "cgi",
    "ps1",
    "jar",
    "msi",
}

# If a form doesn't explicitly configure allowed MIME types, fall back to a safe default.
# This is intentionally restrictive; public uploads should never be "allow anything".
DEFAULT_ALLOWED_FORM_UPLOAD_MIME_TYPES: list[str] = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/csv",
    "application/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "video/mp4",
    "video/quicktime",
]

# Extension allowlist for form submission uploads. Always enforce this to avoid
# accidentally allowing executables/scripts when a form's allowed_mime_types is unset
# or overly broad (e.g. "application/*").
_FORM_UPLOAD_EXTENSION_TO_MIME_TYPES: dict[str, tuple[str, ...]] = {
    "pdf": ("application/pdf",),
    "png": ("image/png",),
    "jpg": ("image/jpeg",),
    "jpeg": ("image/jpeg",),
    "csv": ("text/csv", "application/csv"),
    "doc": ("application/msword",),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
    "xls": ("application/vnd.ms-excel",),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
    "mp4": ("video/mp4",),
    "mov": ("video/quicktime",),
}

_MIME_TYPE_ALIASES: dict[str, str] = {
    # Non-standard but commonly seen in the wild.
    "image/jpg": "image/jpeg",
}
_CUSTOM_TEXT_LIKE_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
}


def _unwrap_annotation(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    if origin in (UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return _unwrap_annotation(args[0])
        return annotation
    origin_name = str(origin)
    if "Annotated" in origin_name:
        args = get_args(annotation)
        if args:
            return _unwrap_annotation(args[0])
    return annotation


def _surrogate_field_type_from_annotation(annotation: Any) -> str | None:
    base = _unwrap_annotation(annotation)
    if base is bool:
        return "bool"
    if base is int:
        return "int"
    if base is Decimal:
        return "decimal"
    if base is date:
        return "date"
    if base is EmailStr:
        return "str"
    if base is str:
        return "str"
    if isinstance(base, type):
        if issubclass(base, bool):
            return "bool"
        if issubclass(base, int):
            return "int"
        if issubclass(base, Decimal):
            return "decimal"
        if issubclass(base, date):
            return "date"
        if issubclass(base, EmailStr):
            return "str"
        if issubclass(base, str):
            return "str"
    return None


def _build_surrogate_field_types() -> dict[str, str]:
    field_types: dict[str, str] = {}
    for field_name, model_field in SurrogateUpdate.model_fields.items():
        field_type = _surrogate_field_type_from_annotation(model_field.annotation)
        if field_type:
            field_types[field_name] = field_type
    return field_types


SURROGATE_FIELD_TYPES: dict[str, str] = _build_surrogate_field_types()
CRITICAL_SURROGATE_FIELDS = frozenset({"full_name", "email"})
_SURROGATE_FIELD_LABEL_OVERRIDES: dict[str, str] = {
    "full_name": "Full Name",
    "date_of_birth": "Date of Birth",
    "height_ft": "Height (ft)",
    "weight_lb": "Weight (lb)",
    "weight_kg": "Weight (kg)",
    "weight_lbs": "Weight (lbs)",
    "is_age_eligible": "Age Eligible",
    "is_citizen_or_pr": "US Citizen/PR",
    "is_non_smoker": "Non-Smoker",
    "num_csections": "Number of C-Sections",
}

logger = logging.getLogger(__name__)


def parse_schema(schema_json: dict[str, Any]) -> FormSchema:
    return FormSchema.model_validate(schema_json)


def flatten_fields(schema: FormSchema) -> dict[str, FormField]:
    fields: dict[str, FormField] = {}
    for page in schema.pages:
        for field in page.fields:
            if field.key in fields:
                raise ValueError(f"Duplicate field key: {field.key}")
            fields[field.key] = field
    return fields


def list_field_mappings(db: Session, form_id: uuid.UUID) -> list[FormFieldMapping]:
    return (
        db.query(FormFieldMapping)
        .filter(FormFieldMapping.form_id == form_id)
        .order_by(FormFieldMapping.field_key.asc())
        .all()
    )


def _humanize_surrogate_field_name(field_name: str) -> str:
    if field_name in _SURROGATE_FIELD_LABEL_OVERRIDES:
        return _SURROGATE_FIELD_LABEL_OVERRIDES[field_name]
    return field_name.replace("_", " ").title()


def list_surrogate_mapping_options() -> list[dict[str, Any]]:
    preferred_order = ("full_name", "email", "phone")
    ordered_fields: list[str] = []
    seen: set[str] = set()
    for field in preferred_order:
        if field in SURROGATE_FIELD_TYPES and field not in seen:
            ordered_fields.append(field)
            seen.add(field)
    for field in sorted(SURROGATE_FIELD_TYPES.keys()):
        if field not in seen:
            ordered_fields.append(field)
            seen.add(field)

    return [
        {
            "value": field_name,
            "label": _humanize_surrogate_field_name(field_name),
            "is_critical": field_name in CRITICAL_SURROGATE_FIELDS,
        }
        for field_name in ordered_fields
    ]


def build_application_link(base_url: str | None, token: str) -> str:
    cleaned_base = (base_url or "").strip().rstrip("/")
    if not cleaned_base:
        return f"/apply/{token}"
    return f"{cleaned_base}/apply/{token}"


def assert_dedicated_form_purpose(
    form: Form,
    *,
    allow_purpose_override: bool = False,
) -> None:
    if form.purpose == FormPurpose.SURROGATE_APPLICATION.value:
        return
    if allow_purpose_override:
        return
    raise ValueError(
        "Dedicated surrogate sends require purpose=surrogate_application. "
        "Set allow_purpose_override=true to intentionally send a different form."
    )


def create_submission_token(
    db: Session,
    org_id: uuid.UUID,
    form: Form,
    surrogate: Surrogate,
    user_id: uuid.UUID | None,
    expires_in_days: int,
    *,
    allow_purpose_override: bool = False,
) -> FormSubmissionToken:
    assert_dedicated_form_purpose(form, allow_purpose_override=allow_purpose_override)
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before sending")

    token = _generate_token(db)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    record = FormSubmissionToken(
        organization_id=org_id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        token=token,
        expires_at=expires_at,
        max_submissions=1,
        used_submissions=0,
        created_by_user_id=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_latest_active_token_for_surrogate(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
    *,
    form_id: uuid.UUID | None = None,
) -> FormSubmissionToken | None:
    now = datetime.now(timezone.utc)

    query = (
        db.query(FormSubmissionToken)
        .join(Form, Form.id == FormSubmissionToken.form_id)
        .filter(
            FormSubmissionToken.organization_id == org_id,
            FormSubmissionToken.surrogate_id == surrogate_id,
            FormSubmissionToken.revoked_at.is_(None),
            FormSubmissionToken.used_submissions < FormSubmissionToken.max_submissions,
            FormSubmissionToken.expires_at >= now,
            Form.status == FormStatus.PUBLISHED.value,
        )
    )
    if form_id:
        query = query.filter(FormSubmissionToken.form_id == form_id)

    return query.order_by(
        FormSubmissionToken.created_at.desc(), FormSubmissionToken.id.desc()
    ).first()


def get_or_create_submission_token(
    db: Session,
    org_id: uuid.UUID,
    form: Form,
    surrogate: Surrogate,
    user_id: uuid.UUID | None,
    expires_in_days: int,
    *,
    allow_purpose_override: bool = False,
    commit: bool = True,
) -> FormSubmissionToken:
    assert_dedicated_form_purpose(form, allow_purpose_override=allow_purpose_override)
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before sending")

    existing_token = get_latest_active_token_for_surrogate(
        db,
        org_id=org_id,
        surrogate_id=surrogate.id,
        form_id=form.id,
    )
    if existing_token:
        return existing_token

    token = _generate_token(db)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    record = FormSubmissionToken(
        organization_id=org_id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        token=token,
        expires_at=expires_at,
        max_submissions=1,
        used_submissions=0,
        created_by_user_id=user_id,
    )
    db.add(record)
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def get_valid_token(db: Session, token: str) -> FormSubmissionToken | None:
    record = db.query(FormSubmissionToken).filter(FormSubmissionToken.token == token).first()
    if not record:
        return None
    if record.revoked_at is not None:
        return None
    if record.used_submissions >= record.max_submissions:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return record


def get_token_row(db: Session, token: str) -> FormSubmissionToken | None:
    """Fetch a token row without applying validity rules (revoked/expired/used)."""
    return db.query(FormSubmissionToken).filter(FormSubmissionToken.token == token).first()


def get_token_by_id(
    db: Session, *, org_id: uuid.UUID, form_id: uuid.UUID, token_id: uuid.UUID
) -> FormSubmissionToken | None:
    return (
        db.query(FormSubmissionToken)
        .filter(
            FormSubmissionToken.organization_id == org_id,
            FormSubmissionToken.form_id == form_id,
            FormSubmissionToken.id == token_id,
        )
        .first()
    )


def create_submission(
    db: Session,
    token: FormSubmissionToken,
    form: Form,
    answers: dict[str, Any],
    files: list[UploadFile] | None = None,
    file_field_keys: list[str] | None = None,
) -> FormSubmission:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    schema = parse_schema(form.published_schema_json)
    _validate_answers(schema, answers)

    file_fields = _get_file_fields(schema, answers)
    resolved_file_field_keys = _resolve_file_field_keys(
        file_fields=file_fields,
        files=files or [],
        file_field_keys=file_field_keys,
    )
    _validate_required_file_fields(file_fields, resolved_file_field_keys)
    _validate_file_field_limits(file_fields, resolved_file_field_keys)

    existing = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.form_id == form.id, FormSubmission.surrogate_id == token.surrogate_id
        )
        .first()
    )
    upload_files = files or []
    validated_content_types = _validate_files(form, upload_files)

    mapping_snapshot = _snapshot_mappings(db, form.id)
    now = datetime.now(timezone.utc)

    if existing:
        submission = existing
        submission.token_id = token.id
        submission.status = FormSubmissionStatus.PENDING_REVIEW.value
        submission.source_mode = FormLinkMode.DEDICATED.value
        submission.match_status = FormSubmissionMatchStatus.LINKED.value
        submission.match_reason = "dedicated_token"
        submission.matched_at = now
        submission.answers_json = answers
        submission.schema_snapshot = form.published_schema_json
        submission.mapping_snapshot = mapping_snapshot
        submission.submitted_at = now
        submission.reviewed_at = None
        submission.reviewed_by_user_id = None
        submission.review_notes = None
        submission.applied_at = None
        db.query(FormSubmissionFile).filter(
            FormSubmissionFile.submission_id == submission.id,
            FormSubmissionFile.deleted_at.is_(None),
        ).update(
            {
                FormSubmissionFile.deleted_at: now,
                FormSubmissionFile.deleted_by_user_id: None,
            },
            synchronize_session=False,
        )
    else:
        submission = FormSubmission(
            organization_id=form.organization_id,
            form_id=form.id,
            surrogate_id=token.surrogate_id,
            token_id=token.id,
            source_mode=FormLinkMode.DEDICATED.value,
            status=FormSubmissionStatus.PENDING_REVIEW.value,
            match_status=FormSubmissionMatchStatus.LINKED.value,
            match_reason="dedicated_token",
            matched_at=now,
            answers_json=answers,
            schema_snapshot=form.published_schema_json,
            mapping_snapshot=mapping_snapshot,
            submitted_at=now,
        )
        db.add(submission)
        db.flush()

    for idx, file in enumerate(upload_files):
        field_key = resolved_file_field_keys[idx] if resolved_file_field_keys else None
        _store_submission_file(
            db,
            submission,
            file,
            form,
            field_key=field_key,
            content_type=validated_content_types[idx],
        )

    token.used_submissions += 1
    if token.used_submissions >= token.max_submissions:
        token.revoked_at = datetime.now(timezone.utc)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=form.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_RECEIVED,
        actor_user_id=None,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(form.id),
            "surrogate_id": str(token.surrogate_id),
        },
    )

    db.commit()
    db.refresh(submission)

    surrogate = db.query(Surrogate).filter(Surrogate.id == token.surrogate_id).first()
    if surrogate:
        # Notify assignee + admins (in-app)
        try:
            from app.services import notification_facade

            notification_facade.notify_form_submission_received(
                db=db,
                surrogate=surrogate,
                submission_id=submission.id,
            )
        except Exception:
            logger.debug(
                "notify_form_submission_received_failed",
                exc_info=True,
            )

        # Trigger workflows for submission (so org workflows can email admins/owner, etc.)
        try:
            from app.services import workflow_triggers

            workflow_triggers.trigger_form_submitted(
                db=db,
                org_id=surrogate.organization_id,
                form_id=form.id,
                submission_id=submission.id,
                submitted_at=submission.submitted_at,
                surrogate_id=surrogate.id,
                source_mode=FormLinkMode.DEDICATED.value,
                entity_owner_id=(
                    surrogate.owner_id
                    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id
                    else None
                ),
            )
        except Exception:
            logger.debug(
                "trigger_form_submitted_failed",
                exc_info=True,
            )

        # Best-effort: advance stage to application_submitted (never regress)
        try:
            from app.db.models import Pipeline
            from app.services import pipeline_service, surrogate_status_service

            current_stage = (
                pipeline_service.get_stage_by_id(db, surrogate.stage_id)
                if surrogate.stage_id
                else None
            )
            pipeline_id = (
                current_stage.pipeline_id
                if current_stage
                else pipeline_service.get_or_create_default_pipeline(
                    db, surrogate.organization_id
                ).id
            )

            target_stage = pipeline_service.get_stage_by_slug(
                db=db, pipeline_id=pipeline_id, slug="application_submitted"
            )
            if not target_stage:
                pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
                if pipeline:
                    pipeline_service.sync_missing_stages(db, pipeline, user_id=None)
                target_stage = pipeline_service.get_stage_by_slug(
                    db=db, pipeline_id=pipeline_id, slug="application_submitted"
                )

            if target_stage and surrogate.stage_id != target_stage.id:
                current_order = current_stage.order if current_stage else 0
                if current_order < target_stage.order:
                    old_stage_id = surrogate.stage_id
                    old_label = surrogate.status_label
                    old_slug = current_stage.slug if current_stage else None
                    now = datetime.now(timezone.utc)
                    surrogate_status_service.apply_status_change(
                        db=db,
                        surrogate=surrogate,
                        new_stage=target_stage,
                        old_stage_id=old_stage_id,
                        old_label=old_label,
                        old_slug=old_slug,
                        user_id=None,
                        reason="application_submitted via public form",
                        effective_at=now,
                        recorded_at=now,
                    )
        except Exception:
            logger.debug(
                "advance_stage_application_submitted_failed",
                exc_info=True,
            )

        # Best-effort: clear server-side draft (if any)
        try:
            from app.services import form_draft_service

            form_draft_service.delete_draft(
                db=db,
                org_id=form.organization_id,
                form_id=form.id,
                surrogate_id=token.surrogate_id,
            )
        except Exception:
            logger.debug(
                "delete_form_draft_failed",
                exc_info=True,
            )

    return submission


def list_form_submissions(
    db: Session,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    status: str | None = None,
    match_status: str | None = None,
    source_mode: str | None = None,
    limit: int | None = 200,
) -> list[FormSubmission]:
    query = db.query(FormSubmission).filter(
        FormSubmission.organization_id == org_id,
        FormSubmission.form_id == form_id,
    )
    if status:
        query = query.filter(FormSubmission.status == status)
    if match_status:
        query = query.filter(FormSubmission.match_status == match_status)
    if source_mode:
        query = query.filter(FormSubmission.source_mode == source_mode)
    query = query.order_by(FormSubmission.submitted_at.desc())
    if limit and limit > 0:
        query = query.limit(limit)
    return query.all()


def get_submission_by_surrogate(
    db: Session, org_id: uuid.UUID, form_id: uuid.UUID, surrogate_id: uuid.UUID
) -> FormSubmission | None:
    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.form_id == form_id,
            FormSubmission.surrogate_id == surrogate_id,
        )
        .first()
    )


def get_submission(
    db: Session, org_id: uuid.UUID, submission_id: uuid.UUID
) -> FormSubmission | None:
    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.id == submission_id,
        )
        .first()
    )


def get_latest_submission_for_surrogate(
    db: Session, org_id: uuid.UUID, surrogate_id: uuid.UUID
) -> FormSubmission | None:
    """Get the most recently submitted form submission for a surrogate (org-scoped)."""
    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.surrogate_id == surrogate_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )


def list_submission_files(
    db: Session, org_id: uuid.UUID, submission_id: uuid.UUID
) -> list[FormSubmissionFile]:
    return (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.organization_id == org_id,
            FormSubmissionFile.submission_id == submission_id,
            FormSubmissionFile.deleted_at.is_(None),
        )
        .order_by(FormSubmissionFile.created_at.asc())
        .all()
    )


def get_submission_file(
    db: Session, org_id: uuid.UUID, submission_id: uuid.UUID, file_id: uuid.UUID
) -> FormSubmissionFile | None:
    return (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.organization_id == org_id,
            FormSubmissionFile.submission_id == submission_id,
            FormSubmissionFile.id == file_id,
            FormSubmissionFile.deleted_at.is_(None),
        )
        .first()
    )


def add_submission_file(
    db: Session,
    org_id: uuid.UUID,
    submission: FormSubmission,
    file: UploadFile,
    field_key: str | None,
    user_id: uuid.UUID,
) -> FormSubmissionFile:
    """Add a file to an existing submission (staff edit mode)."""
    form = db.query(Form).filter(Form.id == submission.form_id).first()
    if not form:
        raise ValueError("Form not found")

    validated_content_type = _validate_file(form, file)

    schema_json = submission.schema_snapshot or form.published_schema_json
    if not schema_json:
        raise ValueError("Submission schema missing")

    schema = parse_schema(schema_json)
    file_fields = _get_file_fields(schema)
    resolved_keys = _resolve_file_field_keys(
        file_fields=file_fields,
        files=[file],
        file_field_keys=[field_key] if field_key else None,
    )
    resolved_field_key = resolved_keys[0] if resolved_keys else None

    if resolved_field_key:
        existing_field_count = (
            db.query(FormSubmissionFile)
            .filter(
                FormSubmissionFile.submission_id == submission.id,
                FormSubmissionFile.field_key == resolved_field_key,
                FormSubmissionFile.deleted_at.is_(None),
            )
            .count()
        )
        if existing_field_count >= PER_FILE_FIELD_MAX_COUNT:
            # Use direct indexing so static type checkers don't treat `.get()` as optional.
            label = (
                file_fields[resolved_field_key].label if resolved_field_key in file_fields else None
            )
            label_text = label or resolved_field_key
            raise ValueError(f"Maximum {PER_FILE_FIELD_MAX_COUNT} files allowed for {label_text}")

    existing_count = (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.submission_id == submission.id,
            FormSubmissionFile.deleted_at.is_(None),
        )
        .count()
    )
    max_count = form.max_file_count or DEFAULT_MAX_FILE_COUNT
    if existing_count >= max_count:
        raise ValueError(f"Maximum {max_count} files allowed")

    scan_enabled = getattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    checksum = calculate_checksum(file.file)
    processed_file = strip_exif_data(file.file, validated_content_type)
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    suffix = f".{ext}" if ext else ""
    storage_key = (
        f"{submission.organization_id}/form-submissions/{submission.id}/{uuid.uuid4()}{suffix}"
    )

    store_file(storage_key, processed_file, validated_content_type)
    register_storage_cleanup_on_rollback(db, storage_key)

    record = FormSubmissionFile(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        filename=file.filename or "upload",
        field_key=resolved_field_key,
        storage_key=storage_key,
        content_type=validated_content_type,
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=False,
    )
    db.add(record)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.ATTACHMENT_UPLOADED,
        actor_user_id=user_id,
        target_type="form_submission_file",
        target_id=record.id,
        details={
            "submission_id": str(submission.id),
            "surrogate_id": str(submission.surrogate_id),
            "filename": record.filename,
        },
    )

    db.flush()

    if scan_enabled:
        job_service.enqueue_job(
            db=db,
            org_id=org_id,
            job_type=JobType.FORM_SUBMISSION_FILE_SCAN,
            payload={"submission_file_id": str(record.id)},
            run_at=datetime.now(timezone.utc),
            commit=False,
        )
    return record


def soft_delete_submission_file(
    db: Session,
    org_id: uuid.UUID,
    submission: FormSubmission,
    file_record: FormSubmissionFile,
    user_id: uuid.UUID,
) -> bool:
    """Soft-delete a submission file (staff edit mode)."""
    if file_record.deleted_at is not None:
        return False

    filename = file_record.filename

    file_record.deleted_at = datetime.now(timezone.utc)
    file_record.deleted_by_user_id = user_id

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.ATTACHMENT_DELETED,
        actor_user_id=user_id,
        target_type="form_submission_file",
        target_id=file_record.id,
        details={
            "submission_id": str(submission.id),
            "surrogate_id": str(submission.surrogate_id),
            "filename": filename,
        },
    )

    db.flush()
    return True


def get_submission_file_download_url(
    db: Session,
    org_id: uuid.UUID,
    submission: FormSubmission,
    file_record: FormSubmissionFile,
    user_id: uuid.UUID,
) -> str | None:
    if file_record.scan_status in ("infected", "error"):
        return None
    if getattr(settings, "ATTACHMENT_SCAN_ENABLED", False) and file_record.scan_status != "clean":
        return None

    ext = file_record.filename.rsplit(".", 1)[-1].lower() if "." in file_record.filename else ""
    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.FORM_SUBMISSION_FILE_DOWNLOADED,
        actor_user_id=user_id,
        target_type="form_submission_file",
        target_id=file_record.id,
        details={
            "surrogate_id": str(submission.surrogate_id),
            "submission_id": str(submission.id),
            "file_ext": ext,
            "file_size": file_record.file_size,
        },
    )
    db.flush()

    return generate_signed_url(file_record.storage_key)


def mark_submission_file_scanned(
    db: Session, file_id: uuid.UUID, status: str
) -> FormSubmissionFile | None:
    record = db.query(FormSubmissionFile).filter(FormSubmissionFile.id == file_id).first()
    if not record:
        return None
    record.scan_status = status
    record.quarantined = status in ("infected", "error")
    db.flush()
    return record


def approve_submission(
    db: Session,
    submission: FormSubmission,
    reviewer_id: uuid.UUID,
    review_notes: str | None,
) -> FormSubmission:
    if submission.status != FormSubmissionStatus.PENDING_REVIEW.value:
        raise ValueError("Submission is not pending review")
    if not submission.surrogate_id:
        raise ValueError("Submission is not linked to a surrogate")

    surrogate = db.query(Surrogate).filter(Surrogate.id == submission.surrogate_id).first()
    if not surrogate:
        raise ValueError("Surrogate not found")

    mappings = _get_submission_mappings(db, submission)
    updates = _build_surrogate_updates(submission, mappings)

    if updates:
        from app.services import surrogate_service

        surrogate_update = SurrogateUpdate(**updates)
        surrogate_service.update_surrogate(
            db=db,
            surrogate=surrogate,
            data=surrogate_update,
            user_id=reviewer_id,
            org_id=submission.organization_id,
            commit=False,
        )

    now = datetime.now(timezone.utc)
    submission.status = FormSubmissionStatus.APPROVED.value
    submission.reviewed_at = now
    submission.reviewed_by_user_id = reviewer_id
    submission.review_notes = review_notes
    submission.applied_at = now

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=submission.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_APPROVED,
        actor_user_id=reviewer_id,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(submission.form_id),
            "surrogate_id": str(submission.surrogate_id),
        },
    )

    db.commit()
    db.refresh(submission)
    return submission


def reject_submission(
    db: Session,
    submission: FormSubmission,
    reviewer_id: uuid.UUID,
    review_notes: str | None,
) -> FormSubmission:
    if submission.status != FormSubmissionStatus.PENDING_REVIEW.value:
        raise ValueError("Submission is not pending review")

    submission.status = FormSubmissionStatus.REJECTED.value
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by_user_id = reviewer_id
    submission.review_notes = review_notes

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=submission.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_REJECTED,
        actor_user_id=reviewer_id,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(submission.form_id),
            "surrogate_id": str(submission.surrogate_id),
        },
    )

    db.commit()
    db.refresh(submission)
    return submission


def update_submission_answers(
    db: Session,
    submission: FormSubmission,
    updates: list[dict[str, Any]],
    user_id: uuid.UUID,
) -> tuple[dict[str, Any], list[str]]:
    """
    Update submission answers and sync mapped case fields.

    Returns:
        Tuple of (old_values dict, list of case fields updated)
    """
    if not submission.schema_snapshot:
        raise ValueError("Submission has no schema snapshot")

    schema = parse_schema(submission.schema_snapshot)
    fields = flatten_fields(schema)
    mappings = _get_submission_mappings(db, submission)
    mapping_by_key = {m["field_key"]: m["surrogate_field"] for m in mappings}

    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    surrogate_updates: dict[str, Any] = {}
    updated_surrogate_fields: list[str] = []

    for update in updates:
        field_key = update.get("field_key")
        value = update.get("value")

        if not field_key:
            continue

        if field_key not in fields:
            raise ValueError(f"Unknown field key: {field_key}")

        field = fields[field_key]
        if value is not None and value != "":
            _validate_field_value(field, value)

        old_values[field_key] = submission.answers_json.get(field_key)
        new_values[field_key] = value

        submission.answers_json[field_key] = value

        if field_key in mapping_by_key:
            surrogate_field = mapping_by_key[field_key]
            if surrogate_field in SURROGATE_FIELD_TYPES:
                try:
                    coerced = _coerce_surrogate_value(surrogate_field, value) if value else None
                    surrogate_updates[surrogate_field] = coerced
                    updated_surrogate_fields.append(surrogate_field)
                except ValueError:
                    pass

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(submission, "answers_json")

    if surrogate_updates and submission.surrogate_id:
        surrogate = db.query(Surrogate).filter(Surrogate.id == submission.surrogate_id).first()
        if surrogate:
            from app.services import surrogate_service

            surrogate_update = SurrogateUpdate(**surrogate_updates)
            surrogate_service.update_surrogate(
                db=db,
                surrogate=surrogate,
                data=surrogate_update,
                user_id=user_id,
                org_id=submission.organization_id,
                commit=False,
            )

    from app.services import activity_service

    if submission.surrogate_id:
        activity_service.log_activity(
            db=db,
            surrogate_id=submission.surrogate_id,
            organization_id=submission.organization_id,
            activity_type=SurrogateActivityType.APPLICATION_EDITED,
            actor_user_id=user_id,
            details={
                "changes": {k: {"old": old_values.get(k), "new": v} for k, v in new_values.items()},
                "surrogate_updates": updated_surrogate_fields,
            },
        )

    db.commit()
    db.refresh(submission)
    return old_values, updated_surrogate_fields


def _generate_token(db: Session) -> str:
    token = secrets.token_urlsafe(32)
    while (
        db.query(FormSubmissionToken).filter(FormSubmissionToken.token == token).first() is not None
    ):
        token = secrets.token_urlsafe(32)
    return token


def _validate_answers(schema: FormSchema, answers: dict[str, Any]) -> None:
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")
    fields = flatten_fields(schema)
    for key, field in fields.items():
        if not _is_field_visible(field, answers, fields):
            continue
        value = answers.get(key)
        if field.type == "file":
            continue
        if field.required and (value is None or value == "" or value == []):
            raise ValueError(f"Missing required field: {field.label}")
        if value is None or value == "":
            continue
        _validate_field_value(field, value)


def _validate_field_value(field: FormField, value: Any) -> None:
    field_type = field.type
    if field_type in {"text", "textarea", "email", "phone", "address"}:
        if not isinstance(value, str):
            raise ValueError(f"Field '{field.label}' must be a string")
        validation = field.validation
        if validation:
            if validation.min_length is not None and len(value) < validation.min_length:
                raise ValueError(
                    f"Field '{field.label}' must be at least {validation.min_length} characters"
                )
            if validation.max_length is not None and len(value) > validation.max_length:
                raise ValueError(
                    f"Field '{field.label}' must be at most {validation.max_length} characters"
                )
            if validation.pattern:
                try:
                    if re.fullmatch(validation.pattern, value) is None:
                        raise ValueError(f"Field '{field.label}' does not match required pattern")
                except re.error as exc:
                    raise ValueError(f"Invalid validation pattern for '{field.label}'") from exc
        return

    if field_type == "number":
        numeric_value: float | None = None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str):
            try:
                numeric_value = float(value)
            except ValueError:
                pass
        if numeric_value is None:
            raise ValueError(f"Field '{field.label}' must be a number")
        validation = field.validation
        if validation:
            if validation.min_value is not None and numeric_value < validation.min_value:
                raise ValueError(f"Field '{field.label}' must be at least {validation.min_value}")
            if validation.max_value is not None and numeric_value > validation.max_value:
                raise ValueError(f"Field '{field.label}' must be at most {validation.max_value}")
        return

    if field_type == "date":
        if isinstance(value, date):
            return
        if isinstance(value, str):
            try:
                date.fromisoformat(value)
                return
            except ValueError:
                pass
        raise ValueError(f"Field '{field.label}' must be a date (YYYY-MM-DD)")

    if field_type in {"select", "radio"}:
        if not isinstance(value, str):
            raise ValueError(f"Field '{field.label}' must be a string")
        if field.options:
            allowed = {o.value for o in field.options}
            if value not in allowed:
                raise ValueError(f"Invalid option for '{field.label}'")
        return

    if field_type == "multiselect":
        if not isinstance(value, list):
            raise ValueError(f"Field '{field.label}' must be a list")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"Field '{field.label}' must be a list of strings")
        if field.options:
            allowed = {o.value for o in field.options}
            for item in value:
                if item not in allowed:
                    raise ValueError(f"Invalid option for '{field.label}'")
        return

    if field_type == "checkbox":
        # Checkbox fields with options behave like a multiselect. Without options, treat as a boolean.
        if field.options:
            if not isinstance(value, list):
                raise ValueError(f"Field '{field.label}' must be a list")
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"Field '{field.label}' must be a list of strings")
            allowed = {o.value for o in field.options}
            for item in value:
                if item not in allowed:
                    raise ValueError(f"Invalid option for '{field.label}'")
            return

        if not isinstance(value, bool):
            raise ValueError(f"Field '{field.label}' must be a boolean")
        return

    if field_type == "file":
        return

    if field_type == "repeatable_table":
        _validate_repeatable_table(field, value)
        return

    raise ValueError(f"Unsupported field type: {field_type}")


def _validate_repeatable_table(field: FormField, value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError(f"Field '{field.label}' must be a list")
    columns = field.columns or []
    if not columns:
        raise ValueError(f"Field '{field.label}' must define columns")
    min_rows = field.min_rows
    max_rows = field.max_rows
    if min_rows is not None and len(value) < min_rows:
        raise ValueError(f"Field '{field.label}' requires at least {min_rows} rows")
    if max_rows is not None and len(value) > max_rows:
        raise ValueError(f"Field '{field.label}' allows at most {max_rows} rows")

    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"Field '{field.label}' rows must be objects")
        for column in columns:
            column_value = row.get(column.key)
            if column.required and (column_value is None or column_value == ""):
                raise ValueError(f"Missing required value: {column.label}")
            if column_value is None or column_value == "":
                continue
            _validate_table_column_value(field.label, column, column_value)


def _validate_table_column_value(field_label: str, column: FormFieldColumn, value: Any) -> None:
    column_type = column.type
    if column_type == "text":
        if not isinstance(value, str):
            raise ValueError(f"Column '{column.label}' must be a string")
        return

    if column_type == "number":
        if isinstance(value, (int, float)):
            return
        if isinstance(value, str):
            try:
                float(value)
                return
            except ValueError:
                pass
        raise ValueError(f"Column '{column.label}' must be a number")

    if column_type == "date":
        if isinstance(value, date):
            return
        if isinstance(value, str):
            try:
                date.fromisoformat(value)
                return
            except ValueError:
                pass
        raise ValueError(f"Column '{column.label}' must be a date (YYYY-MM-DD)")

    if column_type == "select":
        if not isinstance(value, str):
            raise ValueError(f"Column '{column.label}' must be a string")
        if column.options:
            allowed = {o.value for o in column.options}
            if value not in allowed:
                raise ValueError(f"Invalid option for '{column.label}'")
        return

    raise ValueError(f"Unsupported column type: {column_type}")


def _is_field_visible(
    field: FormField, answers: dict[str, Any], fields: dict[str, FormField]
) -> bool:
    condition = field.show_if
    if not condition:
        return True
    target_field = fields.get(condition.field_key)
    if not target_field:
        return True
    return _evaluate_condition(condition, answers.get(condition.field_key))


def _evaluate_condition(condition: FormFieldCondition, value: Any) -> bool:
    operator = condition.operator
    expected = condition.value

    if operator == "is_empty":
        return value is None or value == "" or value == []
    if operator == "is_not_empty":
        return not (value is None or value == "" or value == [])

    if operator == "equals":
        if expected is not None and isinstance(expected, str) and value is not None:
            return str(value) == expected
        return value == expected
    if operator == "not_equals":
        if expected is not None and isinstance(expected, str) and value is not None:
            return str(value) != expected
        return value != expected
    if operator == "contains":
        if isinstance(value, list):
            return expected in value if expected is not None else False
        if isinstance(value, str) and isinstance(expected, str):
            return expected in value
        return False
    if operator == "not_contains":
        if isinstance(value, list):
            return expected not in value if expected is not None else True
        if isinstance(value, str) and isinstance(expected, str):
            return expected not in value
        return True

    return True


def _validate_files(form: Form, files: list[UploadFile]) -> list[str]:
    if not files:
        return []
    max_count = form.max_file_count if form.max_file_count is not None else DEFAULT_MAX_FILE_COUNT
    if len(files) > max_count:
        raise ValueError(f"Maximum {max_count} files allowed")

    validated: list[str] = []
    for file in files:
        validated.append(_validate_file(form, file))
    return validated


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE_PREFIX = b"\xff\xd8\xff"
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_SIGNATURE_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_EXECUTABLE_SIGNATURE_PREFIXES = (
    b"MZ",  # Windows PE
    b"\x7fELF",  # Linux ELF
    b"\xfe\xed\xfa\xce",  # Mach-O (32-bit)
    b"\xfe\xed\xfa\xcf",  # Mach-O (64-bit)
    b"\xcf\xfa\xed\xfe",  # Mach-O (reverse endian)
    b"\xca\xfe\xba\xbe",  # Mach-O fat
    b"\xbe\xba\xfe\xca",  # Mach-O fat (reverse endian)
)


def _read_file_prefix(file: UploadFile, size: int) -> bytes:
    """Read bytes from the beginning of the upload without consuming the stream."""
    try:
        file.file.seek(0)
        return file.file.read(size)
    finally:
        file.file.seek(0)


def _zip_contains(file: UploadFile, name: str) -> bool:
    try:
        file.file.seek(0)
        with zipfile.ZipFile(file.file) as zf:
            try:
                zf.getinfo(name)
                return True
            except KeyError:
                return False
    except zipfile.BadZipFile:
        return False
    finally:
        file.file.seek(0)


def _is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    if b"\x00" in data:
        return False
    # Reject a high concentration of control characters (common binary heuristic).
    bad = 0
    for b in data:
        if b in (9, 10, 13):  # \t, \n, \r
            continue
        if b < 32 or b == 127:
            bad += 1
    return (bad / len(data)) <= 0.05


def _sniff_video_kind(file: UploadFile) -> str | None:
    head = _read_file_prefix(file, 16)
    if len(head) < 12:
        return None
    if head[4:8] != b"ftyp":
        return None
    major_brand = head[8:12]
    return "mov" if major_brand == b"qt  " else "mp4"


def _extension_mime_candidates(ext: str) -> tuple[str, ...]:
    built_in = _FORM_UPLOAD_EXTENSION_TO_MIME_TYPES.get(ext)
    if built_in:
        return built_in

    guessed, _ = mimetypes.guess_type(f"upload.{ext}")
    if not guessed:
        return ()
    normalized = _MIME_TYPE_ALIASES.get(guessed.lower(), guessed.lower())
    return (normalized,)


def _validate_extension_signature(ext: str, head: bytes, file: UploadFile) -> None:
    # Verify the actual file bytes match the extension (do NOT trust multipart Content-Type).
    if ext == "pdf":
        stripped = head.lstrip(b"\xef\xbb\xbf \t\r\n")
        if not stripped.startswith(b"%PDF-"):
            raise ValueError("File content does not match .pdf")
        return
    if ext == "png":
        if not head.startswith(_PNG_SIGNATURE):
            raise ValueError("File content does not match .png")
        return
    if ext in ("jpg", "jpeg"):
        if not head.startswith(_JPEG_SIGNATURE_PREFIX):
            raise ValueError("File content does not match .jpg/.jpeg")
        return
    if ext in ("doc", "xls"):
        if not head.startswith(_OLE_SIGNATURE):
            raise ValueError("File content does not match .doc/.xls")
        return
    if ext in ("docx", "xlsx"):
        if not head.startswith(_ZIP_SIGNATURE_PREFIXES):
            raise ValueError("File content does not match .docx/.xlsx")
        if not _zip_contains(file, "[Content_Types].xml"):
            raise ValueError("File content does not match .docx/.xlsx")
        if ext == "docx" and not _zip_contains(file, "word/document.xml"):
            raise ValueError("File content does not match .docx")
        if ext == "xlsx" and not _zip_contains(file, "xl/workbook.xml"):
            raise ValueError("File content does not match .xlsx")
        return
    if ext == "csv":
        sample = _read_file_prefix(file, 4096)
        if not _is_probably_text(sample):
            raise ValueError("File content does not match .csv")
        return
    if ext in ("mp4", "mov"):
        kind = _sniff_video_kind(file)
        if kind != ext:
            raise ValueError("File content does not match video type")
        return


def _validate_custom_extension_content(
    ext: str,
    candidates: tuple[str, ...],
    file: UploadFile,
) -> None:
    # For text-like custom types, reject binary payloads.
    # For other custom types, rely on extension policy + executable signature guard.
    is_text_like = any(
        mime.startswith("text/") or mime in _CUSTOM_TEXT_LIKE_MIME_TYPES for mime in candidates
    )
    if is_text_like:
        sample = _read_file_prefix(file, 4096)
        if not _is_probably_text(sample):
            raise ValueError(f"File content does not match .{ext}")


def _validate_file(form: Form, file: UploadFile) -> str:
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    max_size = (
        form.max_file_size_bytes
        if form.max_file_size_bytes is not None
        else DEFAULT_MAX_FILE_SIZE_BYTES
    )
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValueError(f"File size exceeds {max_mb:.0f} MB limit")

    if not file.filename:
        raise ValueError("Filename is required")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext in BLOCKED_EXTENSIONS:
        raise ValueError(f"File extension '.{ext}' not allowed")
    if not ext:
        raise ValueError("File type not allowed")

    # Determine allowed MIME patterns for the form. If unset/empty, use a safe default.
    allowed_patterns: list[str] = []
    for item in form.allowed_mime_types or []:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        allowed_patterns.append(_MIME_TYPE_ALIASES.get(cleaned, cleaned))
    if not allowed_patterns:
        allowed_patterns = DEFAULT_ALLOWED_FORM_UPLOAD_MIME_TYPES

    head = _read_file_prefix(file, 512)
    if head.startswith(_EXECUTABLE_SIGNATURE_PREFIXES):
        raise ValueError("Executable files are not allowed")

    candidates = _extension_mime_candidates(ext)
    if not candidates:
        raise ValueError("File type not allowed")

    if ext in _FORM_UPLOAD_EXTENSION_TO_MIME_TYPES:
        _validate_extension_signature(ext, head, file)
    else:
        _validate_custom_extension_content(ext, candidates, file)

    # Choose a canonical MIME type for storage/auditing based on the extension, but only
    # if it is allowed by the form's configured allowed_mime_types.
    for mime in candidates:
        if _mime_allowed(mime, allowed_patterns):
            return mime
    raise ValueError("File type not allowed")


def _mime_allowed(content_type: str, allowed: list[str]) -> bool:
    for item in allowed:
        item = item.strip()
        if not item:
            continue
        if item.endswith("/*"):
            prefix = item[:-1]
            if content_type.startswith(prefix):
                return True
        if content_type == item:
            return True
    return False


def _store_submission_file(
    db: Session,
    submission: FormSubmission,
    file: UploadFile,
    form: Form,
    field_key: str | None,
    content_type: str | None = None,
) -> None:
    # Prefer a validated content type from the caller. Fall back to UploadFile.content_type.
    # (We still verify content in `_validate_file` for public upload flows.)
    resolved_content_type = (
        content_type or file.content_type or ""
    ).strip() or "application/octet-stream"
    # Strip charset, etc.
    resolved_content_type = (
        resolved_content_type.split(";", 1)[0].strip() or "application/octet-stream"
    )

    scan_enabled = getattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    checksum = calculate_checksum(file.file)
    processed_file = strip_exif_data(file.file, resolved_content_type)
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    suffix = f".{ext}" if ext else ""
    storage_key = (
        f"{submission.organization_id}/form-submissions/{submission.id}/{uuid.uuid4()}{suffix}"
    )

    store_file(storage_key, processed_file, resolved_content_type)
    register_storage_cleanup_on_rollback(db, storage_key)

    record = FormSubmissionFile(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        filename=file.filename or "upload",
        field_key=field_key,
        storage_key=storage_key,
        content_type=resolved_content_type,
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=False,
    )
    db.add(record)
    db.flush()

    if scan_enabled:
        job_service.enqueue_job(
            db=db,
            org_id=submission.organization_id,
            job_type=JobType.FORM_SUBMISSION_FILE_SCAN,
            payload={"submission_file_id": str(record.id)},
            run_at=datetime.now(timezone.utc),
            commit=False,
        )


def _build_surrogate_updates(
    submission: FormSubmission, mappings: list[dict[str, str]]
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for mapping in mappings:
        field_key = mapping.get("field_key")
        surrogate_field = mapping.get("surrogate_field")
        if not field_key or not surrogate_field:
            continue
        if surrogate_field not in SURROGATE_FIELD_TYPES:
            continue
        value = submission.answers_json.get(field_key)
        if value in (None, ""):
            continue
        updates[surrogate_field] = _coerce_surrogate_value(surrogate_field, value)
    return updates


def _snapshot_mappings(db: Session, form_id: uuid.UUID) -> list[dict[str, str]]:
    return [
        {"field_key": mapping.field_key, "surrogate_field": mapping.surrogate_field}
        for mapping in list_field_mappings(db, form_id)
    ]


def _get_submission_mappings(db: Session, submission: FormSubmission) -> list[dict[str, str]]:
    if submission.mapping_snapshot is not None:
        return submission.mapping_snapshot
    return _snapshot_mappings(db, submission.form_id)


def _get_file_fields(
    schema: FormSchema, answers: dict[str, Any] | None = None
) -> dict[str, FormField]:
    fields: dict[str, FormField] = {}
    field_map = flatten_fields(schema)
    for page in schema.pages:
        for field in page.fields:
            if field.type == "file":
                if answers is not None and not _is_field_visible(field, answers, field_map):
                    continue
                fields[field.key] = field
    return fields


def _resolve_file_field_keys(
    file_fields: dict[str, FormField],
    files: list[UploadFile],
    file_field_keys: list[str] | None,
) -> list[str]:
    if not files:
        if file_field_keys:
            raise ValueError("file_field_keys provided without files")
        return []

    if not file_fields:
        raise ValueError("Form does not accept file uploads")

    provided_keys = file_field_keys or []
    field_keys = list(file_fields.keys())

    if len(file_fields) == 1:
        only_key = field_keys[0]
        if provided_keys:
            if len(provided_keys) != len(files):
                raise ValueError("file_field_keys length must match files")
            for key in provided_keys:
                if key != only_key:
                    raise ValueError(f"Unknown file field: {key}")
            return provided_keys
        return [only_key for _ in files]

    if not provided_keys:
        if len(files) == 1:
            # Gracefully map a single upload to the first configured file field.
            return [field_keys[0]]
        raise ValueError("file_field_keys required when multiple file fields are configured")
    if len(provided_keys) != len(files):
        raise ValueError("file_field_keys length must match files")
    for key in provided_keys:
        if key not in file_fields:
            raise ValueError(f"Unknown file field: {key}")
    return provided_keys


def _validate_required_file_fields(
    file_fields: dict[str, FormField], file_field_keys: list[str]
) -> None:
    required_keys = {key for key, field in file_fields.items() if field.required}
    if not required_keys:
        return
    provided = set(file_field_keys)
    missing = required_keys - provided
    if missing:
        missing_key = next(iter(missing))
        label = file_fields[missing_key].label or missing_key
        raise ValueError(f"Missing required file: {label}")


def _validate_file_field_limits(
    file_fields: dict[str, FormField], file_field_keys: list[str]
) -> None:
    if not file_field_keys:
        return

    counts: dict[str, int] = {}
    for key in file_field_keys:
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > PER_FILE_FIELD_MAX_COUNT:
            label = file_fields[key].label if key in file_fields else None
            label_text = label or key
            raise ValueError(f"Maximum {PER_FILE_FIELD_MAX_COUNT} files allowed for {label_text}")


def _coerce_surrogate_value(surrogate_field: str, value: Any) -> Any:
    field_type = SURROGATE_FIELD_TYPES.get(surrogate_field)
    if field_type == "str":
        return str(value)
    if field_type == "bool":
        return _parse_bool(value)
    if field_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer for {surrogate_field}") from exc
    if field_type == "decimal":
        if surrogate_field == "height_ft":
            transformed = transform_height_flexible(str(value))
            if transformed.success and transformed.value is not None:
                return transformed.value
            raise ValueError(f"Invalid height for {surrogate_field}")
        try:
            return Decimal(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid decimal for {surrogate_field}") from exc
    if field_type == "date":
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"Invalid date for {surrogate_field}") from exc
        raise ValueError(f"Invalid date for {surrogate_field}")
    return value


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes", "1", "y"}:
            return True
        if cleaned in {"false", "no", "0", "n"}:
            return False
    raise ValueError("Invalid boolean value")
