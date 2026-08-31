"""Meta Lead service - ingestion and conversion to surrogates."""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import AlertSeverity, AlertType, SurrogateSource
from app.db.models import (
    Donor,
    MetaAd,
    MetaAdPlatformDaily,
    MetaForm,
    MetaLead,
    Organization,
    Surrogate,
)
from app.db.session import SessionLocal
from app.schemas.donor import DonorCreate
from app.schemas.surrogate import SurrogateCreate
from app.services import (
    custom_field_service,
    donor_service,
    surrogate_input_normalization_service,
    surrogate_service,
)
from app.services.import_transformers import (
    get_suggested_transformer,
    transform_height_flexible,
    transform_int_flexible,
    transform_value,
)
from app.utils.datetime_parsing import parse_datetime_with_timezone

logger = logging.getLogger(__name__)
REQUIRED_CONVERSION_FIELDS = {"full_name", "email"}


def _safe_conversion_error(error: Exception) -> str:
    """Return diagnostic context that cannot serialize lead or SQL parameters."""
    error_class = type(error).__name__
    if isinstance(error, IntegrityError):
        constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if isinstance(constraint_name, str) and constraint_name and all(
            character.isalnum() or character in {"_", "-", "."}
            for character in constraint_name
        ):
            return f"{error_class} ({constraint_name[:100]})"
    if isinstance(error, ValidationError):
        return f"{error_class} ({error.error_count()} validation errors)"
    return error_class


def _mark_conversion_failed(
    db: Session,
    error: Exception,
    *,
    persisted_lead_id: UUID | None,
    organization_id: UUID | None,
    external_meta_lead_id: str | None,
    unmapped_fields: dict | None = None,
    emit_alert: bool = False,
) -> None:
    """Persist convert_failed state after a failed transaction."""
    error_message = _safe_conversion_error(error)
    db.rollback()

    isolated = SessionLocal()
    try:
        persisted_lead = isolated.get(MetaLead, persisted_lead_id) if persisted_lead_id else None
        if not persisted_lead and organization_id and external_meta_lead_id:
            persisted_lead = (
                isolated.query(MetaLead)
                .filter(
                    MetaLead.organization_id == organization_id,
                    MetaLead.meta_lead_id == external_meta_lead_id,
                )
                .first()
            )
        if not persisted_lead:
            return

        persisted_lead.conversion_error = error_message
        if unmapped_fields is not None:
            persisted_lead.unmapped_fields = unmapped_fields or None
        isolated.commit()

        if emit_alert:
            _record_conversion_failure_alert(persisted_lead, error)
    finally:
        isolated.close()


def _is_mapping_related_conversion_failure(error: Exception) -> bool:
    """Classify whether a conversion failure should send the user back to form mapping."""
    if isinstance(error, IntegrityError):
        return False

    message = str(error).lower()
    if any(
        marker in message
        for marker in (
            "duplicate key value",
            "unique constraint",
            "already converted",
            "already has a linked surrogate",
            "already has a linked donor",
            "active donor with this email",
        )
    ):
        return False

    if isinstance(error, (ValidationError, ValueError)):
        return True

    return any(
        marker in message
        for marker in (
            "mapped field",
            "mapping",
            "validation",
            "invalid",
            "required field",
            "transform",
            "parse",
        )
    )


def _ensure_review_task_for_mapping_conversion_failure(
    db: Session,
    organization_id: UUID | None,
    meta_form_id: str | None,
    error: Exception,
) -> None:
    if not organization_id or not meta_form_id or not _is_mapping_related_conversion_failure(error):
        return

    try:
        from app.services import meta_form_mapping_service

        form = meta_form_mapping_service.get_form_by_external_id(
            db,
            organization_id,
            meta_form_id,
        )
        if not form:
            return

        meta_form_mapping_service.ensure_mapping_review_task(
            db,
            form,
            reason=f"Mapping conversion failed: {_safe_conversion_error(error)}",
        )
    except Exception as exc:
        logger.warning(
            "Failed to create mapping review task after conversion failure",
            extra={"error_class": type(exc).__name__},
        )


