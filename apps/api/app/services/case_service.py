"""Case service - business logic for case operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.enums import CaseSource
from app.db.models import Case, CaseStatusHistory, User
from app.schemas.case import CaseCreate, CaseUpdate
from app.utils.normalization import normalize_email, normalize_name


def generate_case_number(db: Session, org_id: UUID) -> str:
    """
    Generate next sequential case number for org (00001-99999).
    
    Case numbers are unique per org and never reused (even for archived).
    """
    # Simple query to get max case number as string, then convert
    max_num = db.query(func.max(Case.case_number)).filter(
        Case.organization_id == org_id
    ).scalar()
    
    if max_num:
        result = int(max_num) + 1
    else:
        result = 1
    
    return f"{result:05d}"


def _is_case_number_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_case_number":
        return True
    message = str(error.orig) if error.orig else str(error)
    return "uq_case_number" in message



def create_case(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    data: CaseCreate,
) -> Case:
    """
    Create a new case with generated case number.
    
    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID for created_by (None for auto-created cases like Meta leads)
        data: Case creation data
    
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
    default_stage = pipeline_service.get_default_stage(db, pipeline.id)
    if not default_stage:
        raise ValueError("Default pipeline has no active stages")

    case = None
    for attempt in range(3):
        case = Case(
            case_number=generate_case_number(db, org_id),
            organization_id=org_id,
            created_by_user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=data.source.value,
            full_name=normalize_name(data.full_name),
            email=normalize_email(data.email),
            phone=data.phone,  # Already normalized by schema
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
            is_priority=data.is_priority if hasattr(data, 'is_priority') else False,
        )
        db.add(case)
        try:
            db.commit()
            db.refresh(case)
            break
        except IntegrityError as exc:
            db.rollback()
            try:
                db.expunge(case)
            except Exception:
                pass
            if _is_case_number_conflict(exc) and attempt < 2:
                continue
            raise
    
    # Log case creation (only if we have a user)
    if user_id:
        activity_service.log_case_created(
            db=db,
            case_id=case.id,
            organization_id=org_id,
            actor_user_id=user_id,
        )
        db.commit()
    
    # Trigger workflows for case creation
    from app.services import workflow_triggers
    workflow_triggers.trigger_case_created(db, case)
    
    return case


def update_case(
    db: Session,
    case: Case,
    data: CaseUpdate,
    user_id: UUID | None = None,
    org_id: UUID | None = None,
) -> Case:
    """
    Update case fields.
    
    Uses exclude_unset=True so only explicitly provided fields are updated.
    None values ARE applied to clear optional fields.
    Logs changes to activity log if user_id is provided.
    """
    from app.services import activity_service
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Fields that can be cleared (set to None)
    clearable_fields = {
        "phone", "state", "date_of_birth", "race", "height_ft", "weight_lb",
        "is_age_eligible", "is_citizen_or_pr", "has_child", "is_non_smoker",
        "has_surrogate_experience", "num_deliveries", "num_csections"
    }
    
    # Track changes for activity log (new values only)
    changes = {}
    priority_changed = False
    old_priority = case.is_priority
    
    for field, value in update_data.items():
        # For clearable fields, allow None; for others, skip None
        if value is None and field not in clearable_fields:
            continue
        if field == "full_name" and value:
            value = normalize_name(value)
        elif field == "email" and value:
            value = normalize_email(value)
        
        # Check if value actually changed
        current_value = getattr(case, field, None)
        if current_value != value:
            # Special handling for priority (separate log type)
            if field == "is_priority":
                priority_changed = True
            else:
                # Convert to string for JSON serialization
                if hasattr(value, 'isoformat'):  # datetime/date
                    changes[field] = value.isoformat()
                elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                    changes[field] = str(value)
                else:
                    changes[field] = value
            
            setattr(case, field, value)
    
    db.commit()
    db.refresh(case)
    
    # Log activity if changes were made and user_id provided
    if user_id and org_id:
        if changes:
            activity_service.log_info_edited(
                db=db,
                case_id=case.id,
                organization_id=org_id,
                actor_user_id=user_id,
                changes=changes,
            )
            db.commit()
        
        if priority_changed:
            activity_service.log_priority_changed(
                db=db,
                case_id=case.id,
                organization_id=org_id,
                actor_user_id=user_id,
                is_priority=case.is_priority,
            )
            db.commit()
    
    return case


