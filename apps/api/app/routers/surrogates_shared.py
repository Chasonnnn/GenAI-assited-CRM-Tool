"""Shared helpers for surrogate routers."""

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import NO_VALUE

from app.db.enums import OwnerType, SurrogateSource
from app.schemas.surrogate import SurrogateListItem, SurrogateRead
from app.services import queue_service, user_service


def _surrogate_to_read(surrogate, db: Session) -> SurrogateRead:
    """Convert Surrogate model to SurrogateRead schema with joined user names."""
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
        status_label=surrogate.status_label,
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
        # IVF clinic
        clinic_name=surrogate.clinic_name,
        clinic_address_line1=surrogate.clinic_address_line1,
        clinic_address_line2=surrogate.clinic_address_line2,
        clinic_city=surrogate.clinic_city,
        clinic_state=surrogate.clinic_state,
        clinic_postal=surrogate.clinic_postal,
        clinic_phone=surrogate.clinic_phone,
        clinic_email=surrogate.clinic_email,
        # Monitoring clinic
        monitoring_clinic_name=surrogate.monitoring_clinic_name,
        monitoring_clinic_address_line1=surrogate.monitoring_clinic_address_line1,
        monitoring_clinic_address_line2=surrogate.monitoring_clinic_address_line2,
        monitoring_clinic_city=surrogate.monitoring_clinic_city,
        monitoring_clinic_state=surrogate.monitoring_clinic_state,
        monitoring_clinic_postal=surrogate.monitoring_clinic_postal,
        monitoring_clinic_phone=surrogate.monitoring_clinic_phone,
        monitoring_clinic_email=surrogate.monitoring_clinic_email,
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
        # Delivery hospital
        delivery_hospital_name=surrogate.delivery_hospital_name,
        delivery_hospital_address_line1=surrogate.delivery_hospital_address_line1,
        delivery_hospital_address_line2=surrogate.delivery_hospital_address_line2,
        delivery_hospital_city=surrogate.delivery_hospital_city,
        delivery_hospital_state=surrogate.delivery_hospital_state,
        delivery_hospital_postal=surrogate.delivery_hospital_postal,
        delivery_hospital_phone=surrogate.delivery_hospital_phone,
        delivery_hospital_email=surrogate.delivery_hospital_email,
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
        last_activity_at=last_activity_at or surrogate.updated_at,
        created_at=surrogate.created_at,
    )
