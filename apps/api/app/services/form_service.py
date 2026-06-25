"""Form service for application builder and assets."""

import copy
import json
import os
import uuid
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import FormPurpose, FormStatus
from app.db.models import Form, FormFieldMapping, FormLogo, Organization
from app.schemas.forms import FormSchema
from app.services.attachment_service import (
    _get_local_storage_path,
    generate_signed_url,
    store_file,
    strip_exif_data,
)
from app.services.form_submission_service import (
    DEFAULT_MAX_FILE_COUNT,
    DEFAULT_MAX_FILE_SIZE_BYTES,
    REQUIRED_SHARED_INTAKE_SURROGATE_FIELDS,
    SURROGATE_FIELD_TYPES,
    flatten_fields,
    parse_schema,
)


FORM_LOGO_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
FORM_LOGO_ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg"}
FORM_LOGO_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
LEGACY_PUBLIC_LOGO_PREFIX = "/forms/public/logos/"
_UNSET = object()
SHARED_INTAKE_FIELD_LABELS = {
    "full_name": "Full Name",
    "date_of_birth": "Date of Birth",
    "phone": "Phone",
    "email": "Email",
}
SHARED_INTAKE_FIELD_TYPES = {
    "full_name": {"text", "textarea"},
    "date_of_birth": {"date"},
    "phone": {"phone", "text"},
    "email": {"email", "text"},
}
LEAD_CAPTURE_REQUIRED_IDENTITY_FIELDS = ("full_name",)
LEAD_CAPTURE_CONTACT_FIELDS = ("email", "phone")
LEAD_CAPTURE_BLOCKED_PRIVACY_SAFE_SENSITIVITIES = {
    "sensitive_health",
    "sensitive_reproductive",
    "sensitive_financial",
    "sensitive_legal",
    "free_text_unclassified",
    "file",
}
PUBLIC_SURROGATE_FIELD_DEFAULTS: dict[str, dict[str, Any]] = {
    "state": {
        "help_text": "Use the 2-letter state code, e.g. CA.",
        "validation": {
            "min_length": 2,
            "max_length": 2,
            "pattern": "^[A-Za-z]{2}$",
        },
    },
    "height_ft": {
        "type": "height",
    },
    "weight_lb": {
        "type": "number",
        "validation": {
            "min_value": 1,
            "max_value": 1000,
        },
    },
    "num_deliveries": {
        "type": "number",
        "validation": {
            "min_value": 1,
            "max_value": 20,
        },
    },
    "num_csections": {
        "type": "number",
        "validation": {
            "min_value": 0,
            "max_value": 20,
        },
    },
}


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _merge_validation_defaults(
    current: Any,
    defaults: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not defaults:
        return current if isinstance(current, dict) else None

    merged = dict(current) if isinstance(current, dict) else {}

    for key in ("min_length", "max_length", "pattern"):
        if defaults.get(key) is not None:
            merged[key] = defaults[key]

    if defaults.get("min_value") is not None:
        current_min = _coerce_number(merged.get("min_value"))
        default_min = _coerce_number(defaults.get("min_value"))
        if default_min is not None:
            merged["min_value"] = default_min if current_min is None else max(current_min, default_min)

    if defaults.get("max_value") is not None:
        current_max = _coerce_number(merged.get("max_value"))
        default_max = _coerce_number(defaults.get("max_value"))
        if default_max is not None:
            merged["max_value"] = default_max if current_max is None else min(current_max, default_max)

    return merged or None


def apply_public_surrogate_field_defaults(
    schema: dict | None,
    field_mappings_by_key: dict[str, str] | None = None,
) -> dict | None:
    """Apply canonical public-input defaults for known surrogate fields.

    Defaults are keyed by either the field key itself or the saved surrogate-field mapping,
    so custom reused fields get the same public validation as the preset library.
    """
    if not isinstance(schema, dict):
        return schema

    mappings = field_mappings_by_key or {}
    patched = copy.deepcopy(schema)
    for page in patched.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for field in page.get("fields") or []:
            if not isinstance(field, dict):
                continue
            field_key = field.get("key")
            if not isinstance(field_key, str):
                continue
            surrogate_field = mappings.get(field_key) or field_key
            defaults = PUBLIC_SURROGATE_FIELD_DEFAULTS.get(surrogate_field)
            if not defaults:
                continue

            default_type = defaults.get("type")
            if isinstance(default_type, str):
                field["type"] = default_type

            default_help = defaults.get("help_text")
            if isinstance(default_help, str) and not field.get("help_text"):
                field["help_text"] = default_help

            default_validation = defaults.get("validation")
            if isinstance(default_validation, dict):
                field["validation"] = _merge_validation_defaults(
                    field.get("validation"),
                    default_validation,
                )

    return patched


def _field_mappings_by_key(db: Session, form_id: uuid.UUID) -> dict[str, str]:
    return {
        mapping.field_key: mapping.surrogate_field
        for mapping in db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form_id).all()
    }