def change_status(
    db: Session,
    case: Case,
    new_stage_id: UUID,
    user_id: UUID | None,
    user_role: "Role | None",  # Import at runtime to avoid circular
    reason: str | None = None,
) -> Case:
    """
    Change case stage and record history.
    
    No-op if stage unchanged.
    
    Transition guard: Intake specialists cannot set post_approval stages.
    Returns:
        Case object or raises error if transition not allowed
    """
    from app.db.enums import Role
    from app.services import pipeline_service
    
    old_stage_id = case.stage_id
    old_label = case.status_label
    old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
    old_slug = old_stage.slug if old_stage else None
    case_pipeline_id = old_stage.pipeline_id if old_stage else None
    if not case_pipeline_id:
        case_pipeline_id = pipeline_service.get_or_create_default_pipeline(
            db,
            case.organization_id,
        ).id
    
    new_stage = pipeline_service.get_stage_by_id(db, new_stage_id)
    if not new_stage or not new_stage.is_active:
        raise ValueError("Invalid or inactive stage")
    if new_stage.pipeline_id != case_pipeline_id:
        raise ValueError("Stage does not belong to case pipeline")
    
    # Transition guard: Intake cannot set CASE_MANAGER_ONLY statuses
    if user_role == Role.INTAKE_SPECIALIST and new_stage.stage_type == "post_approval":
        raise ValueError(f"Intake specialists cannot set stage to {new_stage.slug}")
    
    # No-op if same status
    if old_stage_id == new_stage.id:
        return case
    
    case.stage_id = new_stage.id
    case.status_label = new_stage.label
    
    # Record history
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_stage_id=old_stage_id,
        to_stage_id=new_stage.id,
        from_label_snapshot=old_label,
        to_label_snapshot=new_stage.label,
        changed_by_user_id=user_id,
        reason=reason,
    )
    db.add(history)
    db.commit()
    db.refresh(case)
    
    # NOTE: Status change is recorded in CaseStatusHistory (canonical source)
    # No duplicate log to CaseActivityLog needed
    
    # Send notifications
    from app.services import notification_service
    actor = db.query(User).filter(User.id == user_id).first()
    actor_name = actor.display_name if actor else "Someone"
    
    # Notify assignee and creator of status change
    notification_service.notify_case_status_changed(
        db=db,
        case=case,
        from_status=old_label,
        to_status=new_stage.label,
        actor_id=user_id or case.created_by_user_id or case.owner_id,
        actor_name=actor_name,
    )
    
    # If transitioning to pending_handoff, notify all case_manager+
    if new_stage.slug == "pending_handoff":
        notification_service.notify_case_handoff_ready(db=db, case=case)
    
    # Meta CAPI: Send lead quality signal for Meta-sourced cases
    # Uses requested_status (before auto-transition) so 'approved' triggers CAPI
    _maybe_send_capi_event(db, case, old_slug or "", new_stage.slug)
    
    # Trigger workflows for status change
    from app.services import workflow_triggers
    workflow_triggers.trigger_status_changed(db, case, old_stage_id, new_stage.id, old_slug, new_stage.slug)
    
    return case


