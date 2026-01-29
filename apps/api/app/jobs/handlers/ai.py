"""AI-related job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.encryption import decrypt_value

logger = logging.getLogger(__name__)


async def process_ai_chat(db, job) -> None:
    """Process AI chat job."""
    from app.services import ai_chat_service, oauth_service

    payload = job.payload or {}
    message_encrypted = payload.get("message_encrypted")
    entity_type = payload.get("entity_type") or "global"
    entity_id = payload.get("entity_id")
    user_id = payload.get("user_id")

    if not message_encrypted or not user_id:
        raise Exception("Missing message_encrypted or user_id in job payload")

    message = decrypt_value(message_encrypted)
    user_uuid = UUID(user_id)
    entity_uuid = UUID(entity_id) if entity_id else user_uuid

    integrations = oauth_service.get_user_integrations(db, user_uuid)
    user_integrations = [i.integration_type for i in integrations]

    result = await ai_chat_service.chat_async(
        db=db,
        organization_id=job.organization_id,
        user_id=user_uuid,
        entity_type=entity_type,
        entity_id=entity_uuid,
        message=message,
        user_integrations=user_integrations,
    )

    payload["result"] = result
    payload.pop("message_encrypted", None)
    payload.pop("message", None)
    job.payload = payload
    db.commit()
