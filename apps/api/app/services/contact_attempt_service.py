"""Service layer for contact attempts tracking."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access
from app.db.enums import CaseActivityType, ContactStatus, OwnerType
from app.db.models import Case, CaseActivityLog, CaseContactAttempt, Organization, User
from app.schemas.auth import UserSession
from app.schemas.case import ContactAttemptCreate, ContactAttemptResponse, ContactAttemptsSummary
from app.services import case_service, pipeline_service


def create_contact_attempt(
    session: Session,
    case_id: UUID,
    data: ContactAttemptCreate,
    user: UserSession,
) -> ContactAttemptResponse:
    """
    Create a contact attempt for a case.

    Validates:
    - User has access to case
    - attempted_at is not in future
    - attempted_at is not before case.assigned_at

    Updates case.contact_status if outcome='reached'.
    """
    # Fetch case with organization for timezone
    case = (
        session.query(Case)
        .filter(
            Case.id == case_id,
            Case.organization_id == user.org_id,
        )
        .first()
    )

    if not case:
        raise ValueError("Case not found or access denied")

    check_case_access(case, user.role, user.user_id, db=session, org_id=user.org_id)

    if case.owner_type != OwnerType.USER.value:
        raise ValueError("Cannot log attempts for unassigned cases")

    if not case.assigned_at:
        raise ValueError("Cannot log attempts before assignment")

    # Default attempted_at to now if not provided
    attempted_at = data.attempted_at or datetime.now(timezone.utc)

    # Validate attempted_at
    if attempted_at > datetime.now(timezone.utc):
        raise ValueError("Cannot log future attempts")

    if case.assigned_at and attempted_at < case.assigned_at:
        raise ValueError(
            f"Cannot log attempt before assignment date ({case.assigned_at.isoformat()})"
        )

    # Create contact attempt
    attempt = CaseContactAttempt(
        case_id=case_id,
        organization_id=user.org_id,
        attempted_by_user_id=user.user_id,
        contact_methods=data.contact_methods,
        outcome=data.outcome,
        notes=data.notes,
        attempted_at=attempted_at,
        case_owner_id_at_attempt=case.owner_id,
    )
    session.add(attempt)
    session.flush()
    session.refresh(attempt)

    is_backdated = attempted_at < attempt.created_at

    # If reached, update case contact status
    if data.outcome == "reached":
        case.contact_status = ContactStatus.REACHED.value
        if not case.contacted_at:
            case.contacted_at = attempted_at
        case.last_contacted_at = attempted_at
        case.last_contact_method = data.contact_methods[0]

        current_stage = pipeline_service.get_stage_by_id(session, case.stage_id)
        if current_stage and current_stage.stage_type == "intake":
            if current_stage.slug != "contacted":
                contacted_stage = pipeline_service.get_stage_by_slug(
                    session, current_stage.pipeline_id, "contacted"
                )
                if contacted_stage:
                    case_service.change_status(
                        db=session,
                        case=case,
                        new_stage_id=contacted_stage.id,
                        user_id=user.user_id,
                        user_role=user.role,
                        reason="Contact reached",
                    )

    # Log in activity log
    activity = CaseActivityLog(
        case_id=case_id,
        organization_id=user.org_id,
        activity_type=CaseActivityType.CONTACT_ATTEMPT.value,
        actor_user_id=user.user_id,
        details={
            "contact_methods": data.contact_methods,
            "outcome": data.outcome,
            "notes": data.notes,
            "is_backdated": is_backdated,
            "attempted_at": attempted_at.isoformat(),
        },
    )
    session.add(activity)

    # Resolve user name
    user_name = (
        session.query(User.display_name).filter(User.id == user.user_id).scalar()
    )

    return ContactAttemptResponse(
        id=attempt.id,
        case_id=attempt.case_id,
        attempted_by_user_id=attempt.attempted_by_user_id,
        attempted_by_name=user_name,
        contact_methods=attempt.contact_methods,
        outcome=attempt.outcome,
        notes=attempt.notes,
        attempted_at=attempt.attempted_at,
        created_at=attempt.created_at,
        is_backdated=attempt.is_backdated,
        case_owner_id_at_attempt=attempt.case_owner_id_at_attempt,
    )


def get_case_contact_attempts_summary(
    session: Session,
    case_id: UUID,
    user: UserSession,
) -> ContactAttemptsSummary:
    """
    Get summary of contact attempts for a case.

    Includes:
    - Total attempts (all history)
    - Current assignment attempts
    - Distinct days in org timezone
    - Successful attempts
    """
    # Fetch case and org timezone
    case_stmt = (
        select(Case, Organization.timezone)
        .join(Organization, Case.organization_id == Organization.id)
        .where(Case.id == case_id, Case.organization_id == user.org_id)
    )
    case_result = session.execute(case_stmt)
    case_row = case_result.one_or_none()

    if not case_row:
        raise ValueError("Case not found or access denied")

    case, org_tz = case_row

    # Fetch all attempts
    attempts_stmt = (
        select(CaseContactAttempt)
        .where(CaseContactAttempt.case_id == case_id)
        .order_by(CaseContactAttempt.attempted_at.desc())
    )
    attempts_result = session.execute(attempts_stmt)
    attempts = attempts_result.scalars().all()

    # Calculate stats
    total_attempts = len(attempts)
    current_assignment_attempts = sum(
        1 for a in attempts if a.case_owner_id_at_attempt == case.owner_id
    )
    successful_attempts = sum(1 for a in attempts if a.outcome == "reached")

    # Calculate distinct days for current assignment (in org timezone)
    if current_assignment_attempts > 0:
        distinct_days_stmt = select(
            func.count(
                func.distinct(
                    func.date(
                        func.timezone(
                            org_tz, CaseContactAttempt.attempted_at
                        )
                    )
                )
            )
        ).where(
            CaseContactAttempt.case_id == case_id,
            CaseContactAttempt.case_owner_id_at_attempt == case.owner_id,
        )
        distinct_days_result = session.execute(distinct_days_stmt)
        distinct_days = distinct_days_result.scalar() or 0
    else:
        distinct_days = 0

    # Get last attempt time
    last_attempt_at = attempts[0].attempted_at if attempts else None

    # Calculate days since last attempt
    if last_attempt_at:
        delta = datetime.now(timezone.utc) - last_attempt_at
        days_since = delta.days
    else:
        days_since = None

    # Resolve user names
    user_ids = {a.attempted_by_user_id for a in attempts if a.attempted_by_user_id}
    if user_ids:
        users_stmt = select(User.id, User.display_name).where(User.id.in_(user_ids))
        users_result = session.execute(users_stmt)
        user_names = {uid: name for uid, name in users_result}
    else:
        user_names = {}

    # Build response
    attempt_responses = [
        ContactAttemptResponse(
            id=a.id,
            case_id=a.case_id,
            attempted_by_user_id=a.attempted_by_user_id,
            attempted_by_name=user_names.get(a.attempted_by_user_id),
            contact_methods=a.contact_methods,
            outcome=a.outcome,
            notes=a.notes,
            attempted_at=a.attempted_at,
            created_at=a.created_at,
            is_backdated=a.is_backdated,
            case_owner_id_at_attempt=a.case_owner_id_at_attempt,
        )
        for a in attempts
    ]

    return ContactAttemptsSummary(
        total_attempts=total_attempts,
        current_assignment_attempts=current_assignment_attempts,
        distinct_days_current_assignment=distinct_days,
        successful_attempts=successful_attempts,
        last_attempt_at=last_attempt_at,
        days_since_last_attempt=days_since,
        attempts=attempt_responses,
    )


def get_cases_needing_followup(
    session: Session,
    org_id: UUID,
    org_timezone: str,
) -> list[dict]:
    """
    Find cases that need contact follow-up reminders.

    Criteria:
    - owner_type = 'user' (not queue)
    - contact_status = 'unreached'
    - is_intake_stage = true
    - assigned_at IS NOT NULL
    - EITHER:
        - No attempts yet AND today > assigned_day
        - OR distinct_days < 3 AND last_attempt_day < today

    Returns list of dicts with case info for notification creation.
    """
    # Build query with CTE
    query = text("""
        WITH case_stats AS (
            SELECT 
                c.id,
                c.case_number,
                c.owner_id,
                c.organization_id,
                c.assigned_at,
                c.contact_status,
                ps.is_intake_stage,
                date(c.assigned_at AT TIME ZONE :org_tz) as assigned_day,
                COUNT(DISTINCT date(ca.attempted_at AT TIME ZONE :org_tz)) FILTER (
                    WHERE ca.case_owner_id_at_attempt = c.owner_id
                ) as distinct_attempt_days,
                MAX(date(ca.attempted_at AT TIME ZONE :org_tz)) FILTER (
                    WHERE ca.case_owner_id_at_attempt = c.owner_id
                ) as last_attempt_day,
                date(now() AT TIME ZONE :org_tz) as today
            FROM cases c
            JOIN pipeline_stages ps ON ps.id = c.stage_id
            LEFT JOIN case_contact_attempts ca ON ca.case_id = c.id
            WHERE 
                c.organization_id = :org_id
                AND c.is_archived = FALSE
                AND c.owner_type = 'user'
                AND c.contact_status = 'unreached'
                AND ps.is_intake_stage = true
                AND c.assigned_at IS NOT NULL
            GROUP BY c.id, ps.is_intake_stage
        )
        SELECT * FROM case_stats
        WHERE (
            -- No attempts yet, and at least 1 day has passed since assignment
            (distinct_attempt_days = 0 AND today > assigned_day)
            OR
            -- Has attempts but less than 3 distinct days, and last attempt was before today
            (distinct_attempt_days > 0 AND distinct_attempt_days < 3 AND last_attempt_day < today)
        )
    """)

    result = session.execute(query, {"org_id": str(org_id), "org_tz": org_timezone})

    return [dict(row._mapping) for row in result]
