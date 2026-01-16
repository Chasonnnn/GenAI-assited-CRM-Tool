"""Surrogate service - business logic for surrogate operations."""

from datetime import datetime, timezone, time, timedelta
from typing import TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.encryption import hash_email, hash_phone
from app.db.enums import (
    SurrogateActivityType,
    SurrogateSource,
    SurrogateStatus,
    ContactStatus,
    OwnerType,
    Role,
)
from app.db.models import Surrogate, SurrogateStatusHistory, StatusChangeRequest, User, Organization
from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.utils.normalization import normalize_email, normalize_name, normalize_phone


# Grace period for undo (5 minutes)
UNDO_GRACE_PERIOD = timedelta(minutes=5)


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    surrogate: Surrogate | None
    request_id: UUID | None
    message: str | None


def _get_org_timezone(db: Session, org_id: UUID) -> str:
    """Get organization timezone string."""
    result = db.execute(
        select(Organization.timezone).where(Organization.id == org_id)
    ).scalar_one_or_none()
    return result or "America/Los_Angeles"


def _normalize_effective_at(
    effective_at: datetime | None,
    org_timezone_str: str,
) -> datetime:
    """
    Normalize effective_at to UTC datetime.

    Rules:
    - None: return now (UTC)
    - Today with time 00:00:00: return now (UTC) - effective now
    - Past date with time 00:00:00: default to 12:00 PM in org timezone
    - Otherwise: use as-is (assume UTC if no timezone)
    """
    now = datetime.now(timezone.utc)

    if effective_at is None:
        return now

    # If datetime is naive, assume it's in org timezone
    org_tz = ZoneInfo(org_timezone_str)
    if effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=org_tz)
    else:
        effective_at = effective_at.astimezone(org_tz)

    # Check if time component is midnight (00:00:00)
    # This indicates date-only was provided
    if effective_at.time() == time(0, 0, 0):
        today_org = now.astimezone(org_tz).date()
        effective_date = effective_at.date()

        if effective_date == today_org:
            # Today with no time = effective now
            return now
        elif effective_date < today_org:
            # Past date with no time = 12:00 PM org timezone
            noon = datetime.combine(effective_date, time(12, 0, 0)).replace(tzinfo=org_tz)
            return noon.astimezone(timezone.utc)
        else:
            # Future date - this will be rejected later
            return effective_at.astimezone(timezone.utc)

    # Has explicit time, use as-is
    return effective_at.astimezone(timezone.utc)


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