def _configured_form_lead_kind(
    db: Session,
    org_id: UUID,
    meta_form_id: str | None,
) -> str | None:
    """Resolve a reviewed form classification without freezing an unmapped default."""
    if not meta_form_id:
        return None
    form = db.scalar(
        select(MetaForm).where(
            MetaForm.organization_id == org_id,
            MetaForm.form_external_id == meta_form_id,
        )
    )
    if not form or form.mapping_status == "unmapped":
        return None
    return form.lead_kind


def store_meta_lead(
    db: Session,
    org_id: UUID,
    meta_lead_id: str,
    field_data: dict,
    raw_payload: dict | None = None,
    field_data_raw: dict | None = None,
    meta_form_id: str | None = None,
    meta_page_id: str | None = None,
    meta_created_time: datetime | None = None,
    custom_disclaimer_responses: list | None = None,
    meta_form_legal_snapshot_id: UUID | None = None,
) -> tuple[MetaLead | None, str | None]:
    """
    Store a raw Meta lead.

    Args:
        field_data: Normalized field data (scalars for conversion)
        field_data_raw: Raw field data preserving multi-select arrays (for form analysis)

    Returns:
        (meta_lead, error) - meta_lead is None if error
    """
    # Idempotent store: if the lead already exists, update it with any new data.
    existing = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            MetaLead.meta_lead_id == meta_lead_id,
        )
        .first()
    )

    if existing:
        existing.field_data = field_data
        if raw_payload is not None:
            existing.raw_payload = raw_payload
        if field_data_raw is not None:
            existing.field_data_raw = field_data_raw
        if meta_form_id is not None:
            existing.meta_form_id = meta_form_id
        if meta_page_id is not None:
            existing.meta_page_id = meta_page_id
        if meta_created_time is not None:
            existing.meta_created_time = meta_created_time
        if custom_disclaimer_responses is not None:
            existing.custom_disclaimer_responses = custom_disclaimer_responses
        if meta_form_legal_snapshot_id is not None:
            existing.meta_form_legal_snapshot_id = meta_form_legal_snapshot_id
        if existing.lead_kind is None:
            existing.lead_kind = _configured_form_lead_kind(
                db,
                org_id,
                meta_form_id or existing.meta_form_id,
            )
        db.commit()
        db.refresh(existing)
        return existing, None

    lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=meta_lead_id,
        meta_form_id=meta_form_id,
        meta_page_id=meta_page_id,
        lead_kind=_configured_form_lead_kind(db, org_id, meta_form_id),
        field_data=field_data,
        field_data_raw=field_data_raw,
        raw_payload=raw_payload,
        meta_created_time=meta_created_time,
        custom_disclaimer_responses=custom_disclaimer_responses,
        meta_form_legal_snapshot_id=meta_form_legal_snapshot_id,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead, None


def enrich_platform_from_insights(db: Session, meta_lead: MetaLead) -> str | None:
    """
    Populate meta_platform on a lead using cached ad-level insights.

    Returns the platform string if set, else None.
    """
    fields_raw = meta_lead.field_data_raw or meta_lead.field_data or {}
    platform = (
        fields_raw.get("meta_platform")
        or fields_raw.get("platform")
        or fields_raw.get("publisher_platform")
    )
    if platform:
        return str(platform)

    ad_id = fields_raw.get("meta_ad_id") or fields_raw.get("ad_id")
    if not ad_id:
        return None

    created_at = meta_lead.meta_created_time or meta_lead.received_at
    if not created_at:
        return None

    spend_date = created_at.date()

    platform_row = (
        db.query(MetaAdPlatformDaily)
        .filter(
            MetaAdPlatformDaily.organization_id == meta_lead.organization_id,
            MetaAdPlatformDaily.ad_external_id == str(ad_id),
            MetaAdPlatformDaily.spend_date == spend_date,
        )
        .order_by(MetaAdPlatformDaily.leads.desc(), MetaAdPlatformDaily.impressions.desc())
        .first()
    )
    if not platform_row:
        return None

    platform_value = platform_row.platform

    raw_updated = dict(meta_lead.field_data_raw or {})
    raw_updated["meta_platform"] = platform_value
    meta_lead.field_data_raw = raw_updated

    normalized = dict(meta_lead.field_data or {})
    normalized.setdefault("meta_platform", platform_value)
    meta_lead.field_data = normalized

    db.commit()
    return platform_value


