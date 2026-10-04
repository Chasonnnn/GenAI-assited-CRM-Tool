"""Shared helpers for surrogate routers."""

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import NO_VALUE

from app.db.enums import OwnerType, SurrogateSource
from app.schemas.surrogate import SurrogateListItem, SurrogateRead
from app.services import (
    queue_service,
    surrogate_outcome_summary_service,
    surrogate_service,
    surrogate_stage_context,
    user_service,
)
from app.services.surrogate_checklist_service import build_eligibility_checklist
from app.utils.height import height_ft_to_total_inches


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

    sensitive_info_available = surrogate_service.is_sensitive_info_available(db, surrogate)

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
        sensitive_info_available=sensitive_info_available,
        marital_status=surrogate.marital_status if sensitive_info_available else None,
        ssn_masked=(
            surrogate_service.build_masked_ssn(surrogate.ssn_last4)
            if sensitive_info_available
            else None
        ),
        address_line1=surrogate.address_line1 if sensitive_info_available else None,
        address_line2=surrogate.address_line2 if sensitive_info_available else None,
        address_city=surrogate.address_city if sensitive_info_available else None,
        address_state=surrogate.address_state if sensitive_info_available else None,
        address_postal=surrogate.address_postal if sensitive_info_available else None,
        partner_name=surrogate.partner_name if sensitive_info_available else None,
        partner_date_of_birth=(
            surrogate.partner_date_of_birth if sensitive_info_available else None
        ),
        partner_email=surrogate.partner_email if sensitive_info_available else None,
        partner_phone=surrogate.partner_phone if sensitive_info_available else None,
        partner_ssn_masked=(
            surrogate_service.build_masked_ssn(surrogate.partner_ssn_last4)
            if sensitive_info_available
            else None
        ),
        partner_address_line1=surrogate.partner_address_line1 if sensitive_info_available else None,
        partner_address_line2=surrogate.partner_address_line2 if sensitive_info_available else None,
        partner_city=surrogate.partner_city if sensitive_info_available else None,
        partner_state=surrogate.partner_state if sensitive_info_available else None,
        partner_postal=surrogate.partner_postal if sensitive_info_available else None,
        lead_intake_warnings=surrogate_service.build_lead_intake_warnings(db, surrogate),
        latest_contact_outcome=surrogate_outcome_summary_service.get_latest_contact_outcome(
            surrogate, db
        ),
        date_of_birth=surrogate.date_of_birth,
        race=surrogate.race,
        height_ft=surrogate.height_ft,
        weight_lb=surrogate.weight_lb,
        is_age_eligible=surrogate.is_age_eligible,
        is_citizen_or_pr=surrogate.is_citizen_or_pr,
        has_child=surrogate.has_child,
        is_non_smoker=surrogate.is_non_smoker,
        has_surrogate_experience=surrogate.has_surrogate_experience,
        journey_timing_preference=surrogate.journey_timing_preference,
        num_deliveries=surrogate.num_deliveries,
        num_csections=surrogate.num_csections,
        eligibility_checklist=build_eligibility_checklist(db, surrogate),
        # Pregnancy tracking
        embryo_stage=surrogate.embryo_stage,
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


def _surrogate_to_list_item(surrogate, last_activity_at=None) -> SurrogateListItem:
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
        height_inches = height_ft_to_total_inches(surrogate.height_ft) or 0
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
        paused_from_stage_id=surrogate.paused_from_stage_id,
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
