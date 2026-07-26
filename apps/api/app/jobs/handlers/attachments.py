"""Attachment job handlers."""

from __future__ import annotations

import logging
from uuid import UUID


logger = logging.getLogger(__name__)


async def process_attachment_scan(db, job) -> bool:
    """Process attachment scan job."""
    attachment_id = job.payload.get("attachment_id")
    if not attachment_id:
        raise Exception("Missing attachment_id in job payload")
    from app.services import scan_dispatch_service

    attachment_uuid = UUID(attachment_id)
    if scan_dispatch_service.remote_scan_dispatch_configured():
        if job.claim_token is None:
            raise RuntimeError("Attachment scan job is missing claim identity")
        try:
            await scan_dispatch_service.dispatch_attachment_scan_job(
                job_id=job.id,
                attachment_id=attachment_uuid,
                claim_token=job.claim_token,
            )
        except scan_dispatch_service.ScanDispatchAmbiguousError:
            logger.warning(
                "Attachment scan dispatch outcome is unknown; preserving claim job_id=%s",
                job.id,
            )
        return False

    from app.jobs.scan_attachment import scan_attachment_job

    scan_attachment_job(attachment_uuid)
    return True
