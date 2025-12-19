"""Case service - business logic for case operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.enums import CaseStatus, CaseSource
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

    if user_id:
        owner_type = OwnerType.USER.value
        owner_id = user_id
    else:
        default_queue = queue_service.get_or_create_default_queue(db, org_id)
        owner_type = OwnerType.QUEUE.value
        owner_id = default_queue.id
    
    case = Case(
        case_number=generate_case_number(db, org_id),
        organization_id=org_id,
        created_by_user_id=user_id,
        owner_type=owner_type,
        owner_id=owner_id,
        status=CaseStatus.NEW_UNREAD.value,
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
    db.commit()
    db.refresh(case)
    
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
    new_status: CaseStatus,
    user_id: UUID,
    user_role: "Role",  # Import at runtime to avoid circular
    reason: str | None = None,
) -> Case:
    """
    Change case status and record history.
    
    No-op if status unchanged.
    
    Transition guard: Intake specialists cannot set CASE_MANAGER_ONLY statuses.
    Returns:
        Case object or raises error if transition not allowed
    """
    from app.db.enums import Role
    from app.services import activity_service
    
    old_status = case.status
    
    # Capture requested status for CAPI (no auto-transition anymore)
    requested_status = new_status.value
    
    # NOTE: Auto-transition from approved → pending_handoff was REMOVED
    # Intake specialists should manually set 'pending_handoff' when ready to submit to case manager
    
    # Transition guard: Intake cannot set CASE_MANAGER_ONLY statuses
    if user_role == Role.INTAKE_SPECIALIST:
        if new_status.value in CaseStatus.case_manager_only():
            raise ValueError(f"Intake specialists cannot set status to {new_status.value}")
    
    # No-op if same status
    if old_status == new_status.value:
        return case
    
    case.status = new_status.value
    
    # Record history (legacy table)
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_status=old_status,
        to_status=new_status.value,
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
        from_status=old_status,
        to_status=new_status.value,
        actor_id=user_id,
        actor_name=actor_name,
    )
    
    # If transitioning to pending_handoff, notify all case_manager+
    if new_status == CaseStatus.PENDING_HANDOFF:
        notification_service.notify_case_handoff_ready(db=db, case=case)
    
    # Meta CAPI: Send lead quality signal for Meta-sourced cases
    # Uses requested_status (before auto-transition) so 'approved' triggers CAPI
    _maybe_send_capi_event(db, case, old_status, requested_status)
    
    # Trigger workflows for status change
    from app.services import workflow_triggers
    workflow_triggers.trigger_status_changed(db, case, old_status, new_status.value)
    
    return case


def _maybe_send_capi_event(db: Session, case: Case, old_status: str, new_status: str) -> None:
    """
    Send Meta Conversions API event if applicable.
    
    Triggers when:
    - Case source is META
    - Status changes to a qualified-like status
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
    
    if case.status != CaseStatus.PENDING_HANDOFF.value:
        return None, f"Case is not pending handoff (current: {case.status})"
    
    old_status = case.status
    case.status = CaseStatus.PENDING_MATCH.value
    
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_status=old_status,
        to_status=CaseStatus.PENDING_MATCH.value,
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
    
    if case.status != CaseStatus.PENDING_HANDOFF.value:
        return None, f"Case is not pending handoff (current: {case.status})"
    
    old_status = case.status
    case.status = CaseStatus.UNDER_REVIEW.value
    
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_status=old_status,
        to_status=CaseStatus.UNDER_REVIEW.value,
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
    
    return case


def archive_case(
    db: Session,
    case: Case,
    user_id: UUID,
) -> Case:
    """Soft-delete a case (set is_archived and status=ARCHIVED)."""
    from app.services import activity_service
    
    if case.is_archived:
        return case  # Already archived
    
    prior_status = case.status
    case.status = CaseStatus.ARCHIVED.value  # Actually set status to archived
    case.is_archived = True
    case.archived_at = datetime.now(timezone.utc)
    case.archived_by_user_id = user_id
    
    # Record in status history with prior status for restore reference
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_status=prior_status,
        to_status=CaseStatus.ARCHIVED.value,
        changed_by_user_id=user_id,
        reason=f"Case archived (was: {prior_status})",
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
    
    # Find the prior status from the archive history entry
    archive_history = db.query(CaseStatusHistory).filter(
        CaseStatusHistory.case_id == case.id,
        CaseStatusHistory.to_status == CaseStatus.ARCHIVED.value,
    ).order_by(CaseStatusHistory.changed_at.desc()).first()
    
    # Get prior status from archive history, default to NEW_UNREAD
    prior_status = CaseStatus.NEW_UNREAD.value  # Safe fallback
    if archive_history and archive_history.from_status:
        prior_status = archive_history.from_status
    
    case.status = prior_status  # Actually restore the status
    case.is_archived = False
    case.archived_at = None
    case.archived_by_user_id = None
    
    # Record in status history
    history = CaseStatusHistory(
        case_id=case.id,
        organization_id=case.organization_id,
        from_status=CaseStatus.ARCHIVED.value,
        to_status=prior_status,
        changed_by_user_id=user_id,
        reason=f"Case restored (back to: {prior_status})",
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
    status: CaseStatus | None = None,
    source: CaseSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = None,
    include_archived: bool = False,
    role_filter: str | None = None,
    user_id: UUID | None = None,
    owner_type: str | None = None,
    queue_id: UUID | None = None,
):
    """
    List cases with filters and pagination.
    
    Args:
        role_filter: User's role for visibility filtering
        user_id: User's ID for owner-based visibility
        owner_type: Filter by owner type ('user' or 'queue')
        queue_id: Filter by specific queue (when owner_type='queue')
    
    Returns:
        (cases, total_count)
    """
    from app.db.enums import Role, OwnerType
    
    query = db.query(Case).filter(Case.organization_id == org_id)
    
    # Archived filter (default: exclude)
    if not include_archived:
        query = query.filter(Case.is_archived == False)
    
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
    if status:
        query = query.filter(Case.status == status.value)
    
    # Source filter
    if source:
        query = query.filter(Case.source == source.value)
    
    # Assigned filter
    if owner_id:
        query = query.filter(
            Case.owner_type == OwnerType.USER.value,
            Case.owner_id == owner_id,
        )
    
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
    
    # Order by created_at desc
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
    query = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.status == CaseStatus.PENDING_HANDOFF.value,
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
        dict with total, by_status, this_week, this_month
    """
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Base query for non-archived cases
    base = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    )
    
    # Total count
    total = base.count()
    
    # Count by status
    status_counts = db.query(
        Case.status,
        func.count(Case.id).label('count')
    ).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    ).group_by(Case.status).all()
    
    by_status = {row.status: row.count for row in status_counts}
    
    # This week
    this_week = base.filter(Case.created_at >= week_ago).count()
    
    # This month
    this_month = base.filter(Case.created_at >= month_ago).count()
    
    return {
        "total": total,
        "by_status": by_status,
        "this_week": this_week,
        "this_month": this_month,
    }
