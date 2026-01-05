"""Service layer for automated contact reminders."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import NotificationType
from app.db.models import Organization
from app.services import notification_service
from app.services.contact_attempt_service import get_cases_needing_followup


def check_contact_reminders_for_org(
    session: Session,
    org_id: UUID,
) -> dict:
    """
    Check for cases needing follow-up and create reminder notifications.

    Returns stats: {cases_checked, notifications_created}
    """
    # Get organization timezone
    org_stmt = select(Organization.timezone).where(Organization.id == org_id)
    org_result = session.execute(org_stmt)
    org_tz = org_result.scalar_one_or_none()

    if not org_tz:
        raise ValueError(f"Organization {org_id} not found")

    # Get cases needing follow-up
    cases = get_cases_needing_followup(session, org_id, org_tz)

    notifications_created = 0

    # Create notifications for each case
    for case_data in cases:
        case_id = case_data["id"]
        case_number = case_data["case_number"]
        owner_id = case_data["owner_id"]
        distinct_days = case_data["distinct_attempt_days"]
        
        # Calculate days since assignment
        assigned_day = case_data["assigned_day"]
        today = case_data["today"]
        days_ago = (today - assigned_day).days if assigned_day else 0

        if not notification_service.should_notify(
            session, owner_id, org_id, "contact_reminder"
        ):
            continue

        # Create dedupe key with today's date (in org timezone)
        today_str = today.isoformat() if hasattr(today, 'isoformat') else str(today)
        dedupe_key = f"contact_reminder:{case_id}:{today_str}"

        notification = notification_service.create_notification(
            db=session,
            org_id=org_id,
            user_id=owner_id,
            type=NotificationType.CONTACT_REMINDER,
            title=f"Follow-up needed: Case #{case_number}",
            body=(
                f"This case needs contact attempt #{distinct_days + 1} "
                f"(assigned {days_ago} days ago)"
            ),
            entity_type="case",
            entity_id=case_id,
            dedupe_key=dedupe_key,
            dedupe_window_hours=None,
        )

        if notification:
            notifications_created += 1

    return {
        "cases_checked": len(cases),
        "notifications_created": notifications_created,
    }


def process_contact_reminder_jobs(session: Session) -> dict:
    """
    Process contact reminder jobs for all active organizations.

    Entry point for daily reminder job worker.
    
    Returns summary stats.
    """
    # Get all active organizations
    orgs_stmt = select(Organization.id, Organization.name)
    orgs_result = session.execute(orgs_stmt)
    orgs = orgs_result.all()

    total_cases = 0
    total_notifications = 0
    errors = []

    for org_id, org_name in orgs:
        try:
            stats = check_contact_reminders_for_org(session, org_id)
            total_cases += stats["cases_checked"]
            total_notifications += stats["notifications_created"]
        except Exception as e:
            errors.append({"org_id": str(org_id), "org_name": org_name, "error": str(e)})

    return {
        "orgs_processed": len(orgs),
        "total_cases_checked": total_cases,
        "total_notifications_created": total_notifications,
        "errors": errors,
    }
