"""Notification job handlers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def process_notification(db, job) -> None:
    """Process notification job - create in-app notification record."""
    logger.info("Processing notification job %s", job.id)
    payload = job.payload or {}

    if payload.get("user_id") and payload.get("message"):
        from app.db.models import Notification

        notification = Notification(
            organization_id=job.organization_id,
            user_id=payload["user_id"],
            title=payload.get("title", "Notification"),
            message=payload["message"],
            notification_type=payload.get("type", "general"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
        )
        db.add(notification)
        db.commit()
        logger.info("Created notification for user %s", payload["user_id"])
