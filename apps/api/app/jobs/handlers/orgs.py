"""Organization job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_org_delete(db, job) -> None:
    """Permanently delete an organization after the grace period."""
    org_id = job.payload.get("org_id") if job.payload else None
    if not org_id:
        raise Exception("Missing org_id in org_delete payload")

    from app.services import platform_service

    deleted = platform_service.purge_organization(db, UUID(str(org_id)))
    if not deleted:
        logger.info("Org delete job no-op for org_id=%s (not due or already deleted)", org_id)
