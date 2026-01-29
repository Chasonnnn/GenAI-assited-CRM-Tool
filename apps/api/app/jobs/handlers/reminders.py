"""Reminder job handlers."""

from __future__ import annotations

import logging

from app.services import email_service

logger = logging.getLogger(__name__)


async def process_reminder(db, job) -> None:
    """Process reminder job - create notification and/or send email."""
    logger.info("Processing reminder job %s", job.id)
    payload = job.payload or {}

    # Create in-app notification if user_id provided
    if payload.get("user_id") and payload.get("message"):
        from app.db.models import Notification

        notification = Notification(
            organization_id=job.organization_id,
            user_id=payload["user_id"],
            title=payload.get("title", "Reminder"),
            message=payload["message"],
            notification_type=payload.get("type", "task_due"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
        )
        db.add(notification)
        db.commit()

    # Optionally send reminder email
    if payload.get("send_email") and payload.get("user_id"):
        from app.db.models import User

        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if user and user.email:
            email_service.send_reminder_email(
                db=db,
                org_id=job.organization_id,
                to_email=user.email,
                subject=payload.get("title", "Reminder"),
                message=payload["message"],
            )
