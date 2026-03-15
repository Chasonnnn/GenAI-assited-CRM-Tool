"""Attachment job handlers."""

from __future__ import annotations

from uuid import UUID


async def process_attachment_scan(db, job) -> bool:
    """Process attachment scan job."""
    attachment_id = job.payload.get("attachment_id")
    if not attachment_id:
        raise Exception("Missing attachment_id in job payload")
    from app.services import scan_dispatch_service

    attachment_uuid = UUID(attachment_id)
    if scan_dispatch_service.remote_scan_dispatch_configured():
        await scan_dispatch_service.dispatch_attachment_scan_job(
            job_id=job.id,
            attachment_id=attachment_uuid,
        )
        return False

    from app.jobs.scan_attachment import scan_attachment_job

    scan_attachment_job(attachment_uuid)
    return True
