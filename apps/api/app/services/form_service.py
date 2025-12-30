"""Form service for application builder, submissions, and approvals."""

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import AuditEventType, FormStatus, FormSubmissionStatus
from app.db.models import (
    Case,
    Form,
    FormFieldMapping,
    FormLogo,
    FormSubmission,
    FormSubmissionFile,
    FormSubmissionToken,
)
from app.schemas.case import CaseUpdate
from app.schemas.forms import FormSchema, FormField
from app.services import audit_service, case_service
from app.services.attachment_service import (
    calculate_checksum,
    generate_signed_url,
    store_file,
    strip_exif_data,
)


DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FILE_COUNT = 10
FORM_LOGO_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
FORM_LOGO_ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg"}
FORM_LOGO_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def list_forms(db: Session, org_id: uuid.UUID) -> list[Form]:
    return (
        db.query(Form)
        .filter(Form.organization_id == org_id)
        .order_by(Form.updated_at.desc())
        .all()
    )


def get_form(db: Session, org_id: uuid.UUID, form_id: uuid.UUID) -> Form | None:
    return (
        db.query(Form)
        .filter(Form.organization_id == org_id, Form.id == form_id)
        .first()
    )


def create_form(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
    schema: dict | None,
    max_file_size_bytes: int | None,
    max_file_count: int | None,
    allowed_mime_types: list[str] | None,
) -> Form:
    max_size = (
        max_file_size_bytes
        if max_file_size_bytes is not None
        else DEFAULT_MAX_FILE_SIZE_BYTES
    )
    max_count = max_file_count if max_file_count is not None else DEFAULT_MAX_FILE_COUNT
    form = Form(
        organization_id=org_id,
        name=name,
        description=description,
        schema_json=schema,
        status=FormStatus.DRAFT.value,
        max_file_size_bytes=max_size,
        max_file_count=max_count,
        allowed_mime_types=allowed_mime_types,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    return form


def update_form(
    db: Session,
    form: Form,
    user_id: uuid.UUID,
    name: str | None,
    description: str | None,
    schema: dict | None,
    max_file_size_bytes: int | None,
    max_file_count: int | None,
    allowed_mime_types: list[str] | None,
) -> Form:
    if name is not None:
        form.name = name
    if description is not None:
        form.description = description
    if schema is not None:
        form.schema_json = schema
    if max_file_size_bytes is not None:
        form.max_file_size_bytes = max_file_size_bytes
    if max_file_count is not None:
        form.max_file_count = max_file_count
    if allowed_mime_types is not None:
        form.allowed_mime_types = allowed_mime_types
    form.updated_by_user_id = user_id

    db.commit()
    db.refresh(form)
    return form


def upload_form_logo(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    file: UploadFile,
) -> FormLogo:
    if not file.filename:
        raise ValueError("Logo filename is required")

    content_type = file.content_type or "application/octet-stream"
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > FORM_LOGO_MAX_FILE_SIZE_BYTES:
        max_mb = FORM_LOGO_MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise ValueError(f"Logo exceeds {max_mb:.0f} MB limit")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in FORM_LOGO_ALLOWED_EXTENSIONS:
        raise ValueError("Logo file type not allowed")
    if content_type not in FORM_LOGO_ALLOWED_MIME_TYPES:
        raise ValueError("Logo content type not allowed")

    logo_id = uuid.uuid4()
    storage_key = f"{org_id}/form-logos/{logo_id}.{ext}"
    processed_file = strip_exif_data(file.file, content_type)
    store_file(storage_key, processed_file)

    logo = FormLogo(
        id=logo_id,
        organization_id=org_id,
        storage_key=storage_key,
        filename=file.filename,
        content_type=content_type,
        file_size=file_size,
        created_by_user_id=user_id,
    )
    db.add(logo)
    db.commit()
    db.refresh(logo)
    return logo


def get_form_logo(
    db: Session, org_id: uuid.UUID, logo_id: uuid.UUID
) -> FormLogo | None:
    return (
        db.query(FormLogo)
        .filter(FormLogo.organization_id == org_id, FormLogo.id == logo_id)
        .first()
    )


def get_form_logo_by_id(db: Session, logo_id: uuid.UUID) -> FormLogo | None:
    return db.query(FormLogo).filter(FormLogo.id == logo_id).first()


def get_form_logo_public_url(logo: FormLogo) -> str:
    return f"/forms/public/logos/{logo.id}"


def get_form_logo_download_url(logo: FormLogo) -> str | None:
    backend = getattr(settings, "STORAGE_BACKEND", "local")
    if backend == "s3":
        return generate_signed_url(logo.storage_key)
    return None


def get_form_logo_local_path(logo: FormLogo) -> str:
    base_path = getattr(settings, "LOCAL_STORAGE_PATH", "/tmp/crm-attachments")
    return os.path.join(base_path, logo.storage_key)


def publish_form(db: Session, form: Form, user_id: uuid.UUID) -> Form:
    if not form.schema_json:
        raise ValueError("Form schema is required before publishing")

    form.published_schema_json = json.loads(json.dumps(form.schema_json))
    form.status = FormStatus.PUBLISHED.value
    form.updated_by_user_id = user_id
    db.commit()
    db.refresh(form)
    return form


def set_field_mappings(
    db: Session, form: Form, mappings: list[dict[str, str]]
) -> list[FormFieldMapping]:
    if not form.schema_json:
        raise ValueError("Form schema is required before mapping fields")
    schema = _parse_schema(form.schema_json)
    fields = _flatten_fields(schema)

    for mapping in mappings:
        field_key = mapping["field_key"]
        case_field = mapping["case_field"]
        if field_key not in fields:
            raise ValueError(f"Unknown field key: {field_key}")
        if case_field not in CASE_FIELD_TYPES:
            raise ValueError(f"Unsupported case field: {case_field}")

    db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form.id).delete()
    created: list[FormFieldMapping] = []
    for mapping in mappings:
        created.append(
            FormFieldMapping(
                form_id=form.id,
                field_key=mapping["field_key"],
                case_field=mapping["case_field"],
            )
        )
    db.add_all(created)
    db.commit()
    return created


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
    case: Case,
    user_id: uuid.UUID,
    expires_in_days: int,
) -> FormSubmissionToken:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before sending")

    existing = (
        db.query(FormSubmission)
        .filter(FormSubmission.form_id == form.id, FormSubmission.case_id == case.id)
        .first()
    )
    if existing:
        raise ValueError("Submission already exists for this case")

    token = _generate_token(db)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    record = FormSubmissionToken(
        organization_id=org_id,
        form_id=form.id,
        case_id=case.id,
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
    record = (
        db.query(FormSubmissionToken).filter(FormSubmissionToken.token == token).first()
    )
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
) -> FormSubmission:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    schema = _parse_schema(form.published_schema_json)
    _validate_answers(schema, answers)

    existing = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.form_id == form.id, FormSubmission.case_id == token.case_id
        )
        .first()
    )
    if existing:
        raise ValueError("Submission already exists for this case")

    upload_files = files or []
    _validate_files(form, upload_files)

    submission = FormSubmission(
        organization_id=form.organization_id,
        form_id=form.id,
        case_id=token.case_id,
        token_id=token.id,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        answers_json=answers,
        schema_snapshot=form.published_schema_json,
    )
    db.add(submission)
    db.flush()

    for file in upload_files:
        _store_submission_file(db, submission, file, form)

    token.used_submissions += 1
    if token.used_submissions >= token.max_submissions:
        token.revoked_at = datetime.now(timezone.utc)

    audit_service.log_event(
        db=db,
        org_id=form.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_RECEIVED,
        actor_user_id=None,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(form.id),
            "case_id": str(token.case_id),
        },
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