def list_forms(db: Session, org_id: uuid.UUID) -> list[Form]:
    return (
        db.query(Form).filter(Form.organization_id == org_id).order_by(Form.updated_at.desc()).all()
    )


def get_form(db: Session, org_id: uuid.UUID, form_id: uuid.UUID) -> Form | None:
    return db.query(Form).filter(Form.organization_id == org_id, Form.id == form_id).first()


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
    purpose: str = FormPurpose.SURROGATE_APPLICATION.value,
    default_application_email_template_id: uuid.UUID | None = None,
) -> Form:
    max_size = (
        max_file_size_bytes if max_file_size_bytes is not None else DEFAULT_MAX_FILE_SIZE_BYTES
    )
    max_count = max_file_count if max_file_count is not None else DEFAULT_MAX_FILE_COUNT
    schema = apply_public_surrogate_field_defaults(schema)
    form = Form(
        organization_id=org_id,
        name=name,
        description=description,
        purpose=purpose,
        schema_json=schema,
        status=FormStatus.DRAFT.value,
        max_file_size_bytes=max_size,
        max_file_count=max_count,
        allowed_mime_types=allowed_mime_types,
        default_application_email_template_id=default_application_email_template_id,
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
    purpose: str | None,
    schema: dict | None,
    max_file_size_bytes: int | None,
    max_file_count: int | None,
    allowed_mime_types: list[str] | None,
    default_application_email_template_id: uuid.UUID | None | object = _UNSET,
) -> Form:
    if name is not None:
        form.name = name
    if description is not None:
        form.description = description
    if purpose is not None:
        form.purpose = purpose
    if schema is not None:
        form.schema_json = apply_public_surrogate_field_defaults(
            schema,
            _field_mappings_by_key(db, form.id),
        )
    if max_file_size_bytes is not None:
        form.max_file_size_bytes = max_file_size_bytes
    if max_file_count is not None:
        form.max_file_count = max_file_count
    if allowed_mime_types is not None:
        form.allowed_mime_types = allowed_mime_types
    if default_application_email_template_id is not _UNSET:
        form.default_application_email_template_id = default_application_email_template_id
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
    store_file(storage_key, processed_file, content_type)

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


def get_form_logo(db: Session, org_id: uuid.UUID, logo_id: uuid.UUID) -> FormLogo | None:
    return (
        db.query(FormLogo)
        .filter(FormLogo.organization_id == org_id, FormLogo.id == logo_id)
        .first()
    )


def get_form_logo_by_id(db: Session, org_id: uuid.UUID, logo_id: uuid.UUID) -> FormLogo | None:
    return get_form_logo(db, org_id, logo_id)


def get_form_logo_public_url(logo: FormLogo) -> str:
    return f"/forms/public/{logo.organization_id}/logos/{logo.id}"


def normalize_form_schema_logo_url(schema: FormSchema, org_id: uuid.UUID) -> FormSchema:
    if not schema.logo_url:
        return schema
    if schema.logo_url.startswith(LEGACY_PUBLIC_LOGO_PREFIX):
        logo_id = schema.logo_url.removeprefix(LEGACY_PUBLIC_LOGO_PREFIX)
        return schema.model_copy(update={"logo_url": f"/forms/public/{org_id}/logos/{logo_id}"})
    return schema


def get_form_logo_download_url(logo: FormLogo) -> str | None:
    backend = getattr(settings, "STORAGE_BACKEND", "local")
    if backend == "s3":
        return generate_signed_url(logo.storage_key)
    return None


def get_form_logo_local_path(logo: FormLogo) -> str:
    return os.path.join(_get_local_storage_path(), logo.storage_key)


def _field_for_target(
    *,
    fields: dict,
    mappings: dict[str, str],
    target: str,
):
    field_key = mappings.get(target) or (target if target in fields else None)
    if not field_key:
        return None
    return fields.get(field_key)


