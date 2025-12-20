"""Email service - business logic for email templates and sending.

v2: With version control for templates.
"""

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import EmailTemplate, EmailLog, Job, Case
from app.db.enums import EmailStatus, JobType
from app.services.job_service import schedule_job
from app.services import version_service


# Variable pattern for template substitution: {{variable_name}}
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

ENTITY_TYPE = "email_template"


def _template_payload(template: EmailTemplate) -> dict:
    """Extract versionable payload from template."""
    return {
        "name": template.name,
        "subject": template.subject,
        "body": template.body,
        "is_active": template.is_active,
    }

def create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    subject: str,
    body: str,
) -> EmailTemplate:
    """Create a new email template with initial version snapshot."""
    template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=name,
        subject=subject,
        body=body,
        is_active=True,
        current_version=1,
    )
    db.add(template)
    db.flush()
    
    # Create initial version snapshot
    version_service.create_version(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        payload=_template_payload(template),
        created_by_user_id=user_id,
        comment="Created",
    )
    
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template: EmailTemplate,
    user_id: UUID,
    name: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    is_active: bool | None = None,
    expected_version: int | None = None,
    comment: str | None = None,
) -> EmailTemplate:
    """
    Update an email template with version control.
    
    Creates version snapshot on changes.
    Supports optimistic locking via expected_version.
    """
    # Optimistic locking
    if expected_version is not None:
        version_service.check_version(template.current_version, expected_version)
    
    if name is not None:
        template.name = name
    if subject is not None:
        template.subject = subject
    if body is not None:
        template.body = body
    if is_active is not None:
        template.is_active = is_active
    
    # Increment version and snapshot
    template.current_version += 1
    template.updated_at = datetime.now(timezone.utc)
    
    version_service.create_version(
        db=db,
        org_id=template.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        payload=_template_payload(template),
        created_by_user_id=user_id,
        comment=comment or "Updated",
    )
    
    db.commit()
    db.refresh(template)
    return template


def get_template_versions(
    db: Session,
    org_id: UUID,
    template_id: UUID,
    limit: int = 50,
) -> list:
    """Get version history for a template."""
    return version_service.get_version_history(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=template_id,
        limit=limit,
    )


def rollback_template(
    db: Session,
    template: EmailTemplate,
    target_version: int,
    user_id: UUID,
) -> tuple[EmailTemplate | None, str | None]:
    """
    Rollback template to a previous version.
    
    Creates a NEW version with old payload.
    Returns (updated_template, error).
    """
    new_version, error = version_service.rollback_to_version(
        db=db,
        org_id=template.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        target_version=target_version,
        user_id=user_id,
    )
    
    if error:
        return None, error
    
    # Apply rolled-back payload
    payload = version_service.decrypt_payload(new_version.payload_encrypted)
    template.name = payload.get("name", template.name)
    template.subject = payload.get("subject", template.subject)
    template.body = payload.get("body", template.body)
    template.is_active = payload.get("is_active", template.is_active)
    template.current_version = new_version.version
    template.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(template)
    return template, None

def get_template(db: Session, template_id: UUID, org_id: UUID) -> EmailTemplate | None:
    """Get template by ID, scoped to org."""
    return db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.organization_id == org_id,
    ).first()


def get_template_by_name(db: Session, name: str, org_id: UUID) -> EmailTemplate | None:
    """Get template by name, scoped to org."""
    return db.query(EmailTemplate).filter(
        EmailTemplate.name == name,
        EmailTemplate.organization_id == org_id,
    ).first()


def list_templates(
    db: Session,
    org_id: UUID,
    active_only: bool = True,
) -> list[EmailTemplate]:
    """List email templates for an organization."""
    query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id
    )
    if active_only:
        query = query.filter(EmailTemplate.is_active == True)
    return query.order_by(EmailTemplate.name).all()


def delete_template(db: Session, template: EmailTemplate) -> None:
    """Soft delete a template (deactivate)."""
    template.is_active = False
    db.commit()


def render_template(
    subject: str,
    body: str,
    variables: dict[str, str],
) -> tuple[str, str]:
    """
    Render a template with variable substitution.
    
    Variables in format {{variable_name}} are replaced with values.
    Missing variables are replaced with empty string.
    
    Returns (rendered_subject, rendered_body).
    """
    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        return variables.get(var_name, "")
    
    rendered_subject = VARIABLE_PATTERN.sub(replace_var, subject)
    rendered_body = VARIABLE_PATTERN.sub(replace_var, body)
    return rendered_subject, rendered_body