def _maybe_send_capi_event(db: Session, case: Case, old_status: str, new_status: str) -> None:
    """
    Send Meta Conversions API event if applicable.
    
    Triggers when:
    - Case source is META
    - Status changes into a different Meta status bucket
    - CAPI is enabled
    """
    from app.core.config import settings
    from app.db.enums import CaseSource, JobType
    from app.services import job_service
    
    # Only for Meta-sourced cases
    if case.source != CaseSource.META.value:
        return
    
    # Only if CAPI is enabled
    if not settings.META_CAPI_ENABLED:
        return
    
    # Check if this status change should trigger CAPI
    from app.services.meta_capi import should_send_capi_event
    if not should_send_capi_event(old_status, new_status):
        return
    
    # Need the original meta_lead_id
    if not case.meta_lead_id:
        return
    
    # Get the meta lead to get the original Meta leadgen_id
    from app.db.models import MetaLead
    meta_lead = db.query(MetaLead).filter(MetaLead.id == case.meta_lead_id).first()
    if not meta_lead:
        return
    
    try:
        # Offload to worker for reliability (no event-loop assumptions, retries supported)
        idempotency_key = f"meta_capi:{meta_lead.meta_lead_id}:{new_status}"
        job_service.schedule_job(
            db=db,
            org_id=case.organization_id,
            job_type=JobType.META_CAPI_EVENT,
            payload={
                "meta_lead_id": meta_lead.meta_lead_id,
                "case_status": new_status,
                "email": case.email,
                "phone": case.phone,
                "meta_page_id": meta_lead.meta_page_id,
            },
            idempotency_key=idempotency_key,
        )
    except Exception:
        # Best-effort: never block status change on CAPI scheduling.
        db.rollback()


def accept_handoff(
    db: Session,
    case: Case,
    user_id: UUID,
) -> tuple[Case | None, str | None]:
    """
    Case manager accepts a pending_handoff case.
    
    - Must be in pending_handoff status (409 conflict if not)
    - Changes status to pending_match
    - Records history
    
    Returns:
        (case, error) - error is set if status mismatch
    """
    from app.services import activity_service
    
    from app.services import pipeline_service
    current_stage = pipeline_service.get_stage_by_id(db, case.stage_id)
    pipeline_id = current_stage.pipeline_id if current_stage else None
    if not pipeline_id:
        pipeline_id = pipeline_service.get_or_create_default_pipeline(db, case.organization_id).id
    handoff_stage = pipeline_service.get_stage_by_slug(db, pipeline_id, "pending_handoff")
    target_stage = pipeline_service.get_stage_by_slug(db, pipeline_id, "pending_match")
    if not handoff_stage or not target_stage:
        return None, "Required handoff stages are not configured"
    if case.stage_id != handoff_stage.id:
        return None, f"Case is not pending handoff (current: {case.status_label})"
    
    old_stage_id = case.stage_id
    old_label = case.status_label
    case.stage_id = target_stage.id
    case.status_label = target_stage.label
    
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_stage_id=old_stage_id,
        to_stage_id=target_stage.id,
        from_label_snapshot=old_label,
        to_label_snapshot=target_stage.label,
        changed_by_user_id=user_id,
        reason="Handoff accepted by case manager",
    )
    db.add(history)
    db.commit()
    db.refresh(case)
    
    # Log to activity log
    activity_service.log_handoff_accepted(
        db=db,
        case_id=case.id,
        organization_id=case.organization_id,
        actor_user_id=user_id,
    )
    db.commit()
    
    # Notify case creator that handoff was accepted
    from app.services import notification_service
    actor = db.query(User).filter(User.id == user_id).first()
    actor_name = actor.display_name if actor else "Case Manager"
    notification_service.notify_case_handoff_accepted(
        db=db,
        case=case,
        actor_name=actor_name,
    )
    
    return case, None


def deny_handoff(
    db: Session,
    case: Case,
    user_id: UUID,
    reason: str | None = None,
) -> tuple[Case | None, str | None]:
    """
    Case manager denies a pending_handoff case.
    
    - Must be in pending_handoff status (409 conflict if not)
    - Reverts status to under_review
    - Records reason in history
    
    Returns:
        (case, error) - error is set if status mismatch
    """
    from app.services import activity_service
    
    from app.services import pipeline_service
    current_stage = pipeline_service.get_stage_by_id(db, case.stage_id)
    pipeline_id = current_stage.pipeline_id if current_stage else None
    if not pipeline_id:
        pipeline_id = pipeline_service.get_or_create_default_pipeline(db, case.organization_id).id
    handoff_stage = pipeline_service.get_stage_by_slug(db, pipeline_id, "pending_handoff")
    target_stage = pipeline_service.get_stage_by_slug(db, pipeline_id, "under_review")
    if not handoff_stage or not target_stage:
        return None, "Required handoff stages are not configured"
    if case.stage_id != handoff_stage.id:
        return None, f"Case is not pending handoff (current: {case.status_label})"
    
    old_stage_id = case.stage_id
    old_label = case.status_label
    case.stage_id = target_stage.id
    case.status_label = target_stage.label
    
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_stage_id=old_stage_id,
        to_stage_id=target_stage.id,
        from_label_snapshot=old_label,
        to_label_snapshot=target_stage.label,
        changed_by_user_id=user_id,
        reason=reason or "Handoff denied by case manager",
    )
    db.add(history)
    db.commit()
    db.refresh(case)
    
    # Log to activity log
    activity_service.log_handoff_denied(
        db=db,
        case_id=case.id,
        organization_id=case.organization_id,
        actor_user_id=user_id,
        reason=reason,
    )
    db.commit()
    
    # Notify case creator that handoff was denied
    from app.services import notification_service
    actor = db.query(User).filter(User.id == user_id).first()
    actor_name = actor.display_name if actor else "Case Manager"
    notification_service.notify_case_handoff_denied(
        db=db,
        case=case,
        actor_name=actor_name,
        reason=reason,
    )
    
    return case, None