def backfill_platform_for_date_range(
    db: Session,
    org_id: UUID,
    date_start: date,
    date_end: date,
    ad_ids: set[str] | None = None,
) -> int:
    """
    Backfill meta_platform for leads missing it in a date range.

    Returns number of leads updated.
    """
    platform_expr = func.coalesce(
        MetaLead.field_data_raw["meta_platform"].astext,
        MetaLead.field_data_raw["platform"].astext,
        MetaLead.field_data_raw["publisher_platform"].astext,
        MetaLead.field_data["meta_platform"].astext,
        MetaLead.field_data["platform"].astext,
        MetaLead.field_data["publisher_platform"].astext,
    )

    query = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            func.coalesce(MetaLead.meta_created_time, MetaLead.received_at).between(
                datetime.combine(date_start, datetime.min.time(), tzinfo=UTC),
                datetime.combine(date_end, datetime.max.time(), tzinfo=UTC),
            ),
            func.nullif(platform_expr, "").is_(None),
        )
        .order_by(MetaLead.received_at.desc())
    )

    if ad_ids:
        ad_id_expr = func.coalesce(
            MetaLead.field_data_raw["meta_ad_id"].astext,
            MetaLead.field_data_raw["ad_id"].astext,
            MetaLead.field_data["meta_ad_id"].astext,
            MetaLead.field_data["ad_id"].astext,
        )
        query = query.filter(ad_id_expr.in_([str(a) for a in ad_ids]))

    leads = query.all()
    updated = 0
    for lead in leads:
        if enrich_platform_from_insights(db, lead):
            updated += 1

    return updated


