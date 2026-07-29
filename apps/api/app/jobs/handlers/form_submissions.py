"""Form submission job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_form_submission_file_scan(db, job) -> bool:
    """Process form submission file scan job."""
    file_id = job.payload.get("submission_file_id")
    if not file_id:
        raise Exception("Missing submission_file_id in job payload")
    from app.services import scan_dispatch_service

    file_uuid = UUID(file_id)
    if scan_dispatch_service.remote_scan_dispatch_configured():
        if job.claim_token is None:
            raise RuntimeError("Form submission scan job is missing claim identity")
        try:
            await scan_dispatch_service.dispatch_form_submission_file_scan_job(
                job_id=job.id,
                submission_file_id=file_uuid,
                claim_token=job.claim_token,
            )
        except scan_dispatch_service.ScanDispatchAmbiguousError:
            logger.warning(
                "Form submission scan dispatch outcome is unknown; preserving claim job_id=%s",
                job.id,
            )
        return False

    from app.jobs.scan_attachment import scan_form_submission_file_job

    scan_form_submission_file_job(file_uuid)
    return True