def create_surrogate(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    data: SurrogateCreate,
) -> Surrogate:
    """
    Create a new surrogatewith generated surrogatenumber.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID for created_by (None for auto-created surrogates like Meta leads)
        data: Surrogatecreation data

    Phone and state are validated in schema layer.
    """
    from app.services import activity_service
    from app.db.enums import OwnerType
    from app.services import queue_service
    from app.services import pipeline_service

    if user_id:
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
    surrogate = None
    for attempt in range(3):
        surrogate = Surrogate(
            surrogate_number=generate_surrogate_number(db, org_id),
            organization_id=org_id,
            created_by_user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            assigned_at=datetime.now(timezone.utc) if owner_type == OwnerType.USER.value else None,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=data.source.value,
            full_name=normalize_name(data.full_name),
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            phone=normalized_phone,  # Already normalized by schema
            phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
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
            is_priority=data.is_priority if hasattr(data, "is_priority") else False,
        )
        db.add(surrogate)
        try:
            db.commit()
            db.refresh(surrogate)
            break
        except IntegrityError as exc:
            db.rollback()
            try:
                db.expunge(surrogate)
            except Exception:
                pass
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
        elif field == "phone":
            if value:
                try:
                    value = normalize_phone(value)
                except ValueError:
                    pass
            phone_hash = hash_phone(value) if value else None

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
            elif field == "phone":
                surrogate.phone_hash = phone_hash

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
            pregnancy_fields = {"pregnancy_start_date", "pregnancy_due_date"}
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
    from app.db.enums import Role
    from app.services import pipeline_service

    now = datetime.now(timezone.utc)
    org_tz_str = _get_org_timezone(db, surrogate.organization_id)
    normalized_effective_at = _normalize_effective_at(effective_at, org_tz_str)

    old_stage_id = surrogate.stage_id
    old_label = surrogate.status_label
    old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
    old_slug = old_stage.slug if old_stage else None
    old_order = old_stage.order if old_stage else 0
    surrogate_pipeline_id = old_stage.pipeline_id if old_stage else None
    if not surrogate_pipeline_id:
        surrogate_pipeline_id = pipeline_service.get_or_create_default_pipeline(
            db,
            surrogate.organization_id,
        ).id

    new_stage = pipeline_service.get_stage_by_id(db, new_stage_id)
    if not new_stage or not new_stage.is_active:
        raise ValueError("Invalid or inactive stage")
    if new_stage.pipeline_id != surrogate_pipeline_id:
        raise ValueError("Stage does not belong to surrogate pipeline")

    # No-op guard: reject if target equals current
    if old_stage_id == new_stage.id:
        raise ValueError("Target stage is same as current stage")

    # Detect backdating and regression
    # Allow small time drift (1 second) to account for processing time
    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = new_stage.order < old_order

    # Validation: cannot set future date (allow 1 second tolerance)
    if (normalized_effective_at - now).total_seconds() > 1:
        raise ValueError("Cannot set future date for stage change")

    # Validation: cannot set date before surrogate creation
    if surrogate.created_at and normalized_effective_at < surrogate.created_at:
        raise ValueError("Cannot set date before surrogate was created")

    role_str = user_role.value if hasattr(user_role, "value") else user_role
    if not role_str:
        raise ValueError("User role is required to change stage")

    from app.core.stage_rules import ROLE_STAGE_MUTATION

    # Role-based stage permissions
    rules = ROLE_STAGE_MUTATION.get(role_str)
    if not rules:
        raise ValueError("Role not permitted to change stage")

    if role_str == Role.CASE_MANAGER.value:
        if surrogate.owner_type != OwnerType.USER.value or surrogate.owner_id != user_id:
            raise ValueError("Surrogate must be claimed before changing stage")

    allowed_types = set(rules["stage_types"])
    allowed_slugs = set(rules.get("extra_slugs", []))
    if not is_regression:
        if new_stage.stage_type not in allowed_types and new_stage.slug not in allowed_slugs:
            if role_str == Role.INTAKE_SPECIALIST.value:
                raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
            if role_str == Role.CASE_MANAGER.value:
                raise ValueError("Case managers can only set post-approval stages")
            raise ValueError("Role not permitted to change stage")
    elif role_str == Role.INTAKE_SPECIALIST.value:
        if new_stage.stage_type not in allowed_types and new_stage.slug not in allowed_slugs:
            raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
    elif role_str == Role.CASE_MANAGER.value:
        regression_allowed_types = allowed_types | {"intake"}
        if new_stage.stage_type not in regression_allowed_types and new_stage.slug not in allowed_slugs:
            raise ValueError("Case managers can only regress to intake or post-approval stages")

    # REGRESSION: Create request, don't apply yet (unless within undo grace period)
    if is_regression:
        # Check if this is an undo within grace period (must be most recent change)
        last_history = (
            db.query(SurrogateStatusHistory)
            .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
            .order_by(SurrogateStatusHistory.recorded_at.desc())
            .first()
        )

        within_grace_period = (
            last_history
            and last_history.changed_by_user_id == user_id
            and last_history.recorded_at
            and (now - last_history.recorded_at) <= UNDO_GRACE_PERIOD
            and last_history.from_stage_id == new_stage.id  # Undoing to previous stage
        )

        if within_grace_period:
            # Undo bypasses admin approval and reason requirement
            return _apply_status_change(
                db=db,
                surrogate=surrogate,
                new_stage=new_stage,
                old_stage_id=old_stage_id,
                old_label=old_label,
                old_slug=old_slug,
                user_id=user_id,
                reason=reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                is_undo=True,
            )

    # Backdating or regression requires reason (unless undo)
    if (is_backdated or is_regression) and not reason:
        raise ValueError("Reason required for backdated or regressed stage changes")

    if is_regression:
        # Create pending request for admin approval
        request = StatusChangeRequest(
            organization_id=surrogate.organization_id,
            entity_type="surrogate",
            entity_id=surrogate.id,
            target_stage_id=new_stage.id,
            effective_at=normalized_effective_at,
            reason=reason or "",
            requested_by_user_id=user_id,
            requested_at=now,
            status="pending",
        )
        db.add(request)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("A pending regression request already exists for this stage and date.")
        db.refresh(request)

        from app.services import notification_service

        requester = _get_org_user(db, surrogate.organization_id, user_id)
        notification_service.notify_status_change_request_pending(
            db=db,
            request=request,
            surrogate=surrogate,
            target_stage_label=new_stage.label,
            current_stage_label=old_label or "Unknown",
            requester_name=requester.display_name if requester else "Someone",
        )

        return StatusChangeResult(
            status="pending_approval",
            surrogate=surrogate,
            request_id=request.id,
            message="Regression requires admin approval. Request submitted.",
        )

    # NON-REGRESSION: Apply immediately
    return _apply_status_change(
        db=db,
        surrogate=surrogate,
        new_stage=new_stage,
        old_stage_id=old_stage_id,
        old_label=old_label,
        old_slug=old_slug,
        user_id=user_id,
        reason=reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        is_undo=False,
    )


