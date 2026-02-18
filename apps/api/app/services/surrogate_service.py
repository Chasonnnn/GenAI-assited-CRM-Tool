"""Surrogate service - business logic for surrogate operations."""

from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from app.core.encryption import hash_email, hash_phone
from app.db.enums import (
    ContactStatus,
    SurrogateActivityType,
    SurrogateSource,
    OwnerType,
    Role,
)
from app.db.models import Surrogate, SurrogateStatusHistory, User
from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.utils.normalization import (
    escape_like_string,
    extract_email_domain,
    extract_phone_last4,
    normalize_email,
    normalize_identifier,
    normalize_name,
    normalize_phone,
    normalize_search_text,
)
from app.services.surrogate_status_service import StatusChangeResult

logger = logging.getLogger(__name__)


def generate_surrogate_number(db: Session, org_id: UUID) -> str:
    """
    Generate next sequential surrogate number for org (S10001+).

    Uses atomic INSERT...ON CONFLICT for race-condition-free counter increment.
    Surrogate numbers are unique per org and never reused (even for archived).
    """
    from sqlalchemy import text

    # Atomic upsert: increment counter or initialize at 1 if not exists
    result = db.execute(
        text("""
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'surrogate_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
        """),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError("Failed to generate surrogate number")

    return f"S{result:05d}"


def _is_surrogate_number_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_surrogate_number":
        return True
    message = str(error.orig) if error.orig else str(error)
    return "uq_surrogate_number" in message


def _get_org_user(db: Session, org_id: UUID, user_id: UUID | None) -> User | None:
    if not user_id:
        return None
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    return membership.user if membership else None


def get_last_activity_map(
    db: Session, org_id: UUID, surrogate_ids: list[UUID]
) -> dict[UUID, datetime]:
    """Return last activity timestamps by surrogate id."""
    if not surrogate_ids:
        return {}

    from app.db.models import SurrogateActivityLog

    rows = (
        db.query(
            SurrogateActivityLog.surrogate_id,
            func.max(SurrogateActivityLog.created_at),
        )
        .filter(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.surrogate_id.in_(surrogate_ids),
        )
        .group_by(SurrogateActivityLog.surrogate_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def create_surrogate(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    data: SurrogateCreate,
    *,
    emit_events: bool = False,
    created_at_override: datetime | None = None,
) -> Surrogate:
    """
    Create a new surrogatewith generated surrogatenumber.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID for created_by (None for auto-created surrogates like Meta leads)
        data: Surrogatecreation data
        created_at_override: Optional created_at for backdated imports

    Phone and state are validated in schema layer.
    """
    from app.services import activity_service
    from app.db.enums import OwnerType
    from app.services import queue_service
    from app.services import pipeline_service

    assign_to_user = data.assign_to_user if data.assign_to_user is not None else user_id is not None
    if user_id and assign_to_user:
        owner_type = OwnerType.USER.value
        owner_id = user_id
    else:
        default_queue = queue_service.get_or_create_default_queue(db, org_id)
        owner_type = OwnerType.QUEUE.value
        owner_id = default_queue.id

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, user_id)
    default_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "new_unread")
    if not default_stage or not default_stage.is_active:
        default_stage = pipeline_service.get_default_stage(db, pipeline.id)
    if not default_stage:
        raise ValueError("Default pipeline has no active stages")

    normalized_email = normalize_email(data.email)
    normalized_phone = data.phone
    email_domain = extract_email_domain(normalized_email)
    phone_last4 = extract_phone_last4(normalized_phone)
    surrogate = None
    for attempt in range(3):
        surrogate_number = generate_surrogate_number(db, org_id)
        normalized_full_name = normalize_name(data.full_name)
        surrogate_kwargs = dict(
            surrogate_number=surrogate_number,
            surrogate_number_normalized=normalize_identifier(surrogate_number),
            organization_id=org_id,
            created_by_user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            assigned_at=datetime.now(timezone.utc) if owner_type == OwnerType.USER.value else None,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=data.source.value,
            full_name=normalized_full_name,
            full_name_normalized=normalize_search_text(normalized_full_name),
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            email_domain=email_domain,
            phone=normalized_phone,  # Already normalized by schema
            phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
            phone_last4=phone_last4,
            state=data.state,  # Already normalized by schema
            date_of_birth=data.date_of_birth,
            race=data.race,
            height_ft=data.height_ft,
            weight_lb=data.weight_lb,
            is_age_eligible=data.is_age_eligible,
            is_citizen_or_pr=data.is_citizen_or_pr,
            has_child=data.has_child,
            is_non_smoker=data.is_non_smoker,
            has_surrogate_experience=data.has_surrogate_experience,
            num_deliveries=data.num_deliveries,
            num_csections=data.num_csections,
            # Insurance info
            insurance_company=data.insurance_company,
            insurance_plan_name=data.insurance_plan_name,
            insurance_phone=data.insurance_phone,
            insurance_policy_number=data.insurance_policy_number,
            insurance_member_id=data.insurance_member_id,
            insurance_group_number=data.insurance_group_number,
            insurance_subscriber_name=data.insurance_subscriber_name,
            insurance_subscriber_dob=data.insurance_subscriber_dob,
            # IVF clinic
            clinic_name=data.clinic_name,
            clinic_address_line1=data.clinic_address_line1,
            clinic_address_line2=data.clinic_address_line2,
            clinic_city=data.clinic_city,
            clinic_state=data.clinic_state,
            clinic_postal=data.clinic_postal,
            clinic_phone=data.clinic_phone,
            clinic_email=data.clinic_email,
            # Monitoring clinic
            monitoring_clinic_name=data.monitoring_clinic_name,
            monitoring_clinic_address_line1=data.monitoring_clinic_address_line1,
            monitoring_clinic_address_line2=data.monitoring_clinic_address_line2,
            monitoring_clinic_city=data.monitoring_clinic_city,
            monitoring_clinic_state=data.monitoring_clinic_state,
            monitoring_clinic_postal=data.monitoring_clinic_postal,
            monitoring_clinic_phone=data.monitoring_clinic_phone,
            monitoring_clinic_email=data.monitoring_clinic_email,
            # OB provider
            ob_provider_name=data.ob_provider_name,
            ob_clinic_name=data.ob_clinic_name,
            ob_address_line1=data.ob_address_line1,
            ob_address_line2=data.ob_address_line2,
            ob_city=data.ob_city,
            ob_state=data.ob_state,
            ob_postal=data.ob_postal,
            ob_phone=data.ob_phone,
            ob_email=data.ob_email,
            # Delivery hospital
            delivery_hospital_name=data.delivery_hospital_name,
            delivery_hospital_address_line1=data.delivery_hospital_address_line1,
            delivery_hospital_address_line2=data.delivery_hospital_address_line2,
            delivery_hospital_city=data.delivery_hospital_city,
            delivery_hospital_state=data.delivery_hospital_state,
            delivery_hospital_postal=data.delivery_hospital_postal,
            delivery_hospital_phone=data.delivery_hospital_phone,
            delivery_hospital_email=data.delivery_hospital_email,
            # Pregnancy tracking
            pregnancy_start_date=data.pregnancy_start_date,
            pregnancy_due_date=data.pregnancy_due_date,
            actual_delivery_date=data.actual_delivery_date,
            delivery_baby_gender=data.delivery_baby_gender,
            delivery_baby_weight=data.delivery_baby_weight,
            is_priority=data.is_priority if hasattr(data, "is_priority") else False,
        )
        if created_at_override is not None:
            surrogate_kwargs["created_at"] = created_at_override
        surrogate = Surrogate(**surrogate_kwargs)
        db.add(surrogate)
        try:
            db.commit()
            db.refresh(surrogate)
            break
        except IntegrityError as exc:
            db.rollback()
            try:
                db.expunge(surrogate)
            except Exception as expunge_exc:
                logger.debug("surrogate_expunge_failed", exc_info=expunge_exc)
            if _is_surrogate_number_conflict(exc) and attempt < 2:
                continue
            raise

    # Log surrogatecreation (only if we have a user)
    if user_id:
        activity_service.log_surrogate_created(
            db=db,
            surrogate_id=surrogate.id,
            organization_id=org_id,
            actor_user_id=user_id,
        )
        db.commit()

    # Trigger workflows for surrogatecreation
    from app.services import workflow_triggers

    workflow_triggers.trigger_surrogate_created(db, surrogate)

    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, org_id)

    return surrogate


