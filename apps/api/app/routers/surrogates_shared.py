"""Shared helpers for surrogate routers."""

from decimal import Decimal, InvalidOperation

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import NO_VALUE

from app.db.models import FormSubmission, MetaLead
from app.db.enums import OwnerType, SurrogateSource
from app.schemas.surrogate import SurrogateListItem, SurrogateRead
from app.services import queue_service, surrogate_stage_context, user_service
from app.utils.normalization import normalize_phone

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_LEAD_WARNING_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("email", ("email", "email_address", "emailaddress", "e_mail")),
    (
        "phone",
        ("phone", "phone_number", "phone_number_1", "mobile_phone", "cell_phone", "mobile"),
    ),
    ("height_ft", ("height_ft", "height", "height_feet", "height_inches")),
    ("weight_lb", ("weight_lb", "weight", "weight_lbs", "weight_pounds")),
)


def _normalize_json_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _coerce_raw_scalar(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int | float | Decimal):
        return str(value)
    if isinstance(value, list):
        parts = [part for item in value if (part := _coerce_raw_scalar(item))]
        return ", ".join(parts) or None
    return None


def _find_json_value_by_key(payload: object, candidate_keys: tuple[str, ...]) -> str | None:
    normalized_keys = {_normalize_json_key(key) for key in candidate_keys}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _normalize_json_key(str(key)) in normalized_keys:
                coerced = _coerce_raw_scalar(value)
                if coerced:
                    return coerced
        for value in payload.values():
            nested = _find_json_value_by_key(value, candidate_keys)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _find_json_value_by_key(item, candidate_keys)
            if nested:
                return nested
    return None


def _has_valid_email(value: str | None) -> bool:
    if not value or not value.strip():
        return False
    try:
        _EMAIL_ADAPTER.validate_python(value)
    except ValidationError:
        return False
    return True


def _has_valid_phone(value: str | None) -> bool:
    if not value or not value.strip():
        return False
    try:
        normalize_phone(value)
    except ValueError:
        return False
    return True


def _has_valid_decimal(value: object | None) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def _has_valid_int(value: object | None) -> bool:
    if value is None:
        return False
    try:
        return int(value) > 0
    except (ValueError, TypeError):
        return False


def _resolve_latest_lead_payload(db: Session, surrogate) -> dict:
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == surrogate.organization_id,
            FormSubmission.surrogate_id == surrogate.id,
        )
        .order_by(FormSubmission.submitted_at.desc(), FormSubmission.created_at.desc())
        .first()
    )
    if submission and isinstance(submission.answers_json, dict):
        return submission.answers_json

    if surrogate.meta_lead_id:
        meta_lead = (
            db.query(MetaLead)
            .filter(
                MetaLead.organization_id == surrogate.organization_id,
                MetaLead.id == surrogate.meta_lead_id,
            )
            .first()
        )
        if meta_lead:
            return (
                meta_lead.field_data_raw
                or meta_lead.field_data
                or meta_lead.raw_payload
                or {}
            )

    return {}


def _build_lead_intake_warnings(db: Session, surrogate) -> list[dict[str, str]]:
    raw_payload = _resolve_latest_lead_payload(db, surrogate)
    if not raw_payload:
        return []

    warnings: list[dict[str, str]] = []
    validators = {
        "email": (surrogate.email, _has_valid_email),
        "phone": (surrogate.phone, _has_valid_phone),
        "height_ft": (surrogate.height_ft, _has_valid_decimal),
        "weight_lb": (surrogate.weight_lb, _has_valid_int),
    }

    for field_key, candidate_keys in _LEAD_WARNING_KEYS:
        raw_value = _find_json_value_by_key(raw_payload, candidate_keys)
        if not raw_value:
            continue

        current_value, validator = validators[field_key]
        if validator(current_value):
            continue

        issue = "missing_value"
        if isinstance(current_value, str) and current_value.strip():
            issue = "invalid_value"

        warnings.append(
            {
                "field_key": field_key,
                "issue": issue,
                "raw_value": raw_value,
            }
        )

    return warnings