def convert_to_surrogate_with_mapping(
    db: Session,
    meta_lead: MetaLead,
    mapping_rules: list[dict],
    unknown_column_behavior: str = "metadata",
    user_id: UUID | None = None,
) -> tuple[Surrogate | None, str | None]:
    """
    Convert a Meta lead using explicit mapping rules.

    Args:
        meta_lead: Lead to convert
        mapping_rules: List of column mapping dicts
        unknown_column_behavior: ignore|metadata|warn for unmapped columns
    """
    # Prevent double conversion
    if meta_lead.is_converted:
        return None, "Meta lead already converted"
    if meta_lead.converted_surrogate_id:
        return None, "Meta lead already has a linked surrogate"

    field_data = dict(meta_lead.field_data_raw or meta_lead.field_data or {})
    tracking_fields = _build_meta_tracking_fields(db, meta_lead)
    for key, value in tracking_fields.items():
        field_data.setdefault(key, value)
    if "created_time" not in field_data:
        created_value = meta_lead.meta_created_time or meta_lead.received_at
        if created_value:
            field_data["created_time"] = created_value.isoformat()
    row_data, custom_values, import_metadata, unmapped_fields = _apply_mapping_rules(
        field_data, mapping_rules, unknown_column_behavior
    )

    created_at_override: datetime | None = None
    if "created_at" in row_data:
        raw_created_at = row_data.pop("created_at")
        org_timezone = None
        org = db.get(Organization, meta_lead.organization_id)
        if org:
            org_timezone = org.timezone

        if isinstance(raw_created_at, datetime):
            created_at_override = (
                raw_created_at.astimezone(UTC)
                if raw_created_at.tzinfo
                else parse_datetime_with_timezone(
                    raw_created_at.isoformat(sep=" "), org_timezone
                ).value
            )
        else:
            parsed = parse_datetime_with_timezone(str(raw_created_at), org_timezone)
            created_at_override = parsed.value
            if parsed.value is None:
                import_metadata = import_metadata or {}
                import_metadata["created_time"] = str(raw_created_at)

    # Ensure required fields exist (fallback placeholders)
    full_name = str(row_data.get("full_name") or "").strip()
    email = str(row_data.get("email") or "").strip().lower()

    if not full_name or len(full_name) < 2:
        row_data["full_name"] = f"Meta Lead {meta_lead.meta_lead_id[:8]}"

    if not email or "@" not in email:
        row_data["email"] = f"meta-{meta_lead.meta_lead_id[:16]}@placeholder.invalid"
    else:
        row_data["email"] = email

    row_data.setdefault("source", SurrogateSource.META.value)
    identity = sa_inspect(meta_lead).identity
    persisted_lead_id = identity[0] if identity else None
    organization_id = meta_lead.organization_id
    external_meta_lead_id = meta_lead.meta_lead_id
    meta_form_id = meta_lead.meta_form_id

    try:
        surrogate_data, dropped_invalid_fields = _validate_surrogate_row_lenient(row_data)
        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=meta_lead.organization_id,
            user_id=user_id,
            data=surrogate_data,
            created_at_override=created_at_override,
        )

        if dropped_invalid_fields:
            import_metadata = import_metadata or {}
            import_metadata["dropped_invalid_fields"] = dropped_invalid_fields

        if tracking_fields:
            tracking_fields.update(import_metadata or {})
            import_metadata = tracking_fields
        if import_metadata:
            surrogate.import_metadata = import_metadata

        # Link surrogate back to meta lead and add campaign tracking
        surrogate.meta_lead_id = meta_lead.id
        surrogate.meta_form_id = meta_lead.meta_form_id
        _apply_meta_tracking(db, meta_lead, surrogate)

        # Save custom field values
        if custom_values:
            custom_field_service.set_bulk_custom_values(
                db,
                meta_lead.organization_id,
                surrogate.id,
                custom_values,
            )

        # Update meta lead
        meta_lead.is_converted = True
        meta_lead.converted_surrogate_id = surrogate.id
        meta_lead.converted_at = datetime.now(UTC)
        meta_lead.conversion_error = None
        meta_lead.unmapped_fields = unmapped_fields or None

        db.commit()
        db.refresh(surrogate)

        from app.services import surrogate_events

        surrogate_events.handle_surrogate_created(db=db, surrogate=surrogate)

        return surrogate, None

    except Exception as e:
        _mark_conversion_failed(
            db,
            e,
            persisted_lead_id=persisted_lead_id,
            organization_id=organization_id,
            external_meta_lead_id=external_meta_lead_id,
            unmapped_fields=unmapped_fields,
            emit_alert=True,
        )
        _ensure_review_task_for_mapping_conversion_failure(db, organization_id, meta_form_id, e)
        return None, f"Conversion failed: {_safe_conversion_error(e)}"