def assign_case(
    db: Session,
    case: Case,
    owner_type: "OwnerType",
    owner_id: UUID,
    user_id: UUID,
) -> Case:
    """Assign case to a user or queue."""
    from app.services import activity_service
    from app.db.enums import OwnerType
    from app.services import queue_service
    
    old_owner_type = case.owner_type
    old_owner_id = case.owner_id

    if owner_type == OwnerType.USER:
        case.owner_type = OwnerType.USER.value
        case.owner_id = owner_id
        assignee_id = owner_id
    elif owner_type == OwnerType.QUEUE:
        case = queue_service.assign_to_queue(
            db=db,
            org_id=case.organization_id,
            case_id=case.id,
            queue_id=owner_id,
            assigner_user_id=user_id,
        )
        assignee_id = None
    else:
        raise ValueError("Invalid owner_type")
    db.commit()
    db.refresh(case)
    
    # Log activity
    if case.owner_type == OwnerType.USER.value:
        activity_service.log_assigned(
            db=db,
            case_id=case.id,
            organization_id=case.organization_id,
            actor_user_id=user_id,
            to_user_id=case.owner_id,
            from_user_id=old_owner_id if old_owner_type == OwnerType.USER.value else None,
        )
        
        # Send notification to assignee (if not self-assign)
        if case.owner_id != user_id:
            from app.services import notification_service
            actor = db.query(User).filter(User.id == user_id).first()
            actor_name = actor.display_name if actor else "Someone"
            notification_service.notify_case_assigned(
                db=db,
                case=case,
                assignee_id=case.owner_id,
                actor_name=actor_name,
            )
    elif old_owner_type == OwnerType.USER.value and old_owner_id:
        activity_service.log_unassigned(
            db=db,
            case_id=case.id,
            organization_id=case.organization_id,
            actor_user_id=user_id,
            from_user_id=old_owner_id,
        )
    db.commit()
    
    # Trigger case_assigned workflow
    from app.services import workflow_triggers
    workflow_triggers.trigger_case_assigned(
        db=db,
        case=case,
        old_owner_id=old_owner_id,
        new_owner_id=case.owner_id,
        old_owner_type=old_owner_type,
        new_owner_type=case.owner_type,
    )
    
    return case


def archive_case(
    db: Session,
    case: Case,
    user_id: UUID,
) -> Case:
    """Soft-delete a case (set is_archived)."""
    from app.services import activity_service
    
    if case.is_archived:
        return case  # Already archived
    
    case.is_archived = True
    case.archived_at = datetime.now(timezone.utc)
    case.archived_by_user_id = user_id
    
    # Record in status history with prior status for restore reference
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_stage_id=case.stage_id,
        to_stage_id=case.stage_id,
        from_label_snapshot=case.status_label,
        to_label_snapshot=case.status_label,
        changed_by_user_id=user_id,
        reason="Case archived",
    )
    db.add(history)
    db.commit()
    db.refresh(case)
    
    # Log to activity log
    activity_service.log_archived(
        db=db,
        case_id=case.id,
        organization_id=case.organization_id,
        actor_user_id=user_id,
    )
    db.commit()
    
    return case


