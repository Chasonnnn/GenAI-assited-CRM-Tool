"""Notification job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

from app.db.enums import NotificationType
from app.services import notification_service

logger = logging.getLogger(__name__)


def _coerce_notification_type(raw_type: str | None) -> NotificationType:
    if not raw_type:
        return NotificationType.WORKFLOW_NOTIFICATION
    try:
        return NotificationType(raw_type)
    except ValueError:
        logger.warning(
            "Unknown notification type '%s'; defaulting to workflow_notification", raw_type
        )
        return NotificationType.WORKFLOW_NOTIFICATION


def _coerce_uuid(raw_id: str | None) -> UUID | None:
    if not raw_id:
        return None
    try:
        return UUID(str(raw_id))
    except (TypeError, ValueError):
        logger.warning("Invalid UUID value '%s' in notification payload", raw_id)
        return None


async def process_notification(db, job) -> None:
    """Process notification job - create in-app notification record."""
    logger.info("Processing notification job %s", job.id)
    payload = job.payload or {}

    user_id = _coerce_uuid(payload.get("user_id"))
    body = payload.get("body") or payload.get("message")
    if not user_id or not body:
        return

    notification_service.create_notification(
        db=db,
        org_id=job.organization_id,
        user_id=user_id,
        type=_coerce_notification_type(payload.get("type")),
        title=payload.get("title", "Notification"),
        body=body,
        entity_type=payload.get("entity_type"),
        entity_id=_coerce_uuid(payload.get("entity_id")),
        dedupe_key=payload.get("dedupe_key"),
    )
    logger.info("Created notification for user %s", user_id)