def update_surrogate(
    db: Session,
    surrogate: Surrogate,
    data: SurrogateUpdate,
    user_id: UUID | None = None,
    org_id: UUID | None = None,
    commit: bool = True,
) -> Surrogate:
    """
    Update surrogatefields.

    Uses exclude_unset=True so only explicitly provided fields are updated.
    None values ARE applied to clear optional fields.
    Logs changes to activity log if user_id is provided.
    """
    from app.services import activity_service

    update_data = data.model_dump(exclude_unset=True)

    # Fields that can be cleared (set to None)
    clearable_fields = {
        "phone",
        "state",
        "date_of_birth",
        "race",
        "height_ft",
        "weight_lb",
        "is_age_eligible",
        "is_citizen_or_pr",
        "has_child",
        "is_non_smoker",
        "has_surrogate_experience",
        "num_deliveries",
        "num_csections",
        # Insurance fields
        "insurance_company",
        "insurance_plan_name",
        "insurance_phone",
        "insurance_policy_number",
        "insurance_member_id",
        "insurance_group_number",
        "insurance_subscriber_name",
        "insurance_subscriber_dob",
        # Clinic fields
        "clinic_name",
        "clinic_address_line1",
        "clinic_address_line2",
        "clinic_city",
        "clinic_state",
        "clinic_postal",
        "clinic_phone",
        "clinic_email",
        # Monitoring clinic fields
        "monitoring_clinic_name",
        "monitoring_clinic_address_line1",
        "monitoring_clinic_address_line2",
        "monitoring_clinic_city",
        "monitoring_clinic_state",
        "monitoring_clinic_postal",
        "monitoring_clinic_phone",
        "monitoring_clinic_email",
        # OB provider fields
        "ob_provider_name",
        "ob_clinic_name",
        "ob_address_line1",
        "ob_address_line2",
        "ob_city",
        "ob_state",
        "ob_postal",
        "ob_phone",
        "ob_email",
        # Delivery hospital fields
        "delivery_hospital_name",
        "delivery_hospital_address_line1",
        "delivery_hospital_address_line2",
        "delivery_hospital_city",
        "delivery_hospital_state",
        "delivery_hospital_postal",
        "delivery_hospital_phone",
        "delivery_hospital_email",
        # Pregnancy fields
        "pregnancy_start_date",
        "pregnancy_due_date",
        "actual_delivery_date",
        "delivery_baby_gender",
        "delivery_baby_weight",
    }

    # Track changes for activity log (new values only)
    changes = {}
    priority_changed = False

    for field, value in update_data.items():
        # For clearable fields, allow None; for others, skip None
        if value is None and field not in clearable_fields:
            continue
        if field == "full_name" and value:
            value = normalize_name(value)
        elif field == "email":
            if not value:
                continue
            value = normalize_email(value)
            email_hash = hash_email(value)
            email_domain = extract_email_domain(value)
        elif field == "phone":
            if value:
                try:
                    value = normalize_phone(value)
                except ValueError:
                    pass
            phone_hash = hash_phone(value) if value else None
            phone_last4 = extract_phone_last4(value)

        # Check if value actually changed
        current_value = getattr(surrogate, field, None)
        if current_value != value:
            # Special handling for priority (separate log type)
            if field == "is_priority":
                priority_changed = True
            else:
                # Convert to string for JSON serialization
                if hasattr(value, "isoformat"):  # datetime/date
                    changes[field] = value.isoformat()
                elif hasattr(value, "__str__") and not isinstance(
                    value, (str, int, float, bool, type(None))
                ):
                    changes[field] = str(value)
                else:
                    changes[field] = value

            setattr(surrogate, field, value)
            if field == "email":
                surrogate.email_hash = email_hash
                surrogate.email_domain = email_domain
            elif field == "phone":
                surrogate.phone_hash = phone_hash
                surrogate.phone_last4 = phone_last4
            elif field == "full_name":
                surrogate.full_name_normalized = normalize_search_text(value)
            elif field == "surrogate_number":
                surrogate.surrogate_number_normalized = normalize_identifier(value)

    if commit:
        db.commit()
        db.refresh(surrogate)
    else:
        db.flush()
        db.refresh(surrogate)

    # Log activity if changes were made and user_id provided
    if user_id and org_id:
        if changes:
            activity_service.log_info_edited(
                db=db,
                surrogate_id=surrogate.id,
                organization_id=org_id,
                actor_user_id=user_id,
                changes=changes,
            )
            if commit:
                db.commit()
            else:
                db.flush()

        if priority_changed:
            activity_service.log_priority_changed(
                db=db,
                surrogate_id=surrogate.id,
                organization_id=org_id,
                actor_user_id=user_id,
                is_priority=surrogate.is_priority,
            )
            if commit:
                db.commit()
            else:
                db.flush()

        # Log field group changes (medical, insurance, pregnancy)
        if changes:
            changed_fields = set(changes.keys())

            # Medical fields: clinic, monitoring_clinic, ob, delivery_hospital
            medical_prefixes = ("clinic_", "monitoring_clinic_", "ob_", "delivery_hospital_")
            if any(f.startswith(medical_prefixes) for f in changed_fields):
                activity_service.log_medical_info_updated(
                    db=db,
                    surrogate_id=surrogate.id,
                    organization_id=org_id,
                    actor_user_id=user_id,
                )
                if commit:
                    db.commit()
                else:
                    db.flush()

            # Insurance fields
            if any(f.startswith("insurance_") for f in changed_fields):
                activity_service.log_insurance_info_updated(
                    db=db,
                    surrogate_id=surrogate.id,
                    organization_id=org_id,
                    actor_user_id=user_id,
                )
                if commit:
                    db.commit()
                else:
                    db.flush()

            # Pregnancy fields
            pregnancy_fields = {
                "pregnancy_start_date",
                "pregnancy_due_date",
                "actual_delivery_date",
                "delivery_baby_gender",
                "delivery_baby_weight",
            }
            if changed_fields & pregnancy_fields:
                activity_service.log_pregnancy_dates_updated(
                    db=db,
                    surrogate_id=surrogate.id,
                    organization_id=org_id,
                    actor_user_id=user_id,
                )
                if commit:
                    db.commit()
                else:
                    db.flush()

    return surrogate