def _apply_status_change(
    db: Session,
    surrogate: Surrogate,
    new_stage,
    old_stage_id: UUID | None,
    old_label: str | None,
    old_slug: str | None,
    user_id: UUID | None,
    reason: str | None,
    effective_at: datetime,
    recorded_at: datetime,
    is_undo: bool = False,
    request_id: UUID | None = None,
    approved_by_user_id: UUID | None = None,
    approved_at: datetime | None = None,
    requested_at: datetime | None = None,
) -> StatusChangeResult:
    """
    Apply a status change to a surrogate (internal helper).

    Called for non-regressions, undo within grace period, and approved regressions.
    """
    surrogate.stage_id = new_stage.id
    surrogate.status_label = new_stage.label

    # Update contact status if reached or leaving intake stage
    if surrogate.contact_status == ContactStatus.UNREACHED.value:
        if new_stage.slug == SurrogateStatus.CONTACTED.value or new_stage.is_intake_stage is False:
            surrogate.contact_status = ContactStatus.REACHED.value
            if not surrogate.contacted_at:
                surrogate.contacted_at = effective_at

    # Record history with dual timestamps
    history = SurrogateStatusHistory(
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        from_stage_id=old_stage_id,
        to_stage_id=new_stage.id,
        from_label_snapshot=old_label,
        to_label_snapshot=new_stage.label,
        changed_by_user_id=user_id,
        reason=reason,
        changed_at=effective_at,  # Derived from effective_at for backward compat
        effective_at=effective_at,
        recorded_at=recorded_at,
        is_undo=is_undo,
        request_id=request_id,
        requested_at=requested_at,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
    )
    db.add(history)
    db.commit()
    db.refresh(surrogate)

    # Send notifications
    from app.services import notification_service

    actor = _get_org_user(db, surrogate.organization_id, user_id)
    actor_name = actor.display_name if actor else "Someone"

    notification_service.notify_surrogate_status_changed(
        db=db,
        surrogate=surrogate,
        from_status=old_label,
        to_status=new_stage.label,
        actor_id=user_id or surrogate.created_by_user_id or surrogate.owner_id,
        actor_name=actor_name,
    )

    # If transitioning to approved, auto-assign to Surrogate Pool queue
    if new_stage.slug == "approved":
        from app.services import queue_service

        try:
            pool_queue = queue_service.get_or_create_surrogate_pool_queue(
                db, surrogate.organization_id
            )
            if pool_queue and (
                surrogate.owner_type != OwnerType.QUEUE.value or surrogate.owner_id != pool_queue.id
            ):
                surrogate = queue_service.assign_surrogate_to_queue(
                    db=db,
                    org_id=surrogate.organization_id,
                    surrogate_id=surrogate.id,
                    queue_id=pool_queue.id,
                    assigner_user_id=user_id,
                )
                db.commit()
                db.refresh(surrogate)
            if pool_queue:
                notification_service.notify_surrogate_ready_for_claim(db=db, surrogate=surrogate)
        except Exception:
            pass  # Best-effort: don't block status change

    # Meta CAPI: Send lead quality signal for Meta-sourced surrogates
    _maybe_send_capi_event(db, surrogate, old_slug or "", new_stage.slug)

    # Trigger workflows with effective_at in payload
    from app.services import workflow_triggers

    workflow_triggers.trigger_status_changed(
        db=db,
        surrogate=surrogate,
        old_stage_id=old_stage_id,
        new_stage_id=new_stage.id,
        old_stage_slug=old_slug,
        new_stage_slug=new_stage.slug,
        effective_at=effective_at,
        recorded_at=recorded_at,
        is_undo=is_undo,
        request_id=request_id,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
        requested_at=requested_at,
        changed_by_user_id=user_id,
    )

    return StatusChangeResult(
        status="applied",
        surrogate=surrogate,
        request_id=None,
        message=None,
    )


