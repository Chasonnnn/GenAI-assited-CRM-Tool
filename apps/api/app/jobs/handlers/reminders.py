"""Reminder job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

from app.db.enums import NotificationType
from app.services import email_service
from app.services import notification_service

logger = logging.getLogger(__name__)


def _coerce_notification_type(raw_type: str | None) -> NotificationType:
    if not raw_type:
        return NotificationType.CONTACT_REMINDER
    try:
        return NotificationType(raw_type)
    except ValueError:
        logger.warning("Unknown reminder notification type '%s'; defaulting to contact_reminder", raw_type)
        return NotificationType.CONTACT_REMINDER


def _coerce_uuid(raw_id: str | None) -> UUID | None:
    if not raw_id:
        return None
    try:
        return UUID(str(raw_id))
    except (TypeError, ValueError):
        logger.warning("Invalid UUID value '%s' in reminder payload", raw_id)
        return None


async def process_reminder(db, job) -> None:
    """Process reminder job - create notification and/or send email."""
    logger.info("Processing reminder job %s", job.id)
    payload = job.payload or {}

    # Create in-app notification if user_id provided
    user_id = _coerce_uuid(payload.get("user_id"))
    body = payload.get("body") or payload.get("message")
    if user_id and body:
        notification_service.create_notification(
            db=db,
            org_id=job.organization_id,
            user_id=user_id,
            type=_coerce_notification_type(payload.get("type")),
            title=payload.get("title", "Reminder"),
            body=body,
            entity_type=payload.get("entity_type"),
            entity_id=_coerce_uuid(payload.get("entity_id")),
            dedupe_key=payload.get("dedupe_key"),
        )

    # Optionally send reminder email
    if payload.get("send_email") and user_id and body:
        from app.db.models import User

        user = db.query(User).filter(User.id == user_id).first()
        if user and user.email:
            email_service.send_reminder_email(
                db=db,
                org_id=job.organization_id,
                to_email=user.email,
                subject=payload.get("title", "Reminder"),
                message=body,
            )