def convert_to_donor_with_mapping(
    db: Session,
    meta_lead: MetaLead,
    mapping_rules: list[dict],
    *,
    donor_type: str,
    unknown_column_behavior: str = "metadata",
    user_id: UUID | None = None,
) -> tuple[Donor | None, str | None]:
    """Convert one Meta lead into the configured donor subtype."""
    if donor_type not in {"egg", "sperm"}:
        return None, "Unsupported donor lead type"
    if meta_lead.is_converted:
        return None, "Meta lead already converted"
    if meta_lead.converted_donor_id:
        return None, "Meta lead already has a linked donor"

    field_data = dict(meta_lead.field_data_raw or meta_lead.field_data or {})
    row_data, _, _, unmapped_fields = _apply_mapping_rules(
        field_data,
        mapping_rules,
        unknown_column_behavior,
    )
    full_name = str(row_data.get("full_name") or "").strip()
    email = str(row_data.get("email") or "").strip().lower()
    if not full_name or len(full_name) < 2:
        full_name = f"Meta Lead {meta_lead.meta_lead_id[:8]}"
    if not email or "@" not in email:
        email = f"meta-{meta_lead.meta_lead_id[:16]}@placeholder.invalid"

    if donor_service.get_active_donor_by_email(db, meta_lead.organization_id, email):
        error = "An active donor with this email already exists"
        meta_lead.conversion_error = error
        meta_lead.unmapped_fields = unmapped_fields or None
        db.commit()
        return None, f"Conversion failed: {error}"

    identity = sa_inspect(meta_lead).identity
    persisted_lead_id = identity[0] if identity else None
    organization_id = meta_lead.organization_id
    external_meta_lead_id = meta_lead.meta_lead_id
    meta_form_id = meta_lead.meta_form_id

    try:
        donor = donor_service.create_donor(
            db=db,
            org_id=meta_lead.organization_id,
            user_id=user_id or SYSTEM_USER_ID,
            data=DonorCreate(
                donor_type=donor_type,
                full_name=full_name,
                email=email,
                phone=row_data.get("phone"),
                state=row_data.get("state"),
                education=row_data.get("education"),
                source="Meta",
            ),
            commit=False,
            emit_workflow_events=False,
        )
        meta_lead.is_converted = True
        meta_lead.converted_donor_id = donor.id
        meta_lead.converted_at = datetime.now(UTC)
        meta_lead.conversion_error = None
        meta_lead.unmapped_fields = unmapped_fields or None
        db.commit()
        db.refresh(donor)
    except Exception as exc:
        _mark_conversion_failed(
            db,
            exc,
            persisted_lead_id=persisted_lead_id,
            organization_id=organization_id,
            external_meta_lead_id=external_meta_lead_id,
            unmapped_fields=unmapped_fields,
            emit_alert=True,
        )
        _ensure_review_task_for_mapping_conversion_failure(db, organization_id, meta_form_id, exc)
        return None, f"Conversion failed: {_safe_conversion_error(exc)}"

    try:
        from app.services import workflow_triggers

        workflow_triggers.trigger_donor_created(db, donor)
    except Exception:
        db.rollback()
        logger.exception(
            "Donor-created workflow dispatch failed after Meta conversion for lead %s",
            external_meta_lead_id,
        )
    return donor, None


def convert_with_form_mapping(
    db: Session,
    meta_lead: MetaLead,
    form: MetaForm,
    *,
    user_id: UUID | None = None,
) -> tuple[Surrogate | Donor | None, str | None]:
    """Dispatch conversion only from the organization-scoped form configuration."""
    if form.organization_id != meta_lead.organization_id:
        return None, "Meta form organization does not match lead organization"
    lead_kind = meta_lead.lead_kind or form.lead_kind
    if lead_kind not in {"surrogate", "egg_donor", "sperm_donor"}:
        return None, "Unsupported Meta lead kind"
    if meta_lead.lead_kind is None:
        # Persist routing before conversion so a failed attempt cannot later be
        # redirected by a form reclassification.
        meta_lead.lead_kind = lead_kind
        db.commit()
    common = {
        "db": db,
        "meta_lead": meta_lead,
        "mapping_rules": form.mapping_rules or [],
        "unknown_column_behavior": form.unknown_column_behavior or "metadata",
        "user_id": user_id,
    }
    if lead_kind == "surrogate":
        return convert_to_surrogate_with_mapping(**common)
    if lead_kind == "egg_donor":
        return convert_to_donor_with_mapping(**common, donor_type="egg")
    if lead_kind == "sperm_donor":
        return convert_to_donor_with_mapping(**common, donor_type="sperm")
    return None, "Unsupported Meta lead kind"