def change_status(
    db: Session,
    surrogate: Surrogate,
    new_stage_id: UUID,
    user_id: UUID | None,
    user_role: Role | None,
    reason: str | None = None,
    effective_at: datetime | None = None,
    *,
    emit_events: bool = False,
) -> StatusChangeResult:
    """
    Change surrogate stage and record history with backdating support.

    Supports:
    - Normal changes (effective now)
    - Backdated changes (effective in the past, requires reason)
    - Regressions (earlier stage, requires admin approval)

    Args:
        effective_at: When the change actually occurred. None = now.
            - Today with no time: effective now
            - Past with no time: 12:00 PM org timezone

    Returns:
        StatusChangeResult with status='applied' or 'pending_approval'
    """
    from app.services import surrogate_status_service

    return surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=new_stage_id,
        user_id=user_id,
        user_role=user_role,
        reason=reason,
        effective_at=effective_at,
        emit_events=emit_events,
    )


def assign_surrogate(
    db: Session,
    surrogate: Surrogate,
    owner_type: OwnerType,
    owner_id: UUID,
    user_id: UUID,
) -> Surrogate:
    """Assign surrogateto a user or queue."""
    from app.services import activity_service
    from app.db.enums import OwnerType
    from app.services import queue_service

    old_owner_type = surrogate.owner_type
    old_owner_id = surrogate.owner_id

    if owner_type == OwnerType.USER:
        surrogate.owner_type = OwnerType.USER.value
        surrogate.owner_id = owner_id
        # Set assigned_at when assigning to a user
        surrogate.assigned_at = datetime.now(timezone.utc)
    elif owner_type == OwnerType.QUEUE:
        surrogate = queue_service.assign_surrogate_to_queue(
            db=db,
            org_id=surrogate.organization_id,
            surrogate_id=surrogate.id,
            queue_id=owner_id,
            assigner_user_id=user_id,
        )
        # Clear assigned_at when moving to queue
        surrogate.assigned_at = None
    else:
        raise ValueError("Invalid owner_type")
    db.commit()
    db.refresh(surrogate)

    # Log activity
    if surrogate.owner_type == OwnerType.USER.value:
        activity_service.log_assigned(
            db=db,
            surrogate_id=surrogate.id,
            organization_id=surrogate.organization_id,
            actor_user_id=user_id,
            to_user_id=surrogate.owner_id,
            from_user_id=old_owner_id if old_owner_type == OwnerType.USER.value else None,
        )

        # Send notification to assignee (if not self-assign)
        if surrogate.owner_id != user_id:
            from app.services import notification_facade

            actor = _get_org_user(db, surrogate.organization_id, user_id)
            actor_name = actor.display_name if actor else "Someone"
            notification_facade.notify_surrogate_assigned(
                db=db,
                surrogate=surrogate,
                assignee_id=surrogate.owner_id,
                actor_name=actor_name,
            )
    elif old_owner_type == OwnerType.USER.value and old_owner_id:
        activity_service.log_unassigned(
            db=db,
            surrogate_id=surrogate.id,
            organization_id=surrogate.organization_id,
            actor_user_id=user_id,
            from_user_id=old_owner_id,
        )

    # Invalidate pending workflow approvals if owner changed
    if old_owner_id and old_owner_id != surrogate.owner_id:
        from app.services import task_service

        invalidated_count = task_service.invalidate_pending_approvals_for_surrogate(
            db=db,
            surrogate_id=surrogate.id,
            reason="Surrogateowner changed",
            actor_user_id=user_id,
        )
        if invalidated_count > 0:
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                actor_user_id=user_id,
                activity_type=SurrogateActivityType.WORKFLOW_APPROVAL_INVALIDATED,
                details={
                    "reason": "owner_changed",
                    "old_owner_id": str(old_owner_id),
                    "new_owner_id": str(surrogate.owner_id) if surrogate.owner_id else None,
                    "invalidated_count": invalidated_count,
                },
            )

    db.commit()

    # Trigger surrogate_assigned workflow
    from app.services import workflow_triggers

    workflow_triggers.trigger_surrogate_assigned(
        db=db,
        surrogate=surrogate,
        old_owner_id=old_owner_id,
        new_owner_id=surrogate.owner_id,
        old_owner_type=old_owner_type,
        new_owner_type=surrogate.owner_type,
    )

    return surrogate


