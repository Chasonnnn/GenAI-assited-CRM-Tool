"""Meta Lead service - ingestion and conversion to cases."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import CaseSource
from app.db.models import Case, MetaLead
from app.schemas.case import CaseCreate
from app.services import case_service
from app.utils.normalization import normalize_phone, normalize_state


def store_meta_lead(
    db: Session,
    org_id: UUID,
    meta_lead_id: str,
    field_data: dict,
    raw_payload: dict | None = None,
    meta_form_id: str | None = None,
    meta_page_id: str | None = None,
    meta_created_time: datetime | None = None,
) -> tuple[MetaLead | None, str | None]:
    """
    Store a raw Meta lead.

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
        raw_payload=raw_payload,
        meta_created_time=meta_created_time,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead, None


def convert_to_case(
    db: Session,
    meta_lead: MetaLead,
    user_id: UUID | None = None,
) -> tuple[Case | None, str | None]:
    """
    Convert a Meta lead to a normalized case.

    Lenient conversion: handles missing/invalid data by using placeholders
    rather than rejecting the lead outright.

    Args:
        db: Database session
        meta_lead: The MetaLead to convert
        user_id: Optional user ID for created_by (None for auto-conversion)

    Returns:
        (case, error) - case is None if error
    """
    import re

    # Prevent double conversion
    if meta_lead.is_converted:
        return None, "Meta lead already converted"

    if meta_lead.converted_case_id:
        return None, "Meta lead already has a linked case"

    fields = meta_lead.field_data or {}

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

    # Create case
    try:
        case_data = CaseCreate(
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
                fields.get("num_deliveries")
                or fields.get("how_many_deliveries_have_you_had?")
            ),
            num_csections=_parse_int(
                fields.get("num_csections")
                or fields.get("How many C-sections have you had？")
            ),
            source=CaseSource.META,
        )

        case = case_service.create_case(
            db=db,
            org_id=meta_lead.organization_id,
            user_id=user_id,
            data=case_data,
        )

        # Link case back to meta lead and add campaign tracking
        case.meta_lead_id = meta_lead.id
        case.meta_form_id = meta_lead.meta_form_id
        # Get ad_id from field_data if available (stored during fetch)
        case.meta_ad_id = fields.get("meta_ad_id")

        # Update meta lead
        meta_lead.is_converted = True
        meta_lead.converted_case_id = case.id
        meta_lead.converted_at = datetime.now(timezone.utc)
        meta_lead.conversion_error = None

        db.commit()

        return case, None

    except Exception as e:
        meta_lead.conversion_error = str(e)[:500]
        db.commit()
        return None, f"Conversion failed: {e}"


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
    """Parse decimal from string or number."""
    if not value:
        return None
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


def list_problem_leads(db: Session, limit: int = 50) -> list[MetaLead]:
    """List Meta leads with fetch/convert issues."""
    from sqlalchemy import or_

    return (
        db.query(MetaLead)
        .filter(
            or_(
                MetaLead.status.in_(["fetch_failed", "convert_failed"]),
                MetaLead.fetch_error.isnot(None),
                MetaLead.conversion_error.isnot(None),
            )
        )
        .order_by(MetaLead.received_at.desc())
        .limit(limit)
        .all()
    )


def count_meta_leads(db: Session) -> int:
    """Count total Meta leads."""
    return db.query(MetaLead).count()


def count_failed_meta_leads(db: Session) -> int:
    """Count Meta leads with failed statuses."""
    return (
        db.query(MetaLead)
        .filter(MetaLead.status.in_(["fetch_failed", "convert_failed"]))
        .count()
    )


def list_meta_leads(
    db: Session,
    limit: int = 100,
    status: str | None = None,
) -> list[MetaLead]:
    """List Meta leads for debugging."""
    query = db.query(MetaLead).order_by(MetaLead.received_at.desc())

    if status:
        query = query.filter(MetaLead.status == status)

    return query.limit(limit).all()
