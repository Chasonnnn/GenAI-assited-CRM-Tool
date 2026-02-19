"""Meta Lead service - ingestion and conversion to surrogates."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import SurrogateSource
from app.db.models import MetaAd, MetaAdPlatformDaily, MetaForm, MetaLead, Organization, Surrogate
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service
from app.services import custom_field_service
from app.services.import_transformers import transform_height_flexible, transform_value
from app.utils.datetime_parsing import parse_datetime_with_timezone
from app.utils.normalization import normalize_phone, normalize_state

logger = logging.getLogger(__name__)


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
        db.commit()
        db.refresh(existing)
        return existing, None

    lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=meta_lead_id,
        meta_form_id=meta_form_id,
        meta_page_id=meta_page_id,
        field_data=field_data,
        field_data_raw=field_data_raw,
        raw_payload=raw_payload,
        meta_created_time=meta_created_time,
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
                datetime.combine(date_start, datetime.min.time(), tzinfo=timezone.utc),
                datetime.combine(date_end, datetime.max.time(), tzinfo=timezone.utc),
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


def convert_to_surrogate(
    db: Session,
    meta_lead: MetaLead,
    user_id: UUID | None = None,
) -> tuple[Surrogate | None, str | None]:
    """
    Convert a Meta lead to a normalized surrogate.

    Lenient conversion: handles missing/invalid data by using placeholders
    rather than rejecting the lead outright.

    Args:
        db: Database session
        meta_lead: The MetaLead to convert
        user_id: Optional user ID for created_by (None for auto-conversion)

    Returns:
        (surrogate, error) - surrogate is None if error
    """
    import re

    # Prevent double conversion
    if meta_lead.is_converted:
        return None, "Meta lead already converted"

    if meta_lead.converted_surrogate_id:
        return None, "Meta lead already has a linked surrogate"

    fields = meta_lead.field_data or {}
    tracking_fields = _build_meta_tracking_fields(db, meta_lead)

    # Map field names (adjust based on actual Meta form fields)
    full_name = fields.get("full_name") or fields.get("name") or ""
    email = fields.get("email", "")
    phone = fields.get("phone_number") or fields.get("phone")
    state = fields.get("state")

    # Sanitize name - remove non-printable and limit length
    full_name = re.sub(r"[^\w\s\-\.\,\']+", "", str(full_name)).strip()[:255]

    # If no name, use placeholder with lead ID
    if not full_name or len(full_name) < 2:
        full_name = f"Meta Lead {meta_lead.meta_lead_id[:8]}"

    # Sanitize email
    email = str(email).strip().lower()[:255]

    # Basic email validation - if invalid, generate placeholder
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        # Generate unique placeholder email
        email = f"meta-{meta_lead.meta_lead_id[:16]}@placeholder.invalid"

    # Normalize fields, handle validation errors gracefully
    try:
        normalized_phone = normalize_phone(phone) if phone else None
    except ValueError:
        normalized_phone = None  # Invalid phone format - continue without it

    try:
        normalized_state = normalize_state(state) if state else None
    except ValueError:
        normalized_state = None  # Log but don't fail

    # Create surrogate
    try:
        surrogate_data = SurrogateCreate(
            full_name=full_name,
            email=email,
            phone=normalized_phone,
            state=normalized_state,
            date_of_birth=_parse_date(fields.get("date_of_birth")),
            race=fields.get("race") or fields.get("please_specify_your_race"),
            height_ft=_parse_decimal(
                fields.get("height_ft") or fields.get("what_is_your_height_(ft)?")
            ),
            weight_lb=_parse_int(
                fields.get("weight_lb") or fields.get("what_is_your_weight_(lb)?")
            ),
            is_age_eligible=_parse_bool(
                fields.get("is_age_eligible")
                or fields.get("are_you_currently_between_the_ages_of_21_and_36?")
            ),
            is_citizen_or_pr=_parse_bool(
                fields.get("is_citizen_or_pr")
                or fields.get("are_you_a_citizen_or_permanent_resident_of_the_us?")
            ),
            has_child=_parse_bool(
                fields.get("has_child")
                or fields.get("have_you_given_birth_to_and_raised_at_least_one_child?")
            ),
            is_non_smoker=_parse_bool_inverse(
                fields.get(
                    "do_you_use_nicotine/tobacco_products_of_any_kind_(cigarettes,_cigars,_vape_devices,_hookahs,_marijuana,_etc.)?"
                )
            ),
            has_surrogate_experience=_parse_bool(
                fields.get("has_surrogate_experience")
                or fields.get("have_you_been_a_surrogate_before?")
            ),
            num_deliveries=_parse_int(
                fields.get("num_deliveries") or fields.get("how_many_deliveries_have_you_had?")
            ),
            num_csections=_parse_int(
                fields.get("num_csections") or fields.get("How many C-sections have you had？")
            ),
            source=SurrogateSource.META,
        )

        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=meta_lead.organization_id,
            user_id=user_id,
            data=surrogate_data,
        )

        if tracking_fields:
            surrogate.import_metadata = {**(surrogate.import_metadata or {}), **tracking_fields}

        # Link surrogate back to meta lead and add campaign tracking
        surrogate.meta_lead_id = meta_lead.id
        surrogate.meta_form_id = meta_lead.meta_form_id
        # Get ad_id from field_data if available (stored during fetch)
        surrogate.meta_ad_external_id = tracking_fields.get("meta_ad_id") or fields.get(
            "meta_ad_id"
        )

        # Update meta lead
        meta_lead.is_converted = True
        meta_lead.converted_surrogate_id = surrogate.id
        meta_lead.converted_at = datetime.now(timezone.utc)
        meta_lead.conversion_error = None

        db.commit()

        return surrogate, None

    except Exception as e:
        meta_lead.conversion_error = str(e)[:500]
        db.commit()
        return None, f"Conversion failed: {e}"


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
                raw_created_at.astimezone(timezone.utc)
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

    try:
        surrogate_data = SurrogateCreate(**row_data)
        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=meta_lead.organization_id,
            user_id=user_id,
            data=surrogate_data,
            created_at_override=created_at_override,
        )

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
        meta_lead.converted_at = datetime.now(timezone.utc)
        meta_lead.conversion_error = None
        meta_lead.unmapped_fields = unmapped_fields or None

        db.commit()

        if unmapped_fields and unknown_column_behavior != "ignore":
            _notify_unmapped_fields(db, meta_lead)

        return surrogate, None

    except Exception as e:
        meta_lead.conversion_error = str(e)[:500]
        meta_lead.unmapped_fields = unmapped_fields or None
        db.commit()
        return None, f"Conversion failed: {e}"


def process_stored_meta_lead(
    db: Session,
    meta_lead: MetaLead,
) -> tuple[str, Surrogate | None]:
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
        return meta_lead.status, db.get(Surrogate, meta_lead.converted_surrogate_id)

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

    surrogate, convert_error = convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=meta_lead,
        mapping_rules=form.mapping_rules or [],
        unknown_column_behavior=form.unknown_column_behavior or "metadata",
        user_id=None,
    )

    if convert_error:
        logger.warning("Meta lead auto-conversion failed: %s", convert_error)
        meta_lead.status = "convert_failed"
        db.commit()
        return meta_lead.status, None

    meta_lead.status = "converted"
    db.commit()
    logger.info(
        "Meta lead %s converted to surrogate %s",
        meta_lead.meta_lead_id,
        surrogate.surrogate_number if surrogate else None,
    )
    return meta_lead.status, surrogate


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
    if transformation:
        result = transform_value(transformation, value)
        if result.success:
            return result.value
    return value


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


def _notify_unmapped_fields(db: Session, meta_lead: MetaLead) -> None:
    """Create a review task when new unmapped fields appear."""
    if not meta_lead.meta_form_id:
        return
    try:
        from app.services import meta_form_mapping_service

        form = meta_form_mapping_service.get_form_by_external_id(
            db,
            meta_lead.organization_id,
            meta_lead.meta_form_id,
        )
        if not form:
            return

        meta_form_mapping_service.ensure_mapping_review_task(
            db,
            form,
            reason="Unmapped fields detected in recent Meta lead(s).",
        )
    except Exception as exc:
        logger.warning(f"Failed to create mapping review task: {exc}")


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
    return db.query(MetaLead).filter(MetaLead.organization_id == org_id).count()


def count_failed_meta_leads(db: Session, org_id: UUID) -> int:
    """Count failed Meta leads (org-scoped)."""
    return (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == org_id,
            MetaLead.status.in_(["fetch_failed", "convert_failed"]),
        )
        .count()
    )


def list_meta_leads(db: Session, org_id: UUID, limit: int = 100, status: str | None = None) -> list[MetaLead]:
    """List all Meta leads for an org with optional status filter."""
    query = db.query(MetaLead).filter(MetaLead.organization_id == org_id)
    if status:
        query = query.filter(MetaLead.status == status)
    return query.order_by(MetaLead.received_at.desc()).limit(limit).all()