def process_stored_meta_lead(
    db: Session,
    meta_lead: MetaLead,
) -> tuple[str, Surrogate | Donor | None]:
    """
    Process a stored Meta lead using the standard mapping pipeline.

    Returns a tuple of (status, surrogate or None).
    """
    from app.services import meta_form_mapping_service

    # Enrich platform attribution if missing (uses cached ad-level insights)
    try:
        enrich_platform_from_insights(db, meta_lead)
    except Exception as exc:
        logger.warning("Platform enrichment failed for lead %s: %s", meta_lead.meta_lead_id, exc)

    if meta_lead.is_converted:
        meta_lead.status = "converted"
        db.commit()
        if meta_lead.converted_donor_id:
            subject = donor_service.get_donor(
                db,
                meta_lead.organization_id,
                meta_lead.converted_donor_id,
            )
            return meta_lead.status, subject
        subject = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == meta_lead.organization_id,
                Surrogate.id == meta_lead.converted_surrogate_id,
            )
            .first()
            if meta_lead.converted_surrogate_id
            else None
        )
        return meta_lead.status, subject

    form = meta_form_mapping_service.get_form_by_external_id(
        db, meta_lead.organization_id, meta_lead.meta_form_id
    )
    if not form:
        meta_lead.status = "awaiting_mapping"
        db.commit()
        logger.info(
            "Meta lead %s awaiting mapping (form not found)",
            meta_lead.meta_lead_id,
        )
        return meta_lead.status, None

    configured_lead_kind = (
        form.lead_kind if form.mapping_status != "unmapped" else None
    )
    if meta_lead.lead_kind is None and configured_lead_kind:
        meta_lead.lead_kind = configured_lead_kind
        db.commit()

    if form.mapping_status != "mapped" or form.mapping_version_id != form.current_version_id:
        meta_lead.status = "awaiting_mapping"
        db.commit()
        reason = "Mapping missing" if form.mapping_status != "mapped" else "Mapping outdated"
        meta_form_mapping_service.ensure_mapping_review_task(db, form, reason=reason)
        logger.info(
            "Meta lead %s awaiting mapping for form %s",
            meta_lead.meta_lead_id,
            form.form_external_id,
        )
        return meta_lead.status, None

    meta_lead.status = "stored"
    db.commit()

    subject, convert_error = convert_with_form_mapping(db, meta_lead, form, user_id=None)

    if convert_error:
        logger.warning("Meta lead auto-conversion failed: %s", convert_error)
        meta_lead.status = "convert_failed"
        db.commit()
        return meta_lead.status, None

    meta_lead.status = "converted"
    db.commit()
    logger.info(
        "Meta lead %s converted to %s",
        meta_lead.meta_lead_id,
        getattr(subject, "donor_number", None)
        or getattr(subject, "surrogate_number", None),
    )
    return meta_lead.status, subject


def get_unconverted(db: Session, org_id: UUID) -> list[MetaLead]:
    """Get unconverted Meta leads for an org."""
    return (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            MetaLead.is_converted.is_(False),
        )
        .order_by(MetaLead.received_at.desc())
        .all()
    )


def get_meta_lead(db: Session, meta_lead_id: UUID, org_id: UUID) -> MetaLead | None:
    """Get Meta lead by ID (org-scoped)."""
    return (
        db.query(MetaLead)
        .filter(
            MetaLead.id == meta_lead_id,
            MetaLead.organization_id == org_id,
        )
        .first()
    )


