"""Form submission job handlers."""

from __future__ import annotations

from uuid import UUID


async def process_form_submission_file_scan(db, job) -> None:
    """Process form submission file scan job."""
    file_id = job.payload.get("submission_file_id")
    if not file_id:
        raise Exception("Missing submission_file_id in job payload")
    from app.jobs.scan_attachment import scan_form_submission_file_job

    scan_form_submission_file_job(UUID(file_id))