def restore_case(
    db: Session,
    case: Case,
    user_id: UUID,
) -> tuple[Case | None, str | None]:
    """
    Restore an archived case to its prior status.
    
    Returns:
        (case, error) - case is None if error occurred
    """
    from app.services import activity_service
    
    if not case.is_archived:
        return case, None  # Already active
    
    # Check if email is now taken by another active case
    existing = db.query(Case).filter(
        Case.organization_id == case.organization_id,
        Case.email == case.email,
        Case.is_archived == False,
        Case.id != case.id,
    ).first()
    
    if existing:
        return None, f"Email already in use by case #{existing.case_number}"
    
    case.is_archived = False
    case.archived_at = None
    case.archived_by_user_id = None
    
    # Record in status history
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_stage_id=case.stage_id,
        to_stage_id=case.stage_id,
        from_label_snapshot=case.status_label,
        to_label_snapshot=case.status_label,
        changed_by_user_id=user_id,
        reason="Case restored",
    )
    db.add(history)
    db.commit()
    db.refresh(case)
    
    # Log to activity log
    activity_service.log_restored(
        db=db,
        case_id=case.id,
        organization_id=case.organization_id,
        actor_user_id=user_id,
    )
    db.commit()
    
    return case, None


def get_case(db: Session, org_id: UUID, case_id: UUID) -> Case | None:
    """Get case by ID (org-scoped)."""
    return db.query(Case).filter(
        Case.id == case_id,
        Case.organization_id == org_id,
    ).first()


def get_case_by_number(db: Session, org_id: UUID, case_number: str) -> Case | None:
    """Get case by case number (org-scoped)."""
    return db.query(Case).filter(
        Case.case_number == case_number,
        Case.organization_id == org_id,
    ).first()


def list_cases(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
    stage_id: UUID | None = None,
    source: CaseSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = None,
    include_archived: bool = False,
    role_filter: str | None = None,
    user_id: UUID | None = None,
    owner_type: str | None = None,
    queue_id: UUID | None = None,
    created_from: str | None = None,  # ISO date string
    created_to: str | None = None,    # ISO date string
    exclude_stage_types: list[str] | None = None,  # Permission-based stage filter
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    """
    List cases with filters and pagination.
    
    Args:
        role_filter: User's role for visibility filtering
        user_id: User's ID for owner-based visibility
        owner_type: Filter by owner type ('user' or 'queue')
        queue_id: Filter by specific queue (when owner_type='queue')
        created_from: Filter by creation date from (ISO format YYYY-MM-DD)
        created_to: Filter by creation date to (ISO format YYYY-MM-DD)
        exclude_stage_types: Stage types to exclude (e.g. ['post_approval'] for users without permission)
        sort_by: Column to sort by (case_number, full_name, email, state, race, source, created_at)
        sort_order: Sort direction ('asc' or 'desc')
    
    Returns:
        (cases, total_count)
    """
    from app.db.enums import Role, OwnerType
    from app.db.models import PipelineStage
    from datetime import datetime
    from sqlalchemy import or_, asc, desc
    
    query = db.query(Case).options(selectinload(Case.stage)).filter(
        Case.organization_id == org_id
    )
    
    # Archived filter (default: exclude)
    if not include_archived:
        query = query.filter(Case.is_archived == False)
    
    # Permission-based stage type filter (exclude certain stage types)
    # NULL stage_id cases are kept visible (not excluded)
    if exclude_stage_types:
        excluded_stage_ids = db.query(PipelineStage.id).filter(
            PipelineStage.stage_type.in_(exclude_stage_types),
        ).scalar_subquery()
        query = query.filter(
            or_(
                Case.stage_id.is_(None),
                ~Case.stage_id.in_(excluded_stage_ids)
            )
        )
    
    # Owner-type filter
    if owner_type:
        query = query.filter(Case.owner_type == owner_type)
    
    # Queue filter (for viewing specific queue's cases)
    if queue_id:
        query = query.filter(Case.owner_id == queue_id)
        query = query.filter(Case.owner_type == OwnerType.QUEUE.value)
    
    # Role-based visibility filter (ownership-based)
    if role_filter == Role.INTAKE_SPECIALIST.value or role_filter == Role.INTAKE_SPECIALIST:
        # Intake specialists only see their owned cases.
        if user_id:
            query = query.filter(
                (Case.owner_type == OwnerType.USER.value) & (Case.owner_id == user_id)
            )
        else:
            # No user_id → no owned cases
            query = query.filter(Case.id.is_(None))
    
    # Status filter
    if stage_id:
        query = query.filter(Case.stage_id == stage_id)
    
    # Source filter
    if source:
        query = query.filter(Case.source == source.value)
    
    # Assigned filter
    if owner_id:
        query = query.filter(
            Case.owner_type == OwnerType.USER.value,
            Case.owner_id == owner_id,
        )
    
    # Date range filter
    if created_from:
        try:
            from_date = datetime.fromisoformat(created_from.replace('Z', '+00:00'))
            query = query.filter(Case.created_at >= from_date)
        except (ValueError, AttributeError):
            pass  # Ignore invalid date format
    
    if created_to:
        try:
            to_date = datetime.fromisoformat(created_to.replace('Z', '+00:00'))
            query = query.filter(Case.created_at <= to_date)
        except (ValueError, AttributeError):
            pass  # Ignore invalid date format
    
    # Search (name, email, phone)
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Case.full_name.ilike(search),
                Case.email.ilike(search),
                Case.phone.ilike(search),
                Case.case_number.ilike(search),
            )
        )
    
    # Dynamic sorting
    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "case_number": Case.case_number,
        "full_name": Case.full_name,
        "email": Case.email,
        "phone": Case.phone,
        "state": Case.state,
        "race": Case.race,
        "source": Case.source,
        "created_at": Case.created_at,
        "date_of_birth": Case.date_of_birth,  # For age sorting
    }
    
    if sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        # Default: created_at desc
        query = query.order_by(Case.created_at.desc())
    
    # Count total
    total = query.count()
    
    # Paginate
    offset = (page - 1) * per_page
    cases = query.offset(offset).limit(per_page).all()
    
    return cases, total


