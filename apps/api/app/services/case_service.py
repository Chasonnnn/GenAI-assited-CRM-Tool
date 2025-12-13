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
    user_id: UUID,
    data: CaseCreate,
) -> Case:
    """
    Create a new case with generated case number.
    
    Phone and state are validated in schema layer.
    """
    case = Case(
        case_number=generate_case_number(db, org_id),
        organization_id=org_id,
        created_by_user_id=user_id,
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
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(
    db: Session,
    case: Case,
    data: CaseUpdate,
) -> Case:
    """
    Update case fields.
    
    Uses exclude_unset=True so only explicitly provided fields are updated.
    None values ARE applied to clear optional fields.
    """
    update_data = data.model_dump(exclude_unset=True)
    
    # Fields that can be cleared (set to None)
    clearable_fields = {
        "phone", "state", "date_of_birth", "race", "height_ft", "weight_lb",
        "is_age_eligible", "is_citizen_or_pr", "has_child", "is_non_smoker",
        "has_surrogate_experience", "num_deliveries", "num_csections"
    }
    
    for field, value in update_data.items():
        # For clearable fields, allow None; for others, skip None
        if value is None and field not in clearable_fields:
            continue
        if field == "full_name" and value:
            value = normalize_name(value)
        elif field == "email" and value:
            value = normalize_email(value)
        setattr(case, field, value)
    
    db.commit()
    db.refresh(case)
    return case


def change_status(
    db: Session,
    case: Case,
    new_status: CaseStatus,
    user_id: UUID,
    reason: str | None = None,
) -> Case:
    """
    Change case status and record history.
    
    No-op if status unchanged.
    """
    old_status = case.status
    
    # No-op if same status
    if old_status == new_status.value:
        return case
    
    case.status = new_status.value
    
    # Record history
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
    return case


def assign_case(
    db: Session,
    case: Case,
    assignee_id: UUID | None,
    user_id: UUID,
) -> Case:
    """Assign case to a user (or unassign with None)."""
    case.assigned_to_user_id = assignee_id
    db.commit()
    db.refresh(case)
    return case


def archive_case(
    db: Session,
    case: Case,
    user_id: UUID,
) -> Case:
    """Soft-delete a case (set is_archived). Stores prior status for restore."""
    if case.is_archived:
        return case  # Already archived
    
    prior_status = case.status
    case.is_archived = True
    case.archived_at = datetime.now(timezone.utc)
    case.archived_by_user_id = user_id
    
    # Record in status history with prior status in reason for restore reference
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
    
    # Extract prior status from reason or default to current status
    prior_status = case.status  # Fallback
    if archive_history and archive_history.from_status:
        prior_status = archive_history.from_status
    
    case.is_archived = False
    case.archived_at = None
    case.archived_by_user_id = None
    
    # Record in status history - restore to prior status
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
    assigned_to: UUID | None = None,
    q: str | None = None,
    include_archived: bool = False,
):
    """
    List cases with filters and pagination.
    
    Returns:
        (cases, total_count)
    """
    query = db.query(Case).filter(Case.organization_id == org_id)
    
    # Archived filter (default: exclude)
    if not include_archived:
        query = query.filter(Case.is_archived == False)
    
    # Status filter
    if status:
        query = query.filter(Case.status == status.value)
    
    # Source filter
    if source:
        query = query.filter(Case.source == source.value)
    
    # Assigned filter
    if assigned_to:
        query = query.filter(Case.assigned_to_user_id == assigned_to)
    
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
