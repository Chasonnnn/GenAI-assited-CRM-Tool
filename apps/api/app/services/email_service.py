"""Email service - business logic for email templates and sending."""

import re
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import EmailTemplate, EmailLog, Job
from app.db.enums import EmailStatus, JobType
from app.services.job_service import schedule_job


# Variable pattern for template substitution: {{variable_name}}
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    subject: str,
    body: str,
) -> EmailTemplate:
    """Create a new email template."""
    template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=name,
        subject=subject,
        body=body,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template: EmailTemplate,
    name: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    is_active: bool | None = None,
) -> EmailTemplate:
    """Update an email template."""
    if name is not None:
        template.name = name
    if subject is not None:
        template.subject = subject
    if body is not None:
        template.body = body
    if is_active is not None:
        template.is_active = is_active
    db.commit()
    db.refresh(template)
    return template


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