def _surrogate_to_read(surrogate, db: Session) -> SurrogateRead:
    """Convert Surrogate model to SurrogateRead schema with joined user names."""
    stage_context = surrogate_stage_context.get_stage_context(
        db,
        surrogate,
        current_stage=surrogate.stage,
    )
    paused_from_stage = stage_context.paused_from_stage

    owner_name = None
    if surrogate.owner_type == OwnerType.USER.value:
        # Prefer an already eager-loaded relationship (avoids redundant queries in list contexts).
        state = inspect(surrogate)
        if state.attrs.owner_user.loaded_value is not NO_VALUE and surrogate.owner_user:
            owner_name = surrogate.owner_user.display_name
        else:
            user = user_service.get_user_by_id(db, surrogate.owner_id)
            owner_name = user.display_name if user else None
    elif surrogate.owner_type == OwnerType.QUEUE.value:
        state = inspect(surrogate)
        if state.attrs.owner_queue.loaded_value is not NO_VALUE and surrogate.owner_queue:
            owner_name = surrogate.owner_queue.name
        else:
            queue = queue_service.get_queue(db, surrogate.organization_id, surrogate.owner_id)
            owner_name = queue.name if queue else None

    return SurrogateRead(
        id=surrogate.id,
        surrogate_number=surrogate.surrogate_number,
        stage_id=surrogate.stage_id,
        stage_key=stage_context.current_stage.stage_key if stage_context.current_stage else None,
        stage_slug=stage_context.current_stage.slug if stage_context.current_stage else None,
        stage_type=stage_context.current_stage.stage_type if stage_context.current_stage else None,
        status_label=surrogate.status_label,
        paused_from_stage_id=surrogate.paused_from_stage_id,
        paused_from_stage_key=paused_from_stage.stage_key if paused_from_stage else None,
        paused_from_stage_slug=paused_from_stage.slug if paused_from_stage else None,
        paused_from_stage_label=paused_from_stage.label if paused_from_stage else None,
        paused_from_stage_type=paused_from_stage.stage_type if paused_from_stage else None,
        source=SurrogateSource(surrogate.source),
        is_priority=surrogate.is_priority,
        owner_type=surrogate.owner_type,
        owner_id=surrogate.owner_id,
        owner_name=owner_name,
        created_by_user_id=surrogate.created_by_user_id,
        full_name=surrogate.full_name,
        email=surrogate.email,
        phone=surrogate.phone,
        state=surrogate.state,
        lead_intake_warnings=_build_lead_intake_warnings(db, surrogate),
        date_of_birth=surrogate.date_of_birth,
        race=surrogate.race,
        height_ft=surrogate.height_ft,
        weight_lb=surrogate.weight_lb,
        is_age_eligible=surrogate.is_age_eligible,
        is_citizen_or_pr=surrogate.is_citizen_or_pr,
        has_child=surrogate.has_child,
        is_non_smoker=surrogate.is_non_smoker,
        has_surrogate_experience=surrogate.has_surrogate_experience,
        num_deliveries=surrogate.num_deliveries,
        num_csections=surrogate.num_csections,
        # Insurance info
        insurance_company=surrogate.insurance_company,
        insurance_plan_name=surrogate.insurance_plan_name,
        insurance_phone=surrogate.insurance_phone,
        insurance_policy_number=surrogate.insurance_policy_number,
        insurance_member_id=surrogate.insurance_member_id,
        insurance_group_number=surrogate.insurance_group_number,
        insurance_subscriber_name=surrogate.insurance_subscriber_name,
        insurance_subscriber_dob=surrogate.insurance_subscriber_dob,
        insurance_fax=surrogate.insurance_fax,
        # IVF clinic
        clinic_name=surrogate.clinic_name,
        clinic_address_line1=surrogate.clinic_address_line1,
        clinic_address_line2=surrogate.clinic_address_line2,
        clinic_city=surrogate.clinic_city,
        clinic_state=surrogate.clinic_state,
        clinic_postal=surrogate.clinic_postal,
        clinic_phone=surrogate.clinic_phone,
        clinic_email=surrogate.clinic_email,
        clinic_fax=surrogate.clinic_fax,
        # Monitoring clinic
        monitoring_clinic_name=surrogate.monitoring_clinic_name,
        monitoring_clinic_address_line1=surrogate.monitoring_clinic_address_line1,
        monitoring_clinic_address_line2=surrogate.monitoring_clinic_address_line2,
        monitoring_clinic_city=surrogate.monitoring_clinic_city,
        monitoring_clinic_state=surrogate.monitoring_clinic_state,
        monitoring_clinic_postal=surrogate.monitoring_clinic_postal,
        monitoring_clinic_phone=surrogate.monitoring_clinic_phone,
        monitoring_clinic_email=surrogate.monitoring_clinic_email,
        monitoring_clinic_fax=surrogate.monitoring_clinic_fax,
        # OB provider
        ob_provider_name=surrogate.ob_provider_name,
        ob_clinic_name=surrogate.ob_clinic_name,
        ob_address_line1=surrogate.ob_address_line1,
        ob_address_line2=surrogate.ob_address_line2,
        ob_city=surrogate.ob_city,
        ob_state=surrogate.ob_state,
        ob_postal=surrogate.ob_postal,
        ob_phone=surrogate.ob_phone,
        ob_email=surrogate.ob_email,
        ob_fax=surrogate.ob_fax,
        # Delivery hospital
        delivery_hospital_name=surrogate.delivery_hospital_name,
        delivery_hospital_address_line1=surrogate.delivery_hospital_address_line1,
        delivery_hospital_address_line2=surrogate.delivery_hospital_address_line2,
        delivery_hospital_city=surrogate.delivery_hospital_city,
        delivery_hospital_state=surrogate.delivery_hospital_state,
        delivery_hospital_postal=surrogate.delivery_hospital_postal,
        delivery_hospital_phone=surrogate.delivery_hospital_phone,
        delivery_hospital_email=surrogate.delivery_hospital_email,
        delivery_hospital_fax=surrogate.delivery_hospital_fax,
        # PCP provider
        pcp_provider_name=surrogate.pcp_provider_name,
        pcp_name=surrogate.pcp_name,
        pcp_address_line1=surrogate.pcp_address_line1,
        pcp_address_line2=surrogate.pcp_address_line2,
        pcp_city=surrogate.pcp_city,
        pcp_state=surrogate.pcp_state,
        pcp_postal=surrogate.pcp_postal,
        pcp_phone=surrogate.pcp_phone,
        pcp_fax=surrogate.pcp_fax,
        pcp_email=surrogate.pcp_email,
        # Lab clinic
        lab_clinic_name=surrogate.lab_clinic_name,
        lab_clinic_address_line1=surrogate.lab_clinic_address_line1,
        lab_clinic_address_line2=surrogate.lab_clinic_address_line2,
        lab_clinic_city=surrogate.lab_clinic_city,
        lab_clinic_state=surrogate.lab_clinic_state,
        lab_clinic_postal=surrogate.lab_clinic_postal,
        lab_clinic_phone=surrogate.lab_clinic_phone,
        lab_clinic_fax=surrogate.lab_clinic_fax,
        lab_clinic_email=surrogate.lab_clinic_email,
        # Pregnancy tracking
        pregnancy_start_date=surrogate.pregnancy_start_date,
        pregnancy_due_date=surrogate.pregnancy_due_date,
        actual_delivery_date=surrogate.actual_delivery_date,
        delivery_baby_gender=surrogate.delivery_baby_gender,
        delivery_baby_weight=surrogate.delivery_baby_weight,
        is_archived=surrogate.is_archived,
        archived_at=surrogate.archived_at,
        created_at=surrogate.created_at,
        updated_at=surrogate.updated_at,
    )