def validate_lead_capture_schema(db: Session, form: Form) -> None:
    """Ensure lead-capture forms have contact identity and classified fields."""
    if not form.schema_json:
        raise ValueError("Form schema is required before publishing")

    schema = parse_schema(form.schema_json)
    fields = flatten_fields(schema)
    mappings = {
        mapping.surrogate_field: mapping.field_key
        for mapping in db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form.id).all()
    }

    unclassified = [
        field.label
        for field in fields.values()
        if not field.sensitivity or (field.type == "file" and field.sensitivity != "file")
    ]
    if unclassified:
        raise ValueError(
            "Lead capture fields require a sensitivity classification: " + ", ".join(unclassified)
        )

    missing: list[str] = []
    optional: list[str] = []
    incompatible: list[str] = []

    full_name = _field_for_target(fields=fields, mappings=mappings, target="full_name")
    if not full_name:
        missing.append("Full Name")
    elif full_name.type not in SHARED_INTAKE_FIELD_TYPES["full_name"]:
        incompatible.append("Full Name")
    elif not full_name.required:
        optional.append("Full Name")

    contact_fields = [
        _field_for_target(fields=fields, mappings=mappings, target=target)
        for target in LEAD_CAPTURE_CONTACT_FIELDS
    ]
    required_contact = [field for field in contact_fields if field and field.required]
    if not required_contact:
        missing.append("Email or Phone")
    for target, field in zip(LEAD_CAPTURE_CONTACT_FIELDS, contact_fields, strict=False):
        if not field:
            continue
        allowed_types = SHARED_INTAKE_FIELD_TYPES[target]
        if field.type not in allowed_types:
            incompatible.append(
                f"{SHARED_INTAKE_FIELD_LABELS[target]} ({', '.join(sorted(allowed_types))})"
            )

    if missing or optional or incompatible:
        parts: list[str] = []
        if missing:
            parts.append(f"missing required mappings or fields: {', '.join(missing)}")
        if optional:
            parts.append(f"must be marked required: {', '.join(optional)}")
        if incompatible:
            parts.append(f"use compatible field types for: {', '.join(incompatible)}")
        raise ValueError("Lead capture identity is incomplete; " + "; ".join(parts))


def validate_privacy_safe_lead_schema(db: Session, form: Form) -> None:
    """Block sensitive fields from privacy-safe advertising event surfaces."""
    schema_json = form.schema_json or form.published_schema_json
    if not schema_json:
        raise ValueError("Form schema is required")
    schema = parse_schema(schema_json)
    fields = flatten_fields(schema)
    blocked = [
        field.label
        for field in fields.values()
        if (
            field.type == "file"
            or not field.sensitivity
            or field.sensitivity in LEAD_CAPTURE_BLOCKED_PRIVACY_SAFE_SENSITIVITIES
        )
    ]
    if blocked:
        raise ValueError(
            "Privacy-safe lead tracking cannot be enabled while the form contains "
            "sensitive, file, or unclassified fields: " + ", ".join(blocked)
        )
    validate_lead_capture_schema(db, form)


def validate_shared_intake_identity_targets(db: Session, form: Form) -> None:
    """Ensure published public intake forms can satisfy their identity contract."""
    if not form.schema_json:
        raise ValueError("Form schema is required before publishing")
    if form.purpose == FormPurpose.LEAD_CAPTURE.value:
        validate_lead_capture_schema(db, form)
        return

    schema = parse_schema(form.schema_json)
    fields = flatten_fields(schema)
    mappings = {
        mapping.surrogate_field: mapping.field_key
        for mapping in db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form.id).all()
    }

    missing: list[str] = []
    incompatible: list[str] = []
    optional: list[str] = []

    for target in REQUIRED_SHARED_INTAKE_SURROGATE_FIELDS:
        field_key = mappings.get(target) or (target if target in fields else None)
        label = SHARED_INTAKE_FIELD_LABELS.get(target, target.replace("_", " ").title())
        if not field_key or field_key not in fields:
            missing.append(label)
            continue

        field = fields[field_key]
        allowed_types = SHARED_INTAKE_FIELD_TYPES.get(target)
        if allowed_types and field.type not in allowed_types:
            incompatible.append(f"{label} ({', '.join(sorted(allowed_types))})")
            continue
        if not field.required:
            optional.append(label)

    if missing or incompatible or optional:
        parts: list[str] = []
        if missing:
            parts.append(f"missing required mappings or fields: {', '.join(missing)}")
        if optional:
            parts.append(f"must be marked required: {', '.join(optional)}")
        if incompatible:
            parts.append(f"use compatible field types for: {', '.join(incompatible)}")
        raise ValueError("Shared intake identity is incomplete; " + "; ".join(parts))


