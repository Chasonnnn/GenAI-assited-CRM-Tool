"""Campaign template snapshots and recipient content."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    Campaign,
    CampaignRun,
    EmailTemplate,
    MessageTemplate,
)
from app.services import campaign_audience
from app.services.email_template_snapshot import (
    EmailTemplateSnapshot,
    build_snapshot,
    format_from_address,
    parse_snapshot,
)

DONOR_LAUNCH_SNAPSHOT_VERSION = 1


def build_recipient_template_variables(db: Session, recipient_type: str, entity):
    from app.services import email_service

    if recipient_type == "case":
        return email_service.build_surrogate_template_variables(db, entity)
    if recipient_type == "intended_parent":
        return email_service.build_intended_parent_template_variables(db, entity)
    if recipient_type in campaign_audience.DONOR_RECIPIENT_TYPES:
        return email_service.build_donor_template_variables(db, entity)
    raise ValueError(f"Unknown recipient type: {recipient_type}")


def build_donor_launch_snapshot(
    *,
    recipient_email: str,
    recipient_name: str,
    subject: str,
    body: str,
) -> dict:
    """Capture the exact donor identity and rendered content approved at launch."""
    return {
        "version": DONOR_LAUNCH_SNAPSHOT_VERSION,
        "recipient_email": recipient_email,
        "recipient_name": recipient_name,
        "subject": subject,
        "body": body,
    }


def parse_donor_launch_snapshot(value: dict | None) -> dict | None:
    """Validate a persisted donor launch snapshot before any retry can send it."""
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("version") != DONOR_LAUNCH_SNAPSHOT_VERSION:
        raise ValueError("invalid_donor_launch_snapshot")
    for key in ("recipient_email", "recipient_name", "subject", "body"):
        if not isinstance(value.get(key), str):
            raise ValueError("invalid_donor_launch_snapshot")
    if not value["recipient_email"].strip():
        raise ValueError("invalid_donor_launch_snapshot")
    return value


def load_published_message_template(
    db: Session,
    *,
    org_id: UUID,
    template_version_id: UUID | None,
    purpose: str = "promotional",
    lock: bool = False,
) -> MessageTemplate:
    if template_version_id is None:
        raise ValueError("Messaging campaigns require a message template version")
    query = db.query(MessageTemplate).filter(
        MessageTemplate.id == template_version_id,
        MessageTemplate.organization_id == org_id,
        MessageTemplate.status == "published",
        MessageTemplate.purpose == purpose,
    )
    if lock:
        query = query.with_for_update()
    template = query.first()
    if template is None:
        raise ValueError(f"Published {purpose} message template not found")
    return template


def snapshot_campaign_template(template: EmailTemplate, provider_config) -> dict:
    template_from = (template.from_email or "").strip()
    effective_from = format_from_address(
        template_from or getattr(provider_config, "from_email", None),
        getattr(provider_config, "from_name", None),
    )
    return build_snapshot(
        template,
        effective_from_email=effective_from,
    )


def load_campaign_run_template(
    db: Session,
    *,
    org_id: UUID,
    campaign: Campaign,
    run: CampaignRun,
) -> EmailTemplateSnapshot:
    if run.email_template_snapshot is not None:
        snapshot = parse_snapshot(run.email_template_snapshot)
        if snapshot.organization_id != org_id or snapshot.template_id != campaign.email_template_id:
            raise ValueError("Campaign email template snapshot does not match campaign")
        return snapshot

    # Compatibility for completed/legacy rows that were not eligible for the
    # migration backfill. New runs always persist a snapshot before queueing.
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == campaign.email_template_id,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )
    if template is None:
        raise Exception(f"Email template {campaign.email_template_id} not found")
    return EmailTemplateSnapshot(
        organization_id=org_id,
        template_id=template.id,
        template_version=template.current_version,
        subject=template.subject,
        body=template.body,
        from_email=template.from_email,
    )