def build_case_template_variables(db: Session, case: Case) -> dict[str, str]:
    """Build flat template variables for a case context."""
    from app.db.enums import OwnerType
    from app.db.models import Organization, Queue, User

    org = db.query(Organization).filter(Organization.id == case.organization_id).first()

    owner_name = ""
    if case.owner_type == OwnerType.USER.value and case.owner_id:
        owner = db.query(User).filter(User.id == case.owner_id).first()
        owner_name = owner.display_name if owner else ""
    elif case.owner_type == OwnerType.QUEUE.value and case.owner_id:
        queue = db.query(Queue).filter(Queue.id == case.owner_id).first()
        owner_name = queue.name if queue else ""

    return {
        "full_name": case.full_name or "",
        "email": case.email or "",
        "phone": case.phone or "",
        "case_number": case.case_number or "",
        "status_label": case.status_label or "",
        "state": case.state or "",
        "owner_name": owner_name,
        "org_name": org.name if org else "",
    }


def send_email(
    db: Session,
    org_id: UUID,
    template_id: UUID | None,
    recipient_email: str,
    subject: str,
    body: str,
    case_id: UUID | None = None,
    schedule_at: datetime | None = None,
) -> tuple[EmailLog, Job]:
    """
    Queue an email for sending.
    
    Creates an EmailLog record and schedules a job to send it.
    Returns (email_log, job).
    """
    # Create email log
    email_log = EmailLog(
        organization_id=org_id,
        template_id=template_id,
        case_id=case_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.flush()  # Get ID before creating job
    
    # Schedule job to send
    job = schedule_job(
        db=db,
        org_id=org_id,
        job_type=JobType.SEND_EMAIL,
        payload={"email_log_id": str(email_log.id)},
        run_at=schedule_at,
    )
    
    # Link job to email log
    email_log.job_id = job.id
    db.commit()
    db.refresh(email_log)
    
    return email_log, job


def send_from_template(
    db: Session,
    org_id: UUID,
    template_id: UUID,
    recipient_email: str,
    variables: dict[str, str],
    case_id: UUID | None = None,
    schedule_at: datetime | None = None,
) -> tuple[EmailLog, Job] | None:
    """
    Queue an email using a template.
    
    Renders the template with variables and queues for sending.
    Returns (email_log, job) or None if template not found.
    """
    template = get_template(db, template_id, org_id)
    if not template:
        return None
    
    subject, body = render_template(template.subject, template.body, variables)
    return send_email(
        db=db,
        org_id=org_id,
        template_id=template_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        case_id=case_id,
        schedule_at=schedule_at,
    )


def mark_email_sent(db: Session, email_log: EmailLog) -> EmailLog:
    """Mark an email as sent."""
    email_log.status = EmailStatus.SENT.value
    email_log.sent_at = datetime.utcnow()
    email_log.error = None
    db.commit()
    db.refresh(email_log)
    return email_log


def mark_email_failed(db: Session, email_log: EmailLog, error: str) -> EmailLog:
    """Mark an email as failed."""
    email_log.status = EmailStatus.FAILED.value
    email_log.error = error
    db.commit()
    db.refresh(email_log)
    return email_log


def get_email_log(db: Session, email_id: UUID, org_id: UUID) -> EmailLog | None:
    """Get email log by ID, scoped to org."""
    return db.query(EmailLog).filter(
        EmailLog.id == email_id,
        EmailLog.organization_id == org_id,
    ).first()


def list_email_logs(
    db: Session,
    org_id: UUID,
    case_id: UUID | None = None,
    status: EmailStatus | None = None,
    limit: int = 50,
) -> list[EmailLog]:
    """List email logs for an organization with optional filters."""
    query = db.query(EmailLog).filter(EmailLog.organization_id == org_id)
    if case_id:
        query = query.filter(EmailLog.case_id == case_id)
    if status:
        query = query.filter(EmailLog.status == status.value)
    return query.order_by(EmailLog.created_at.desc()).limit(limit).all()
