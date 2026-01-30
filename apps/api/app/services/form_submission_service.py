"""Form submission service for tokens, submissions, and review flows."""

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import AuditEventType, FormStatus, FormSubmissionStatus, SurrogateActivityType
from app.db.models import (
    Form,
    FormFieldMapping,
    FormSubmission,
    FormSubmissionFile,
    FormSubmissionToken,
    Surrogate,
)
from app.schemas.forms import FormField, FormSchema
from app.schemas.surrogate import SurrogateUpdate
from app.services.attachment_service import (
    calculate_checksum,
    generate_signed_url,
    register_storage_cleanup_on_rollback,
    store_file,
    strip_exif_data,
)


DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FILE_COUNT = 10
PER_FILE_FIELD_MAX_COUNT = 5

SURROGATE_FIELD_TYPES: dict[str, str] = {
    "full_name": "str",
    "email": "str",
    "phone": "str",
    "state": "str",
    "date_of_birth": "date",
    "race": "str",
    "height_ft": "decimal",
    "weight_lb": "int",
    "is_age_eligible": "bool",
    "is_citizen_or_pr": "bool",
    "has_child": "bool",
    "is_non_smoker": "bool",
    "has_surrogate_experience": "bool",
    "num_deliveries": "int",
    "num_csections": "int",
    "is_priority": "bool",
}


def parse_schema(schema_json: dict) -> FormSchema:
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


def create_submission_token(
    db: Session,
    org_id: uuid.UUID,
    form: Form,
    surrogate: Surrogate,
    user_id: uuid.UUID,
    expires_in_days: int,
) -> FormSubmissionToken:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before sending")

    existing = (
        db.query(FormSubmission)
        .filter(FormSubmission.form_id == form.id, FormSubmission.surrogate_id == surrogate.id)
        .first()
    )
    if existing:
        raise ValueError("Submission already exists for this surrogate")

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

    file_fields = _get_file_fields(schema)
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
    if existing:
        raise ValueError("Submission already exists for this surrogate")

    upload_files = files or []
    _validate_files(form, upload_files)

    mapping_snapshot = _snapshot_mappings(db, form.id)

    submission = FormSubmission(
        organization_id=form.organization_id,
        form_id=form.id,
        surrogate_id=token.surrogate_id,
        token_id=token.id,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        answers_json=answers,
        schema_snapshot=form.published_schema_json,
        mapping_snapshot=mapping_snapshot,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    db.flush()

    for idx, file in enumerate(upload_files):
        field_key = resolved_file_field_keys[idx] if resolved_file_field_keys else None
        _store_submission_file(db, submission, file, form, field_key=field_key)

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

    surrogate = db.query(Surrogate).filter(Surrogate.id == token.surrogate_id).first()
    if surrogate:
        from app.services import notification_facade

        notification_facade.notify_form_submission_received(
            db=db,
            surrogate=surrogate,
            submission_id=submission.id,
        )

    db.commit()
    db.refresh(submission)
    return submission


def list_form_submissions(
    db: Session, org_id: uuid.UUID, form_id: uuid.UUID, status: str | None = None
) -> list[FormSubmission]:
    query = db.query(FormSubmission).filter(
        FormSubmission.organization_id == org_id,
        FormSubmission.form_id == form_id,
    )
    if status:
        query = query.filter(FormSubmission.status == status)
    return query.order_by(FormSubmission.submitted_at.desc()).all()


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

    _validate_file(form, file)

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
            label = file_fields.get(resolved_field_key).label if resolved_field_key in file_fields else None
            label_text = label or resolved_field_key
            raise ValueError(
                f"Maximum {PER_FILE_FIELD_MAX_COUNT} files allowed for {label_text}"
            )

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
    processed_file = strip_exif_data(file.file, file.content_type or "")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    suffix = f".{ext}" if ext else ""
    storage_key = (
        f"{submission.organization_id}/form-submissions/{submission.id}/{uuid.uuid4()}{suffix}"
    )

    store_file(storage_key, processed_file)
    register_storage_cleanup_on_rollback(db, storage_key)

    record = FormSubmissionFile(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        filename=file.filename or "upload",
        field_key=resolved_field_key,
        storage_key=storage_key,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=scan_enabled,
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
    if file_record.quarantined:
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


def approve_submission(
    db: Session,
    submission: FormSubmission,
    reviewer_id: uuid.UUID,
    review_notes: str | None,
) -> FormSubmission:
    if submission.status != FormSubmissionStatus.PENDING_REVIEW.value:
        raise ValueError("Submission is not pending review")

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

    if surrogate_updates:
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
        value = answers.get(key)
        if field.type == "file":
            continue
        if field.required and (value is None or value == ""):
            raise ValueError(f"Missing required field: {field.label}")
        if value is None or value == "":
            continue
        _validate_field_value(field, value)


def _validate_field_value(field: FormField, value: Any) -> None:
    field_type = field.type
    if field_type in {"text", "textarea", "email", "phone", "address"}:
        if not isinstance(value, str):
            raise ValueError(f"Field '{field.label}' must be a string")
        return

    if field_type == "number":
        if isinstance(value, (int, float)):
            return
        if isinstance(value, str):
            try:
                float(value)
                return
            except ValueError:
                pass
        raise ValueError(f"Field '{field.label}' must be a number")

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

    if field_type in {"multiselect", "checkbox"}:
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

    if field_type == "file":
        return

    raise ValueError(f"Unsupported field type: {field_type}")


def _validate_files(form: Form, files: list[UploadFile]) -> None:
    if not files:
        return
    max_count = form.max_file_count if form.max_file_count is not None else DEFAULT_MAX_FILE_COUNT
    if len(files) > max_count:
        raise ValueError(f"Maximum {max_count} files allowed")

    for file in files:
        _validate_file(form, file)


def _validate_file(form: Form, file: UploadFile) -> None:
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

    allowed = form.allowed_mime_types
    if allowed:
        if not _mime_allowed(file.content_type or "", allowed):
            raise ValueError(f"Content type '{file.content_type}' not allowed")


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
) -> None:
    scan_enabled = getattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    checksum = calculate_checksum(file.file)
    processed_file = strip_exif_data(file.file, file.content_type or "")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    suffix = f".{ext}" if ext else ""
    storage_key = (
        f"{submission.organization_id}/form-submissions/{submission.id}/{uuid.uuid4()}{suffix}"
    )

    store_file(storage_key, processed_file)
    register_storage_cleanup_on_rollback(db, storage_key)

    record = FormSubmissionFile(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        filename=file.filename or "upload",
        field_key=field_key,
        storage_key=storage_key,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=scan_enabled,
    )
    db.add(record)


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


def _get_submission_mappings(
    db: Session, submission: FormSubmission
) -> list[dict[str, str]]:
    if submission.mapping_snapshot is not None:
        return submission.mapping_snapshot
    return _snapshot_mappings(db, submission.form_id)


def _get_file_fields(schema: FormSchema) -> dict[str, FormField]:
    fields: dict[str, FormField] = {}
    for page in schema.pages:
        for field in page.fields:
            if field.type == "file":
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
            label = file_fields.get(key).label if key in file_fields else None
            label_text = label or key
            raise ValueError(
                f"Maximum {PER_FILE_FIELD_MAX_COUNT} files allowed for {label_text}"
            )


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