def archive_surrogate(
    db: Session,
    surrogate: Surrogate,
    user_id: UUID,
    *,
    emit_events: bool = False,
) -> Surrogate:
    """Soft-delete a surrogate(set is_archived)."""
    from app.services import activity_service

    if surrogate.is_archived:
        return surrogate  # Already archived

    surrogate.is_archived = True
    surrogate.archived_at = datetime.now(timezone.utc)
    surrogate.archived_by_user_id = user_id

    # Record in status history with prior status for restore reference
    history = SurrogateStatusHistory(
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        from_stage_id=surrogate.stage_id,
        to_stage_id=surrogate.stage_id,
        from_label_snapshot=surrogate.status_label,
        to_label_snapshot=surrogate.status_label,
        changed_by_user_id=user_id,
        reason="Surrogatearchived",
    )
    db.add(history)
    db.commit()
    db.refresh(surrogate)

    # Log to activity log
    activity_service.log_archived(
        db=db,
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        actor_user_id=user_id,
    )
    db.commit()

    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, surrogate.organization_id)

    return surrogate


def restore_surrogate(
    db: Session,
    surrogate: Surrogate,
    user_id: UUID,
    *,
    emit_events: bool = False,
) -> tuple[Surrogate | None, str | None]:
    """
    Restore an archived surrogateto its prior status.

    Returns:
        (case, error) - surrogateis None if error occurred
    """
    from app.services import activity_service

    if not surrogate.is_archived:
        return surrogate, None  # Already active

    # Check if email is now taken by another active surrogate
    existing = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == surrogate.organization_id,
            Surrogate.email_hash == surrogate.email_hash,
            Surrogate.is_archived.is_(False),
            Surrogate.id != surrogate.id,
        )
        .first()
    )

    if existing:
        return None, f"Email already in use by surrogate #{existing.surrogate_number}"

    surrogate.is_archived = False
    surrogate.archived_at = None
    surrogate.archived_by_user_id = None

    # Record in status history
    history = SurrogateStatusHistory(
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        from_stage_id=surrogate.stage_id,
        to_stage_id=surrogate.stage_id,
        from_label_snapshot=surrogate.status_label,
        to_label_snapshot=surrogate.status_label,
        changed_by_user_id=user_id,
        reason="Surrogaterestored",
    )
    db.add(history)
    db.commit()
    db.refresh(surrogate)

    # Log to activity log
    activity_service.log_restored(
        db=db,
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        actor_user_id=user_id,
    )
    db.commit()

    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, surrogate.organization_id)

    return surrogate, None


