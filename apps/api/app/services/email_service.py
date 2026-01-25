"""Email service - business logic for email templates and sending.

v2: With version control for templates.
"""

from email.utils import parseaddr
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

import nh3
from email_validator import EmailNotValidError, validate_email

from app.db.models import EmailTemplate, EmailLog, Job, Surrogate
from app.db.enums import EmailStatus, JobType
from app.services.job_service import enqueue_job
from app.services import version_service


# Variable pattern for template substitution: {{variable_name}}
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

ENTITY_TYPE = "email_template"

ALLOWED_TEMPLATE_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "u",
    "ul",
    "ol",
    "li",
    "a",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "code",
    "pre",
    "span",
}
ALLOWED_TEMPLATE_ATTRS = {"a": {"href", "target"}}

_UNSET = object()


def sanitize_template_html(html: str) -> str:
    """Sanitize email template HTML to prevent XSS."""
    return nh3.clean(html, tags=ALLOWED_TEMPLATE_TAGS, attributes=ALLOWED_TEMPLATE_ATTRS)


def _normalize_from_email(value: str | None) -> str | None:
    """Normalize optional From header overrides.

    Accepts either a bare email (e.g. "invites@surrogacyforce.com") or
    a display name + email (e.g. "Surrogacy Force <invites@surrogacyforce.com>").
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    _, addr = parseaddr(text)
    try:
        validate_email(addr, check_deliverability=False)
    except EmailNotValidError as e:
        raise ValueError("Invalid from_email") from e
    return text


def _template_payload(template: EmailTemplate) -> dict:
    """Extract versionable payload from template."""
    return {
        "name": template.name,
        "subject": template.subject,
        "from_email": template.from_email,
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
    from_email: str | None = None,
) -> EmailTemplate:
    """Create a new email template with initial version snapshot."""
    clean_body = sanitize_template_html(body)
    template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=name,
        subject=subject,
        from_email=_normalize_from_email(from_email),
        body=clean_body,
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
    from_email: str | None | object = _UNSET,
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
    if from_email is not _UNSET:
        template.from_email = _normalize_from_email(from_email if isinstance(from_email, str) else None)
    if body is not None:
        template.body = sanitize_template_html(body)
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
    template.from_email = payload.get("from_email", template.from_email)
    if "body" in payload:
        template.body = sanitize_template_html(payload.get("body") or "")
    template.is_active = payload.get("is_active", template.is_active)
    template.current_version = new_version.version
    template.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(template)
    return template, None


def get_template(db: Session, template_id: UUID, org_id: UUID) -> EmailTemplate | None:
    """Get template by ID, scoped to org."""
    return (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )


def get_template_by_name(db: Session, name: str, org_id: UUID) -> EmailTemplate | None:
    """Get template by name, scoped to org."""
    return (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.name == name,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )


def list_templates(
    db: Session,
    org_id: UUID,
    active_only: bool = True,
) -> list[EmailTemplate]:
    """List email templates for an organization."""
    query = db.query(EmailTemplate).filter(EmailTemplate.organization_id == org_id)
    if active_only:
        query = query.filter(EmailTemplate.is_active.is_(True))
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


def build_surrogate_template_variables(db: Session, surrogate: Surrogate) -> dict[str, str]:
    """Build flat template variables for a surrogate context."""
    from app.db.enums import OwnerType
    from app.db.models import Organization, Queue, User

    org = db.query(Organization).filter(Organization.id == surrogate.organization_id).first()

    owner_name = ""
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id:
        owner = db.query(User).filter(User.id == surrogate.owner_id).first()
        owner_name = owner.display_name if owner else ""
    elif surrogate.owner_type == OwnerType.QUEUE.value and surrogate.owner_id:
        queue = db.query(Queue).filter(Queue.id == surrogate.owner_id).first()
        owner_name = queue.name if queue else ""

    return {
        "full_name": surrogate.full_name or "",
        "email": surrogate.email or "",
        "phone": surrogate.phone or "",
        "surrogate_number": surrogate.surrogate_number or "",
        "status_label": surrogate.status_label or "",
        "state": surrogate.state or "",
        "owner_name": owner_name,
        "org_name": org.name if org else "",
    }


def build_appointment_template_variables(
    db: Session,
    appointment,
    surrogate: Surrogate | None = None,
) -> dict[str, str]:
    """
    Build template variables for an appointment context.

    Formats appointment times in the client's timezone (or org timezone fallback).
    Uses client_timezone from the appointment for user-facing display.
    """
    from zoneinfo import ZoneInfo
    from app.db.models import Organization

    # Get org for fallback timezone
    org = db.query(Organization).filter(Organization.id == appointment.organization_id).first()

    # Use appointment's client_timezone, fall back to org timezone
    tz_name = getattr(appointment, "client_timezone", None) or (
        org.timezone if org else "America/Los_Angeles"
    )
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = ZoneInfo("America/Los_Angeles")

    # Convert UTC times to local timezone
    local_start = appointment.scheduled_start.astimezone(local_tz)

    # Format date and time in user-friendly format
    appointment_date = local_start.strftime("%A, %B %d, %Y")  # "Monday, December 25, 2024"
    appointment_time = local_start.strftime("%I:%M %p %Z")  # "2:30 PM PST"

    # Get location (virtual link or physical address)
    location = ""
    if hasattr(appointment, "video_link") and appointment.video_link:
        location = appointment.video_link
    elif hasattr(appointment, "location") and appointment.location:
        location = appointment.location
    else:
        location = "To be confirmed"

    variables = {
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_location": location,
        "org_name": org.name if org else "",
    }

    # Merge in surrogate variables if provided
    if surrogate:
        surrogate_vars = build_surrogate_template_variables(db, surrogate)
        variables.update(surrogate_vars)

    return variables


def send_email(
    db: Session,
    org_id: UUID,
    template_id: UUID | None,
    recipient_email: str,
    subject: str,
    body: str,
    surrogate_id: UUID | None = None,
    schedule_at: datetime | None = None,
    commit: bool = True,
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
        surrogate_id=surrogate_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.flush()  # Get ID before creating job

    # Schedule job to send
    job = enqueue_job(
        db=db,
        org_id=org_id,
        job_type=JobType.SEND_EMAIL,
        payload={"email_log_id": str(email_log.id)},
        run_at=schedule_at,
        commit=commit,
    )

    # Link job to email log
    email_log.job_id = job.id
    if commit:
        db.commit()
        db.refresh(email_log)
    else:
        db.flush()

    return email_log, job


def send_from_template(
    db: Session,
    org_id: UUID,
    template_id: UUID,
    recipient_email: str,
    variables: dict[str, str],
    surrogate_id: UUID | None = None,
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
        surrogate_id=surrogate_id,
        schedule_at=schedule_at,
    )


def mark_email_sent(db: Session, email_log: EmailLog) -> EmailLog:
    """Mark an email as sent."""
    email_log.status = EmailStatus.SENT.value
    email_log.sent_at = datetime.now(timezone.utc)
    email_log.error = None
    db.commit()
    db.refresh(email_log)
    _sync_campaign_recipient(db, email_log, EmailStatus.SENT.value)
    return email_log


def mark_email_failed(db: Session, email_log: EmailLog, error: str) -> EmailLog:
    """Mark an email as failed."""
    email_log.status = EmailStatus.FAILED.value
    email_log.error = error
    db.commit()
    db.refresh(email_log)
    _sync_campaign_recipient(db, email_log, EmailStatus.FAILED.value, error=error)
    return email_log


def get_email_log(db: Session, email_id: UUID, org_id: UUID) -> EmailLog | None:
    """Get email log by ID, scoped to org."""
    return (
        db.query(EmailLog)
        .filter(
            EmailLog.id == email_id,
            EmailLog.organization_id == org_id,
        )
        .first()
    )


def list_email_logs(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID | None = None,
    status: EmailStatus | None = None,
    limit: int = 50,
) -> list[EmailLog]:
    """List email logs for an organization with optional filters."""
    query = db.query(EmailLog).filter(EmailLog.organization_id == org_id)
    if surrogate_id:
        query = query.filter(EmailLog.surrogate_id == surrogate_id)
    if status:
        query = query.filter(EmailLog.status == status.value)
    return query.order_by(EmailLog.created_at.desc()).limit(limit).all()


def _sync_campaign_recipient(
    db: Session,
    email_log: EmailLog,
    status: str,
    error: str | None = None,
) -> None:
    """Update campaign recipient/run stats when an email log changes."""
    from app.db.models import CampaignRecipient, CampaignRun, Campaign
    from app.db.enums import CampaignRecipientStatus, CampaignStatus

    cr = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.external_message_id == str(email_log.id))
        .first()
    )
    if not cr:
        return

    if status == EmailStatus.SENT.value:
        cr.status = CampaignRecipientStatus.SENT.value
        if not cr.sent_at:
            cr.sent_at = datetime.now(timezone.utc)
        cr.error = None
    else:
        cr.status = CampaignRecipientStatus.FAILED.value
        cr.error = (error or email_log.error or "Send failed")[:500]

    db.commit()

    run = db.query(CampaignRun).filter(CampaignRun.id == cr.run_id).first()
    if not run:
        return

    status_rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.run_id == run.id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0)
    run.failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)

    if pending_count == 0:
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed" if run.failed_count == 0 else "failed"
    else:
        run.status = "running"
        run.completed_at = None

    campaign = db.query(Campaign).filter(Campaign.id == run.campaign_id).first()
    if campaign:
        campaign.sent_count = run.sent_count
        campaign.failed_count = run.failed_count
        campaign.skipped_count = run.skipped_count
        campaign.total_recipients = run.total_count
        if pending_count == 0:
            campaign.status = (
                CampaignStatus.COMPLETED.value
                if run.failed_count == 0
                else CampaignStatus.FAILED.value
            )
        else:
            campaign.status = CampaignStatus.SENDING.value

    db.commit()