def list_handoff_queue(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
):
    """
    List cases in pending_handoff status (for case manager review).
    
    Returns:
        (cases, total_count)
    """
    from app.services import pipeline_service
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    handoff_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "pending_handoff")
    if not handoff_stage:
        return [], 0

    query = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.stage_id == handoff_stage.id,
        Case.is_archived == False,
    ).order_by(Case.created_at.desc())
    
    total = query.count()
    offset = (page - 1) * per_page
    cases = query.offset(offset).limit(per_page).all()
    
    return cases, total


def get_status_history(db: Session, case_id: UUID, org_id: UUID):
    """Get status history for a case (org-scoped)."""
    return db.query(CaseStatusHistory).filter(
        CaseStatusHistory.case_id == case_id,
        CaseStatusHistory.organization_id == org_id,
    ).order_by(CaseStatusHistory.changed_at.desc()).all()


def hard_delete_case(db: Session, case: Case) -> bool:
    """
    Permanently delete a case.
    
    Requires case to be archived first.
    
    Returns:
        True if deleted
    """
    if not case.is_archived:
        return False
    
    db.delete(case)
    db.commit()
    return True


def get_case_stats(db: Session, org_id: UUID) -> dict:
    """
    Get aggregated case statistics for dashboard.
    
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
    
    # Base query for non-archived cases
    base = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    )
    
    # Total count
    total = base.count()
    
    # Count by status
    status_counts = db.query(
        Case.status_label,
        func.count(Case.id).label('count')
    ).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    ).group_by(Case.status_label).all()
    
    by_status = {row.status_label: row.count for row in status_counts}
    
    # This week vs last week
    this_week = base.filter(Case.created_at >= week_ago).count()
    last_week = base.filter(
        Case.created_at >= two_weeks_ago,
        Case.created_at < week_ago
    ).count()
    
    # This month vs last month
    this_month = base.filter(Case.created_at >= month_ago).count()
    last_month = base.filter(
        Case.created_at >= two_months_ago,
        Case.created_at < month_ago
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
    pending_tasks = db.query(func.count(Task.id)).filter(
        Task.organization_id == org_id,
        Task.is_completed == False,
    ).scalar() or 0
    
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