def get_surrogate(db: Session, org_id: UUID, surrogate_id: UUID) -> Surrogate | None:
    """Get surrogateby ID (org-scoped)."""
    return (
        db.query(Surrogate)
        .filter(
            Surrogate.id == surrogate_id,
            Surrogate.organization_id == org_id,
        )
        .first()
    )


def get_surrogates_by_ids(db: Session, org_id: UUID, surrogate_ids: list[UUID]) -> list[Surrogate]:
    """Get surrogates by IDs (org-scoped)."""
    if not surrogate_ids:
        return []
    return (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.id.in_(surrogate_ids),
        )
        .all()
    )


def get_surrogate_by_number(db: Session, org_id: UUID, surrogate_number: str) -> Surrogate | None:
    """Get surrogateby surrogatenumber (org-scoped)."""
    return (
        db.query(Surrogate)
        .filter(
            Surrogate.surrogate_number == surrogate_number,
            Surrogate.organization_id == org_id,
        )
        .first()
    )


def list_surrogates(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
    cursor: str | None = None,
    stage_id: UUID | None = None,
    source: SurrogateSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = None,
    include_archived: bool = False,
    role_filter: str | None = None,
    user_id: UUID | None = None,
    owner_type: str | None = None,
    queue_id: UUID | None = None,
    created_from: str | None = None,  # ISO date string
    created_to: str | None = None,  # ISO date string
    exclude_stage_types: list[str] | None = None,  # Permission-based stage filter
    sort_by: str | None = None,
    sort_order: str = "desc",
    include_total: bool = True,
):
    """
    List surrogates with filters and pagination.

    Args:
        role_filter: User's role for visibility filtering
        user_id: User's ID for owner-based visibility
        owner_type: Filter by owner type ('user' or 'queue')
        queue_id: Filter by specific queue (when owner_type='queue')
        created_from: Filter by creation date from (ISO format YYYY-MM-DD)
        created_to: Filter by creation date to (ISO format YYYY-MM-DD)
        exclude_stage_types: Stage types to exclude (e.g. ['post_approval'] for users without permission)
        sort_by: Column to sort by (surrogate_number, full_name, state, race, source, created_at)
        sort_order: Sort direction ('asc' or 'desc')
        include_total: Whether to include total count in response

    Returns:
        (surrogates, total_count or None, next_cursor)
    """
    import base64
    from app.db.enums import Role, OwnerType
    from app.db.models import PipelineStage, Queue
    from datetime import datetime
    from sqlalchemy import asc, desc

    def _encode_cursor(created_at: datetime, surrogate_id: UUID) -> str:
        raw = f"{created_at.isoformat()}|{surrogate_id}"
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    def _decode_cursor(raw: str) -> tuple[datetime, UUID]:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8")
            created_str, id_str = decoded.split("|", 1)
            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            return created_dt, UUID(id_str)
        except Exception as exc:
            raise ValueError("Invalid cursor") from exc

    filter_clauses = [Surrogate.organization_id == org_id]

    # Archived filter (default: exclude)
    if not include_archived:
        filter_clauses.append(Surrogate.is_archived.is_(False))

    # Permission-based stage type filter (exclude certain stage types)
    # NULL stage_id surrogates are kept visible (not excluded)
    if exclude_stage_types:
        excluded_stage_ids = (
            db.query(PipelineStage.id)
            .filter(
                PipelineStage.stage_type.in_(exclude_stage_types),
            )
            .scalar_subquery()
        )
        filter_clauses.append(
            or_(Surrogate.stage_id.is_(None), ~Surrogate.stage_id.in_(excluded_stage_ids))
        )

    # Owner-type filter
    if owner_type:
        filter_clauses.append(Surrogate.owner_type == owner_type)

    # Queue filter (for viewing specific queue's surrogates)
    if queue_id:
        filter_clauses.extend(
            [
                Surrogate.owner_id == queue_id,
                Surrogate.owner_type == OwnerType.QUEUE.value,
            ]
        )

    # Role-based visibility filter (ownership-based)
    if role_filter == Role.INTAKE_SPECIALIST.value or role_filter == Role.INTAKE_SPECIALIST:
        # Intake specialists only see their owned surrogates.
        if user_id:
            filter_clauses.append(
                (Surrogate.owner_type == OwnerType.USER.value) & (Surrogate.owner_id == user_id)
            )
        else:
            # No user_id → no owned surrogates
            filter_clauses.append(Surrogate.id.is_(None))

    # Status filter
    if stage_id:
        filter_clauses.append(Surrogate.stage_id == stage_id)

    # Source filter
    if source:
        filter_clauses.append(Surrogate.source == source.value)

    # Assigned filter
    if owner_id:
        filter_clauses.extend(
            [
                Surrogate.owner_type == OwnerType.USER.value,
                Surrogate.owner_id == owner_id,
            ]
        )

    # Date range filter
    if created_from:
        try:
            from_date = datetime.fromisoformat(created_from.replace("Z", "+00:00"))
            filter_clauses.append(Surrogate.created_at >= from_date)
        except (ValueError, AttributeError):
            logger.debug("surrogate_filter_invalid_created_at")

    if created_to:
        try:
            to_date = datetime.fromisoformat(created_to.replace("Z", "+00:00"))
            filter_clauses.append(Surrogate.created_at <= to_date)
        except (ValueError, AttributeError):
            pass  # Ignore invalid date format

    # Search (name, email, phone)
    if q:
        normalized_text = normalize_search_text(q)
        normalized_identifier = normalize_identifier(q)
        search_filters = []
        if normalized_text:
            escaped_text = escape_like_string(normalized_text)
            search_filters.append(
                Surrogate.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\")
            )
        if normalized_identifier:
            escaped_identifier = escape_like_string(normalized_identifier)
            search_filters.append(
                Surrogate.surrogate_number_normalized.ilike(f"%{escaped_identifier}%", escape="\\")
            )
        if "@" in q:
            try:
                search_filters.append(Surrogate.email_hash == hash_email(q))
            except Exception as exc:
                logger.debug("surrogate_search_email_hash_failed", exc_info=exc)
        try:
            normalized_phone = normalize_phone(q)
            search_filters.append(Surrogate.phone_hash == hash_phone(normalized_phone))
        except Exception as exc:
            logger.debug("surrogate_search_phone_hash_failed", exc_info=exc)
        if search_filters:
            filter_clauses.append(or_(*search_filters))

    base_query = db.query(Surrogate).filter(*filter_clauses)
    query = base_query.options(
        joinedload(Surrogate.stage).load_only(PipelineStage.slug, PipelineStage.stage_type),
        joinedload(Surrogate.owner_user).load_only(User.display_name),
        joinedload(Surrogate.owner_queue).load_only(Queue.name),
    )

    # Dynamic sorting
    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "surrogate_number": Surrogate.surrogate_number,
        "full_name": Surrogate.full_name,
        "state": Surrogate.state,
        "race": Surrogate.race,
        "source": Surrogate.source,
        "created_at": Surrogate.created_at,
    }

    if sort_by and sort_by in sortable_columns:
        if sort_by == "created_at":
            query = query.order_by(order_func(sortable_columns[sort_by]), order_func(Surrogate.id))
        else:
            query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        # Default: created_at desc
        query = query.order_by(Surrogate.created_at.desc(), Surrogate.id.desc())

    if cursor:
        if sort_by and sort_by != "created_at":
            raise ValueError("Cursor pagination only supports created_at sorting")
        if sort_order != "desc":
            raise ValueError("Cursor pagination only supports desc sorting")
        cursor_dt, cursor_id = _decode_cursor(cursor)
        query = query.filter(
            or_(
                Surrogate.created_at < cursor_dt,
                (Surrogate.created_at == cursor_dt) & (Surrogate.id < cursor_id),
            )
        )

    # Count total (optional)
    total = (
        base_query.with_entities(func.count(Surrogate.id)).order_by(None).scalar()
        if include_total
        else None
    )

    # Paginate
    next_cursor = None
    if cursor:
        surrogates = query.limit(per_page).all()
    else:
        offset = (page - 1) * per_page
        surrogates = query.offset(offset).limit(per_page).all()

    cursor_allowed = (sort_by in (None, "created_at")) and sort_order == "desc"
    if cursor_allowed and surrogates and len(surrogates) == per_page:
        last = surrogates[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return surrogates, total, next_cursor


def list_claim_queue(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Surrogate], int]:
    """List approved surrogates in the Surrogate Pool queue (org-scoped)."""
    from app.db.enums import OwnerType
    from app.db.models import PipelineStage, Queue
    from app.services import pipeline_service, queue_service

    pool_queue = queue_service.get_or_create_surrogate_pool_queue(db, org_id)
    if not pool_queue:
        return [], 0

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    approved_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "approved")
    if not approved_stage:
        return [], 0

    query = (
        db.query(Surrogate)
        .options(
            joinedload(Surrogate.stage).load_only(PipelineStage.slug, PipelineStage.stage_type),
            joinedload(Surrogate.owner_user).load_only(User.display_name),
            joinedload(Surrogate.owner_queue).load_only(Queue.name),
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.owner_type == OwnerType.QUEUE.value,
            Surrogate.owner_id == pool_queue.id,
            Surrogate.stage_id == approved_stage.id,
        )
        .order_by(Surrogate.updated_at.desc())
    )

    total = query.count()
    offset = (page - 1) * per_page
    surrogates = query.offset(offset).limit(per_page).all()

    return surrogates, total