def _apply_mapping_rules(
    field_data: dict,
    mapping_rules: list[dict],
    unknown_column_behavior: str,
) -> tuple[dict, dict, dict, dict]:
    """Apply mapping rules to raw field data."""
    row_data: dict = {}
    custom_values: dict = {}
    import_metadata: dict = {}
    unmapped_fields: dict = {}

    mapping_by_column = {_normalize_key(m.get("csv_column", "")): m for m in mapping_rules}

    for raw_key, raw_value in field_data.items():
        key = _normalize_key(str(raw_key))
        if raw_value is None or raw_value == "":
            continue

        mapping = mapping_by_column.get(key)
        value = _stringify_value(raw_value)
        metadata_value = _coerce_metadata_value(raw_value, value)

        if not mapping:
            if unknown_column_behavior == "metadata":
                import_metadata[raw_key] = metadata_value
            if unknown_column_behavior in ("warn", "metadata", "ignore"):
                unmapped_fields[raw_key] = metadata_value
            continue

        action = mapping.get("action")
        if action == "ignore":
            continue
        if action == "metadata":
            import_metadata[raw_key] = metadata_value
            continue
        if action == "custom" and mapping.get("custom_field_key"):
            custom_key = mapping.get("custom_field_key")
            transformed = _apply_transform(mapping, value)
            custom_values[custom_key] = transformed
            continue
        if action == "map" and mapping.get("surrogate_field"):
            field_name = mapping.get("surrogate_field")
            row_data[field_name] = _apply_transform(mapping, value)
            continue

    return row_data, custom_values, import_metadata, unmapped_fields


def _apply_transform(mapping: dict, value: str) -> object:
    transformation = mapping.get("transformation")
    if not transformation and mapping.get("action") == "map":
        field_name = mapping.get("surrogate_field")
        if field_name:
            transformation = get_suggested_transformer(field_name)
    if transformation:
        result = transform_value(transformation, value)
        if result.success:
            return result.value
    return value


def _validate_surrogate_row_lenient(row_data: dict) -> tuple[SurrogateCreate, list[str]]:
    return surrogate_input_normalization_service.build_surrogate_create_from_payload(
        row_data,
        lenient=True,
        required_fields=frozenset(REQUIRED_CONVERSION_FIELDS),
    )


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _stringify_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value)


def _coerce_metadata_value(raw_value: object, string_value: str) -> object:
    if isinstance(raw_value, bool):
        return raw_value
    return string_value


def _apply_meta_tracking(db: Session, meta_lead: MetaLead, surrogate: Surrogate) -> None:
    """Attach campaign hierarchy details to surrogate if available."""
    fields = meta_lead.field_data or {}
    raw_fields = meta_lead.field_data_raw or {}
    meta_ad_id = (
        raw_fields.get("meta_ad_id")
        or raw_fields.get("ad_id")
        or fields.get("meta_ad_id")
        or fields.get("ad_id")
    )
    if meta_ad_id:
        surrogate.meta_ad_external_id = str(meta_ad_id)
        meta_ad = (
            db.query(MetaAd)
            .filter(
                MetaAd.organization_id == meta_lead.organization_id,
                MetaAd.ad_external_id == str(meta_ad_id),
            )
            .first()
        )
        if meta_ad:
            surrogate.meta_campaign_external_id = meta_ad.campaign_external_id
            surrogate.meta_adset_external_id = meta_ad.adset_external_id


def _build_meta_tracking_fields(db: Session, meta_lead: MetaLead) -> dict[str, str]:
    fields = meta_lead.field_data_raw or meta_lead.field_data or {}
    tracking: dict[str, str] = {}

    ad_id = fields.get("meta_ad_id") or fields.get("ad_id")
    if ad_id:
        tracking["meta_ad_id"] = _stringify_value(ad_id)

    ad_name = fields.get("meta_ad_name") or fields.get("ad_name")
    if not ad_name and ad_id:
        meta_ad = (
            db.query(MetaAd)
            .filter(
                MetaAd.organization_id == meta_lead.organization_id,
                MetaAd.ad_external_id == str(ad_id),
            )
            .first()
        )
        if meta_ad:
            ad_name = meta_ad.ad_name
    if ad_name:
        tracking["meta_ad_name"] = _stringify_value(ad_name)

    if meta_lead.meta_form_id:
        form = (
            db.query(MetaForm)
            .filter(
                MetaForm.organization_id == meta_lead.organization_id,
                MetaForm.form_external_id == meta_lead.meta_form_id,
            )
            .first()
        )
        if form and form.form_name:
            tracking["meta_form_name"] = form.form_name

    platform = (
        fields.get("meta_platform") or fields.get("platform") or fields.get("publisher_platform")
    )
    if platform:
        tracking["meta_platform"] = _stringify_value(platform)

    return tracking


