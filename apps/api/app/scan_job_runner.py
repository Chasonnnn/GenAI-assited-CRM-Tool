"""On-demand Cloud Run job entrypoint for malware scanning."""

from __future__ import annotations

import argparse
import logging
from uuid import UUID

from app.db.session import SessionLocal
from app.services import clamav_signature_service, job_service
from app.jobs.scan_attachment import (
    get_available_scanner,
    scan_attachment_job,
    scan_form_submission_file_job,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a dedicated malware scan job")
    parser.add_argument(
        "--scan-type", choices=["attachment", "form_submission_file"], required=True
    )
    parser.add_argument("--resource-id", required=True)
    parser.add_argument("--job-id", required=True)
    return parser.parse_args()


def _prepare_scanner() -> None:
    clamav_signature_service.ensure_signatures()
    scanner = get_available_scanner()
    if not scanner:
        raise RuntimeError("No ClamAV scanner found in PATH")
    logger.info("Dedicated scan job ready using %s", scanner)


def run_scan_job(*, scan_type: str, resource_id: UUID, job_id: UUID) -> int:
    _prepare_scanner()

    if scan_type == "attachment":
        success = scan_attachment_job(resource_id)
    elif scan_type == "form_submission_file":
        success = scan_form_submission_file_job(resource_id)
    else:  # pragma: no cover - argparse guards this
        raise ValueError(f"Unsupported scan type: {scan_type}")

    db = SessionLocal()
    try:
        job = job_service.get_job(db, job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} not found")

        if success:
            job_service.mark_job_completed(db, job)
            return 0

        job_service.mark_job_failed(db, job, f"{scan_type} scan did not complete successfully")
        return 1
    finally:
        db.close()


def main() -> int:
    args = _parse_args()
    return run_scan_job(
        scan_type=args.scan_type,
        resource_id=UUID(args.resource_id),
        job_id=UUID(args.job_id),
    )


if __name__ == "__main__":
    raise SystemExit(main())