def list_unassigned_queue(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Surrogate], int]:
    """List surrogates in the system default Unassigned queue (org-scoped)."""
    from app.db.enums import OwnerType
    from app.db.models import PipelineStage, Queue
    from app.services import queue_service

    default_queue = queue_service.get_or_create_default_queue(db, org_id)
    if not default_queue:
        return [], 0

    query = (
        db.query(Surrogate)
        .options(
            joinedload(Surrogate.stage).load_only(PipelineStage.slug, PipelineStage.stage_type),
            joinedload(Surrogate.owner_user).load_only(User.display_name),
            joinedload(Surrogate.owner_queue).load_only(Queue.name),
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.owner_type == OwnerType.QUEUE.value,
            Surrogate.owner_id == default_queue.id,
        )
        .order_by(Surrogate.updated_at.desc())
    )

    total = query.count()
    offset = (page - 1) * per_page
    surrogates = query.offset(offset).limit(per_page).all()

    return surrogates, total


def get_status_history(
    db: Session, surrogate_id: UUID, org_id: UUID
) -> list[SurrogateStatusHistory]:
    """Get status history for a surrogate(org-scoped)."""
    return (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.organization_id == org_id,
        )
        .order_by(SurrogateStatusHistory.changed_at.desc())
        .all()
    )