def publish_form(db: Session, form: Form, user_id: uuid.UUID) -> Form:
    if not form.schema_json:
        raise ValueError("Form schema is required before publishing")
    form.schema_json = apply_public_surrogate_field_defaults(
        form.schema_json,
        _field_mappings_by_key(db, form.id),
    )
    if settings.FORMS_SHARED_INTAKE:
        validate_shared_intake_identity_targets(db, form)

    form.published_schema_json = json.loads(json.dumps(form.schema_json))
    form.status = FormStatus.PUBLISHED.value
    form.updated_by_user_id = user_id
    db.commit()
    ensure_default_surrogate_application_form(db, form.organization_id)
    db.refresh(form)
    return form


def _get_org(db: Session, org_id: uuid.UUID) -> Organization | None:
    return db.query(Organization).filter(Organization.id == org_id).first()


def ensure_default_surrogate_application_form(
    db: Session,
    org_id: uuid.UUID,
    *,
    commit: bool = True,
) -> uuid.UUID | None:
    """
    Ensure org default points to one published surrogate application form, if available.

    Returns the default form ID after reconciliation.
    """
    org = _get_org(db, org_id)
    if not org:
        return None

    candidates = (
        db.query(Form)
        .filter(
            Form.organization_id == org_id,
            Form.status == FormStatus.PUBLISHED.value,
            Form.purpose == FormPurpose.SURROGATE_APPLICATION.value,
        )
        .order_by(Form.updated_at.desc(), Form.created_at.desc())
        .all()
    )
    candidate_ids = {candidate.id for candidate in candidates}

    next_default: uuid.UUID | None
    if not candidates:
        next_default = None
    elif org.default_surrogate_application_form_id in candidate_ids:
        next_default = org.default_surrogate_application_form_id
    else:
        next_default = candidates[0].id

    if org.default_surrogate_application_form_id == next_default:
        return next_default

    org.default_surrogate_application_form_id = next_default
    if commit:
        db.commit()
    else:
        db.flush()
    return next_default


def get_default_surrogate_application_form(db: Session, org_id: uuid.UUID) -> Form | None:
    default_form_id = ensure_default_surrogate_application_form(db, org_id, commit=False)
    if not default_form_id:
        return None
    return get_form(db, org_id, default_form_id)


def set_default_surrogate_application_form(
    db: Session,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
) -> Form:
    form = get_form(db, org_id, form_id)
    if not form:
        raise ValueError("Form not found")
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Default surrogate application form must be published")
    if form.purpose != FormPurpose.SURROGATE_APPLICATION.value:
        raise ValueError(
            "Default surrogate application form must have purpose=surrogate_application"
        )

    org = _get_org(db, org_id)
    if not org:
        raise ValueError("Organization not found")

    if org.default_surrogate_application_form_id != form.id:
        org.default_surrogate_application_form_id = form.id
        db.commit()
    return form


def set_field_mappings(
    db: Session, form: Form, mappings: list[dict[str, str]]
) -> list[FormFieldMapping]:
    if not form.schema_json:
        raise ValueError("Form schema is required before mapping fields")
    schema = parse_schema(form.schema_json)
    fields = flatten_fields(schema)

    for mapping in mappings:
        field_key = mapping["field_key"]
        surrogate_field = mapping["surrogate_field"]
        if field_key not in fields:
            raise ValueError(f"Unknown field key: {field_key}")
        if surrogate_field not in SURROGATE_FIELD_TYPES:
            raise ValueError(f"Unsupported surrogate field: {surrogate_field}")

    field_key_set: set[str] = set()
    surrogate_field_set: set[str] = set()
    for mapping in mappings:
        field_key = mapping["field_key"]
        surrogate_field = mapping["surrogate_field"]
        if field_key in field_key_set:
            raise ValueError(f"Duplicate field key: {field_key}")
        if surrogate_field in surrogate_field_set:
            raise ValueError(f"Duplicate surrogate field: {surrogate_field}")
        field_key_set.add(field_key)
        surrogate_field_set.add(surrogate_field)

    form.schema_json = apply_public_surrogate_field_defaults(
        form.schema_json,
        {mapping["field_key"]: mapping["surrogate_field"] for mapping in mappings},
    )

    db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form.id).delete()
    created: list[FormFieldMapping] = []
    for mapping in mappings:
        created.append(
            FormFieldMapping(
                form_id=form.id,
                field_key=mapping["field_key"],
                surrogate_field=mapping["surrogate_field"],
            )
        )
    db.add_all(created)
    db.commit()
    return created


def delete_form(db: Session, form: Form) -> None:
    """Permanently delete a form and all related records (via FK cascades)."""
    org_id = form.organization_id
    db.delete(form)
    db.commit()
    ensure_default_surrogate_application_form(db, org_id)