def _record_conversion_failure_alert(meta_lead: MetaLead, error: Exception) -> None:
    from app.services import alert_service

    form_key = meta_lead.meta_form_id or "unknown"
    alert_service.record_alert_isolated(
        org_id=meta_lead.organization_id,
        alert_type=AlertType.META_CONVERT_FAILED,
        severity=AlertSeverity.ERROR,
        title=f"Meta lead conversion failed for form {form_key}",
        message="A Meta lead failed conversion. Review the unconverted leads list for details.",
        integration_key=f"meta_form:{form_key}",
        error_class=type(error).__name__,
        details={
            "meta_lead_id": meta_lead.meta_lead_id,
            "meta_form_id": meta_lead.meta_form_id,
            "status": "convert_failed",
        },
    )


# =============================================================================
# Helper parsers
# =============================================================================


def _parse_date(value) -> date | None:
    """Parse date from various formats."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _parse_decimal(value) -> Decimal | None:
    """Parse height in feet from flexible formats."""
    if not value:
        return None
    transformed = transform_height_flexible(str(value))
    if transformed.success and transformed.value is not None:
        return transformed.value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _parse_int(value) -> int | None:
    """Parse int from string or number."""
    if not value:
        return None
    transformed = transform_int_flexible(str(value))
    if transformed.success:
        return transformed.value
    try:
        return int(value)
    except Exception:
        return None


def _parse_bool(value) -> bool | None:
    """Parse bool from various formats."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("yes", "true", "1", "y")
    return bool(value)


def _parse_bool_inverse(value) -> bool | None:
    """Parse bool and invert (for 'do you smoke' → is_non_smoker)."""
    result = _parse_bool(value)
    return not result if result is not None else None


def list_problem_leads(db: Session, org_id: UUID, limit: int = 50) -> list[MetaLead]:
    """List Meta leads with fetch/convert issues (org-scoped)."""
    from sqlalchemy import or_

    return (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            or_(
                MetaLead.status.in_(["fetch_failed", "convert_failed"]),
                MetaLead.fetch_error.isnot(None),
                MetaLead.conversion_error.isnot(None),
            ),
        )
        .order_by(MetaLead.received_at.desc())
        .limit(limit)
        .all()
    )


def count_meta_leads(db: Session, org_id: UUID) -> int:
    """Count total Meta leads (org-scoped)."""
    return db.scalar(select(func.count(MetaLead.id)).where(MetaLead.organization_id == org_id)) or 0


def count_failed_meta_leads(db: Session, org_id: UUID) -> int:
    """Count failed Meta leads (org-scoped)."""
    return (
        db.scalar(
            select(func.count(MetaLead.id)).where(
                MetaLead.organization_id == org_id,
                MetaLead.status.in_(["fetch_failed", "convert_failed"]),
            )
        )
        or 0
    )


def list_meta_leads(
    db: Session, org_id: UUID, limit: int = 100, status: str | None = None
) -> list[MetaLead]:
    """List all Meta leads for an org with optional status filter."""
    query = db.query(MetaLead).filter(MetaLead.organization_id == org_id)
    if status:
        query = query.filter(MetaLead.status == status)
    return query.order_by(MetaLead.received_at.desc()).limit(limit).all()