def _surrogate_to_list_item(surrogate, db: Session, last_activity_at=None) -> SurrogateListItem:
    """Convert Surrogate model to SurrogateListItem schema."""
    from datetime import date

    owner_name = None
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_user:
        owner_name = surrogate.owner_user.display_name
    elif surrogate.owner_type == OwnerType.QUEUE.value and surrogate.owner_queue:
        owner_name = surrogate.owner_queue.name

    age = None
    if surrogate.date_of_birth:
        today = date.today()
        dob = surrogate.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    bmi = None
    if surrogate.height_ft and surrogate.weight_lb:
        height_inches = round(float(surrogate.height_ft) * 12)
        if height_inches > 0:
            bmi = round((surrogate.weight_lb / (height_inches**2)) * 703, 1)

    return SurrogateListItem(
        id=surrogate.id,
        surrogate_number=surrogate.surrogate_number,
        stage_id=surrogate.stage_id,
        stage_key=surrogate.stage.stage_key if surrogate.stage else None,
        stage_slug=surrogate.stage.slug if surrogate.stage else None,
        stage_type=surrogate.stage.stage_type if surrogate.stage else None,
        status_label=surrogate.status_label,
        source=SurrogateSource(surrogate.source),
        full_name=surrogate.full_name,
        email=surrogate.email,
        phone=surrogate.phone,
        state=surrogate.state,
        race=surrogate.race,
        owner_type=surrogate.owner_type,
        owner_id=surrogate.owner_id,
        owner_name=owner_name,
        is_priority=surrogate.is_priority,
        is_archived=surrogate.is_archived,
        age=age,
        bmi=bmi,
        last_activity_at=last_activity_at,
        created_at=surrogate.created_at,
        updated_at=surrogate.updated_at,
    )
