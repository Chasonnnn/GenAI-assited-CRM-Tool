"""Outbound messaging media scan job handler."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_message_media_scan(db, job) -> bool:
    """Dispatch or locally execute one durable outbound media scan."""
    asset_id = (job.payload or {}).get("media_asset_id")
    if not asset_id:
        raise ValueError("Missing media_asset_id in job payload")
    asset_uuid = UUID(asset_id)

    from app.services import scan_dispatch_service

    if scan_dispatch_service.remote_scan_dispatch_configured():
        if job.claim_token is None:
            raise RuntimeError("Messaging media scan job is missing claim identity")
        try:
            await scan_dispatch_service.dispatch_message_media_scan_job(
                job_id=job.id,
                media_asset_id=asset_uuid,
                claim_token=job.claim_token,
            )
        except scan_dispatch_service.ScanDispatchAmbiguousError:
            logger.warning(
                "Messaging media scan dispatch outcome is unknown; preserving claim job_id=%s",
                job.id,
            )
        return False

    from app.jobs.scan_attachment import scan_message_media_asset_job

    scan_message_media_asset_job(asset_uuid)
    return True
