"""Email channel for in-app notifications.

A notification whose recipient opted in to email for its type queues one platform
email in the transactional outbox, in the transaction that creates the notification.
The outbox worker sends it with leased retries; nothing is sent inline.
"""

from __future__ import annotations

import logging
from html import escape as html_escape
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import NotificationType
from app.db.models import Membership, Notification, Organization, User
from app.services import (
    email_service,
    notification_service,
    org_service,
    platform_email_service,
    system_email_template_service,
)

logger = logging.getLogger(__name__)

SOURCE_TYPE = "notification_email"


def idempotency_key(notification_id: UUID) -> str:
    return f"notification-email:{notification_id}"


def record_path(notification: Notification) -> str | None:
    """Path of the record the notification points to.

    Mirrors apps/web/lib/utils/notification-routing.ts so the email opens the same page
    as the in-app click-through. Status change requests open the record: the pending
    request id is not stored on the notification.
    """
    if notification.entity_id is None:
        return None
    entity_id = notification.entity_id
    entity_type = notification.entity_type
    if notification.type == NotificationType.WORKFLOW_APPROVAL_REQUESTED.value:
        return f"/tasks?filter=my_tasks&focus=approvals&approval={entity_id}"
    if entity_type in {"surrogate", "case"}:
        return f"/surrogates/{entity_id}"
    if entity_type == "intended_parent":
        return f"/intended-parents/{entity_id}"
    if entity_type == "match":
        return f"/intended-parents/matches/{entity_id}"
    if entity_type == "donor":
        return f"/donors/{entity_id}"
    if entity_type in {"task", "donor_task"}:
        return f"/tasks?filter=my_tasks&task={entity_id}"
    if entity_type == "appointment":
        return f"/appointments?appointment={entity_id}"
    return None


def _active_recipient(db: Session, org_id: UUID, user_id: UUID) -> User | None:
    return (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            User.id == user_id,
            User.is_active.is_(True),
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .first()
    )


def render_staff_email(
    db: Session,
    *,
    org: Organization,
    title: str,
    body_block: str,
    link_url: str | None,
    link_label: str,
) -> tuple[str, str, str | None]:
    """Render the staff notification system template. Returns (subject, html, from_email).

    body_block is trusted HTML; callers escape any user content in it.
    """
    template = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.STAFF_NOTIFICATION_SYSTEM_KEY
    )
    if template.is_active:
        subject_template, body_template = template.subject, template.body
    else:
        defaults = system_email_template_service.get_system_template_defaults(
            system_email_template_service.STAFF_NOTIFICATION_SYSTEM_KEY
        )
        subject_template, body_template = defaults["subject"], defaults["body"]

    link_block = (
        f'<a href="{html_escape(link_url, quote=True)}" target="_blank" '
        'style="display: inline-block; padding: 10px 18px; border-radius: 10px; '
        "background-color: #111827; color: #ffffff; text-decoration: none; "
        f'font-size: 14px; font-weight: 600;">{html_escape(link_label)}</a>'
        if link_url
        else ""
    )
    subject, html = email_service.render_template(
        subject_template,
        body_template,
        {
            "org_name": org_service.get_org_display_name(org),
            "title": title,
            "body_block": body_block,
            "link_block": link_block,
        },
        safe_html_vars={"body_block", "link_block"},
    )
    return subject, html, template.from_email


def record_url(org: Organization, notification: Notification) -> str | None:
    path = record_path(notification)
    base_url = org_service.get_org_portal_base_url(org)
    return f"{base_url}{path}" if path and base_url else None


def _render(
    db: Session,
    *,
    notification: Notification,
    org: Organization,
) -> tuple[str, str, str, str | None]:
    """Return (subject, html, text, from_email)."""
    body = (notification.body or "").strip()
    url = record_url(org, notification)
    body_block = (
        '<p style="margin: 0; font-size: 15px; line-height: 1.6; color: #374151;">'
        + html_escape(body).replace("\n", "<br>")
        + "</p>"
        if body
        else ""
    )
    subject, html, from_email = render_staff_email(
        db,
        org=org,
        title=notification.title,
        body_block=body_block,
        link_url=url,
        link_label="View record",
    )
    text_parts = [notification.title]
    if body:
        text_parts.append(body)
    if url:
        text_parts.append(f"View record: {url}")
    return subject, html, "\n\n".join(text_parts) + "\n", from_email


def queue_notification_email(db: Session, notification: Notification) -> bool:
    """Queue the email copy of a flushed notification when its recipient opted in.

    Runs in the caller's transaction and does not commit. Returns True when a
    delivery is queued or already exists for this notification.
    """
    org_id = notification.organization_id
    user_id = notification.user_id
    if not notification_service.wants_email(db, user_id, org_id, notification.type):
        return False

    recipient = _active_recipient(db, org_id, user_id)
    if recipient is None:
        return False
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None or org.deleted_at is not None:
        return False
    if not platform_email_service.platform_sender_configured():
        logger.warning(
            "Notification email skipped: platform sender not configured notification_id=%s",
            notification.id,
        )
        return False

    subject, html, text, from_email = _render(db, notification=notification, org=org)
    result = platform_email_service.queue_email_logged(
        db=db,
        org_id=org_id,
        to_email=recipient.email,
        subject=subject,
        from_email=from_email,
        html=html,
        text=text,
        idempotency_key=idempotency_key(notification.id),
        source_type=SOURCE_TYPE,
        source_id=notification.id,
        commit=False,
    )
    if not result.get("success"):
        # Errors from queue_email_logged are fixed strings without recipient or content.
        logger.warning(
            "Notification email not queued notification_id=%s reason=%s",
            notification.id,
            result.get("error"),
        )
        return False
    return True


def is_notification_email_delivery_eligible(
    db: Session,
    org_id: UUID,
    notification_id: UUID | None,
    recipient_email: str | None,
) -> bool:
    """Re-check membership, opt-in, and address before the outbox sends."""
    if notification_id is None:
        return False
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.organization_id == org_id)
        .first()
    )
    if notification is None:
        return False
    if not notification_service.wants_email(db, notification.user_id, org_id, notification.type):
        return False
    recipient = _active_recipient(db, org_id, notification.user_id)
    if recipient is None:
        return False
    return (recipient.email or "").strip().lower() == (recipient_email or "").strip().lower()