def hard_delete_surrogate(
    db: Session,
    surrogate: Surrogate,
    *,
    emit_events: bool = False,
) -> bool:
    """
    Permanently delete a case.

    Requires surrogateto be archived first.

    Returns:
        True if deleted
    """
    if not surrogate.is_archived:
        return False

    db.delete(surrogate)
    db.commit()
    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, surrogate.organization_id)
    return True


def get_surrogate_stats(
    db: Session,
    org_id: UUID,
    pipeline_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> dict:
    """
    Get aggregated surrogatestatistics for dashboard.

    Returns:
        dict with total, by_status, this_week, new_leads_24h,
        last_week, new_leads_prev_24h, and percentage changes
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    last_24h = now - timedelta(hours=24)
    prev_24h = now - timedelta(hours=48)

    from app.db.models import Task, PipelineStage
    from app.db.enums import TaskType

    surrogate_filters = [
        Surrogate.organization_id == org_id,
        Surrogate.is_archived.is_(False),
    ]
    if owner_id:
        surrogate_filters.extend(
            [
                Surrogate.owner_type == OwnerType.USER.value,
                Surrogate.owner_id == owner_id,
            ]
        )

    task_filters = [
        Task.organization_id == org_id,
        Task.is_completed.is_(False),
        Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
    ]
    if owner_id:
        task_filters.extend(
            [
                Task.owner_type == OwnerType.USER.value,
                Task.owner_id == owner_id,
            ]
        )

    pending_tasks_stmt = select(func.count(Task.id)).select_from(Task).where(*task_filters)
    if pipeline_id:
        # Prevent implicit correlation with the outer Surrogate query.
        surrogate_for_tasks = aliased(Surrogate)
        stage_for_tasks = aliased(PipelineStage)
        pending_tasks_stmt = (
            pending_tasks_stmt.join(
                surrogate_for_tasks, Task.surrogate_id == surrogate_for_tasks.id
            )
            .join(stage_for_tasks, surrogate_for_tasks.stage_id == stage_for_tasks.id)
            .where(
                surrogate_for_tasks.organization_id == org_id,
                surrogate_for_tasks.is_archived.is_(False),
                stage_for_tasks.pipeline_id == pipeline_id,
            )
        )
    pending_tasks_subq = pending_tasks_stmt.scalar_subquery()

    # Aggregate counts in a single query to reduce DB round trips.
    agg_query = db.query(
        func.count(Surrogate.id).label("total"),
        func.coalesce(
            func.sum(case((Surrogate.created_at >= week_ago, 1), else_=0)),
            0,
        ).label("this_week"),
        func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            Surrogate.created_at >= two_weeks_ago, Surrogate.created_at < week_ago
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("last_week"),
        func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            Surrogate.contact_status == ContactStatus.UNREACHED.value,
                            Surrogate.created_at >= last_24h,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("new_leads_24h"),
        func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            Surrogate.contact_status == ContactStatus.UNREACHED.value,
                            Surrogate.created_at >= prev_24h,
                            Surrogate.created_at < last_24h,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("new_leads_prev_24h"),
        pending_tasks_subq.label("pending_tasks"),
    ).filter(*surrogate_filters)
    if pipeline_id:
        agg_query = agg_query.join(PipelineStage, Surrogate.stage_id == PipelineStage.id).filter(
            PipelineStage.pipeline_id == pipeline_id
        )

    agg = agg_query.one()

    total = int(agg.total or 0)
    this_week = int(agg.this_week or 0)
    last_week = int(agg.last_week or 0)
    new_leads_24h = int(agg.new_leads_24h or 0)
    new_leads_prev_24h = int(agg.new_leads_prev_24h or 0)
    pending_tasks = int(agg.pending_tasks or 0)

    # Count by status (separate grouped query).
    status_query = db.query(
        Surrogate.status_label,
        func.count(Surrogate.id).label("count"),
    ).filter(*surrogate_filters)
    if pipeline_id:
        status_query = status_query.join(
            PipelineStage, Surrogate.stage_id == PipelineStage.id
        ).filter(PipelineStage.pipeline_id == pipeline_id)
    status_counts = status_query.group_by(Surrogate.status_label).all()
    by_status = {row.status_label: row.count for row in status_counts}

    # Calculate percentage changes (handle division by zero)
    def calc_change_pct(current: int, previous: int) -> float | None:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    week_change_pct = calc_change_pct(this_week, last_week)
    new_leads_change_pct = calc_change_pct(new_leads_24h, new_leads_prev_24h)

    return {
        "total": total,
        "by_status": by_status,
        "this_week": this_week,
        "last_week": last_week,
        "week_change_pct": week_change_pct,
        "new_leads_24h": new_leads_24h,
        "new_leads_prev_24h": new_leads_prev_24h,
        "new_leads_change_pct": new_leads_change_pct,
        "pending_tasks": pending_tasks,
    }


def list_assignees(db: Session, org_id: UUID) -> list[dict[str, str]]:
    """List assignable org members with display names."""
    from app.db.models import Membership, User

    rows = (
        db.query(Membership, User)
        .join(User, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .all()
    )

    return [
        {
            "id": str(user.id),
            "name": user.display_name,
            "role": membership.role,
        }
        for membership, user in rows
    ]


def list_surrogate_activity(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    page: int,
    per_page: int,
) -> tuple[list[dict], int]:
    """List activity log items for a case."""
    from app.db.models import SurrogateActivityLog, User

    filters = [
        SurrogateActivityLog.surrogate_id == surrogate_id,
        SurrogateActivityLog.organization_id == org_id,
    ]

    base_query = (
        db.query(
            SurrogateActivityLog,
            User.display_name.label("actor_name"),
        )
        .outerjoin(User, SurrogateActivityLog.actor_user_id == User.id)
        .filter(*filters)
    )

    total = db.query(func.count(SurrogateActivityLog.id)).filter(*filters).scalar() or 0
    offset = (page - 1) * per_page
    rows = (
        base_query.order_by(SurrogateActivityLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    items = []
    for row in rows:
        activity = row.SurrogateActivityLog
        items.append(
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "actor_user_id": activity.actor_user_id,
                "actor_name": row.actor_name,
                "details": activity.details,
                "created_at": activity.created_at,
            }
        )

    return items, total
