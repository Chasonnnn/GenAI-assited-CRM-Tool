"""Attachment job handlers."""

from __future__ import annotations

from uuid import UUID


async def process_attachment_scan(db, job) -> None:
    """Process attachment scan job."""
    attachment_id = job.payload.get("attachment_id")
    if not attachment_id:
        raise Exception("Missing attachment_id in job payload")
    from app.jobs.scan_attachment import scan_attachment_job

    scan_attachment_job(UUID(attachment_id))