def _maybe_send_capi_event(
    db: Session, surrogate: Surrogate, old_status: str, new_status: str
) -> None:
    """
    Send Meta Conversions API event if applicable.

    Triggers when:
    - Surrogatesource is META
    - Status changes into a different Meta status bucket

    Note: Per-account CAPI enablement is checked in the worker handler,
    allowing us to skip surrogates without an ad account or where CAPI is disabled.
    """
    from app.db.enums import SurrogateSource, JobType
    from app.services import job_service

    # Only for Meta-sourced surrogates
    if surrogate.source != SurrogateSource.META.value:
        return

    # Check if this status change should trigger CAPI
    from app.services.meta_capi import should_send_capi_event

    if not should_send_capi_event(old_status, new_status):
        return

    # Need the original meta_lead_id
    if not surrogate.meta_lead_id:
        return

    # Get the meta lead to get the original Meta leadgen_id
    from app.db.models import MetaLead

    meta_lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.id == surrogate.meta_lead_id,
            MetaLead.organization_id == surrogate.organization_id,
        )
        .first()
    )
    if not meta_lead:
        return

    try:
        # Offload to worker for reliability (no event-loop assumptions, retries supported)
        idempotency_key = f"meta_capi:{meta_lead.meta_lead_id}:{new_status}"
        job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.META_CAPI_EVENT,
            payload={
                "meta_lead_id": meta_lead.meta_lead_id,
                "meta_ad_external_id": surrogate.meta_ad_external_id,  # For per-account CAPI
                "surrogate_status": new_status,
                "email": surrogate.email,
                "phone": surrogate.phone,
                "meta_page_id": meta_lead.meta_page_id,
            },
            idempotency_key=idempotency_key,
        )
    except Exception:
        # Best-effort: never block status change on CAPI scheduling.
        db.rollback()


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
            from app.services import notification_service

            actor = _get_org_user(db, surrogate.organization_id, user_id)
            actor_name = actor.display_name if actor else "Someone"
            notification_service.notify_surrogate_assigned(
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

    return surrogate


def restore_surrogate(
    db: Session,
    surrogate: Surrogate,
    user_id: UUID,
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

    Returns:
        (surrogates, total_count)
    """
    from app.db.enums import Role, OwnerType
    from app.db.models import PipelineStage
    from datetime import datetime
    from sqlalchemy import asc, desc

    query = (
        db.query(Surrogate)
        .options(
            selectinload(Surrogate.stage),
            selectinload(Surrogate.owner_user),
            selectinload(Surrogate.owner_queue),
        )
        .filter(Surrogate.organization_id == org_id)
    )

    # Archived filter (default: exclude)
    if not include_archived:
        query = query.filter(Surrogate.is_archived.is_(False))

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
        query = query.filter(
            or_(Surrogate.stage_id.is_(None), ~Surrogate.stage_id.in_(excluded_stage_ids))
        )

    # Owner-type filter
    if owner_type:
        query = query.filter(Surrogate.owner_type == owner_type)

    # Queue filter (for viewing specific queue's surrogates)
    if queue_id:
        query = query.filter(Surrogate.owner_id == queue_id)
        query = query.filter(Surrogate.owner_type == OwnerType.QUEUE.value)

    # Role-based visibility filter (ownership-based)
    if role_filter == Role.INTAKE_SPECIALIST.value or role_filter == Role.INTAKE_SPECIALIST:
        # Intake specialists only see their owned surrogates.
        if user_id:
            query = query.filter(
                (Surrogate.owner_type == OwnerType.USER.value) & (Surrogate.owner_id == user_id)
            )
        else:
            # No user_id → no owned surrogates
            query = query.filter(Surrogate.id.is_(None))

    # Status filter
    if stage_id:
        query = query.filter(Surrogate.stage_id == stage_id)

    # Source filter
    if source:
        query = query.filter(Surrogate.source == source.value)

    # Assigned filter
    if owner_id:
        query = query.filter(
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == owner_id,
        )

    # Date range filter
    if created_from:
        try:
            from_date = datetime.fromisoformat(created_from.replace("Z", "+00:00"))
            query = query.filter(Surrogate.created_at >= from_date)
        except (ValueError, AttributeError):
            pass  # Ignore invalid date format

    if created_to:
        try:
            to_date = datetime.fromisoformat(created_to.replace("Z", "+00:00"))
            query = query.filter(Surrogate.created_at <= to_date)
        except (ValueError, AttributeError):
            pass  # Ignore invalid date format

    # Search (name, email, phone)
    if q:
        search = f"%{q}%"
        filters = [
            Surrogate.full_name.ilike(search),
            Surrogate.surrogate_number.ilike(search),
        ]
        if "@" in q:
            try:
                filters.append(Surrogate.email_hash == hash_email(q))
            except Exception:
                pass
        try:
            normalized_phone = normalize_phone(q)
            filters.append(Surrogate.phone_hash == hash_phone(normalized_phone))
        except Exception:
            pass
        query = query.filter(or_(*filters))

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
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        # Default: created_at desc
        query = query.order_by(Surrogate.created_at.desc())

    # Count total
    total = query.count()

    # Paginate
    offset = (page - 1) * per_page
    surrogates = query.offset(offset).limit(per_page).all()

    return surrogates, total


def list_claim_queue(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Surrogate], int]:
    """List approved surrogates in the Surrogate Pool queue (org-scoped)."""
    from app.db.enums import OwnerType
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
            selectinload(Surrogate.stage),
            selectinload(Surrogate.owner_user),
            selectinload(Surrogate.owner_queue),
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


def hard_delete_surrogate(db: Session, surrogate: Surrogate) -> bool:
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
    return True


def get_surrogate_stats(db: Session, org_id: UUID) -> dict:
    """
    Get aggregated surrogatestatistics for dashboard.

    Returns:
        dict with total, by_status, this_week, this_month,
        last_week, last_month, and percentage changes
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)

    # Base query for non-archived surrogates
    base = db.query(Surrogate).filter(
        Surrogate.organization_id == org_id,
        Surrogate.is_archived.is_(False),
    )

    # Total count
    total = base.count()

    # Count by status
    status_counts = (
        db.query(Surrogate.status_label, func.count(Surrogate.id).label("count"))
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
        )
        .group_by(Surrogate.status_label)
        .all()
    )

    by_status = {row.status_label: row.count for row in status_counts}

    # This week vs last week
    this_week = base.filter(Surrogate.created_at >= week_ago).count()
    last_week = base.filter(
        Surrogate.created_at >= two_weeks_ago, Surrogate.created_at < week_ago
    ).count()

    # This month vs last month
    this_month = base.filter(Surrogate.created_at >= month_ago).count()
    last_month = base.filter(
        Surrogate.created_at >= two_months_ago, Surrogate.created_at < month_ago
    ).count()

    # Calculate percentage changes (handle division by zero)
    def calc_change_pct(current: int, previous: int) -> float | None:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    week_change_pct = calc_change_pct(this_week, last_week)
    month_change_pct = calc_change_pct(this_month, last_month)

    # Pending tasks count (for dashboard)
    from app.db.models import Task
    from app.db.enums import TaskType

    pending_tasks = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == org_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .scalar()
        or 0
    )

    return {
        "total": total,
        "by_status": by_status,
        "this_week": this_week,
        "last_week": last_week,
        "week_change_pct": week_change_pct,
        "this_month": this_month,
        "last_month": last_month,
        "month_change_pct": month_change_pct,
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

    base_query = (
        db.query(
            SurrogateActivityLog,
            User.display_name.label("actor_name"),
        )
        .outerjoin(User, SurrogateActivityLog.actor_user_id == User.id)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate_id,
            SurrogateActivityLog.organization_id == org_id,
        )
    )

    total = base_query.count()
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