def get_submission_by_case(
    db: Session, org_id: uuid.UUID, form_id: uuid.UUID, case_id: uuid.UUID
) -> FormSubmission | None:
    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.form_id == form_id,
            FormSubmission.case_id == case_id,
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


def get_submission_file_download_url(
    db: Session,
    org_id: uuid.UUID,
    submission: FormSubmission,
    file_record: FormSubmissionFile,
    user_id: uuid.UUID,
) -> str | None:
    if file_record.quarantined:
        return None

    ext = (
        file_record.filename.rsplit(".", 1)[-1].lower()
        if "." in file_record.filename
        else ""
    )
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.FORM_SUBMISSION_FILE_DOWNLOADED,
        actor_user_id=user_id,
        target_type="form_submission_file",
        target_id=file_record.id,
        details={
            "case_id": str(submission.case_id),
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

    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise ValueError("Case not found")

    mappings = list_field_mappings(db, submission.form_id)
    updates = _build_case_updates(submission, mappings)

    if updates:
        case_update = CaseUpdate(**updates)
        case_service.update_case(
            db=db,
            case=case,
            data=case_update,
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

    audit_service.log_event(
        db=db,
        org_id=submission.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_APPROVED,
        actor_user_id=reviewer_id,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(submission.form_id),
            "case_id": str(submission.case_id),
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

    audit_service.log_event(
        db=db,
        org_id=submission.organization_id,
        event_type=AuditEventType.FORM_SUBMISSION_REJECTED,
        actor_user_id=reviewer_id,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "form_id": str(submission.form_id),
            "case_id": str(submission.case_id),
        },
    )

    db.commit()
    db.refresh(submission)
    return submission


def _generate_token(db: Session) -> str:
    token = secrets.token_urlsafe(32)
    while (
        db.query(FormSubmissionToken).filter(FormSubmissionToken.token == token).first()
        is not None
    ):
        token = secrets.token_urlsafe(32)
    return token


def _parse_schema(schema_json: dict) -> FormSchema:
    return FormSchema.model_validate(schema_json)


def _flatten_fields(schema: FormSchema) -> dict[str, FormField]:
    fields: dict[str, FormField] = {}
    for page in schema.pages:
        for field in page.fields:
            if field.key in fields:
                raise ValueError(f"Duplicate field key: {field.key}")
            fields[field.key] = field
    return fields


def _validate_answers(schema: FormSchema, answers: dict[str, Any]) -> None:
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")
    fields = _flatten_fields(schema)
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
    max_count = (
        form.max_file_count
        if form.max_file_count is not None
        else DEFAULT_MAX_FILE_COUNT
    )
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
    db: Session, submission: FormSubmission, file: UploadFile, form: Form
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
        f"{submission.organization_id}/form-submissions/"
        f"{submission.id}/{uuid.uuid4()}{suffix}"
    )

    store_file(storage_key, processed_file)

    record = FormSubmissionFile(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        filename=file.filename or "upload",
        storage_key=storage_key,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        checksum_sha256=checksum,
        scan_status="pending" if scan_enabled else "clean",
        quarantined=scan_enabled,
    )
    db.add(record)


CASE_FIELD_TYPES: dict[str, str] = {
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


def _build_case_updates(
    submission: FormSubmission, mappings: list[FormFieldMapping]
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for mapping in mappings:
        field_key = mapping.field_key
        case_field = mapping.case_field
        if case_field not in CASE_FIELD_TYPES:
            continue
        value = submission.answers_json.get(field_key)
        if value in (None, ""):
            continue
        updates[case_field] = _coerce_case_value(case_field, value)
    return updates


def _coerce_case_value(case_field: str, value: Any) -> Any:
    field_type = CASE_FIELD_TYPES.get(case_field)
    if field_type == "str":
        return str(value)
    if field_type == "bool":
        return _parse_bool(value)
    if field_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer for {case_field}") from exc
    if field_type == "decimal":
        try:
            return Decimal(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid decimal for {case_field}") from exc
    if field_type == "date":
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"Invalid date for {case_field}") from exc
        raise ValueError(f"Invalid date for {case_field}")
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
