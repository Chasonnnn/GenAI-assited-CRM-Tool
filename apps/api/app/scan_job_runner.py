"""On-demand Cloud Run job entrypoint for malware scanning."""

from __future__ import annotations

import argparse
import logging
from uuid import UUID

from app.db.enums import JobStatus, JobType
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
    parser.add_argument("--claim-token")
    return parser.parse_args()


def _prepare_scanner() -> None:
    clamav_signature_service.ensure_signatures()
    scanner = get_available_scanner()
    if not scanner:
        raise RuntimeError("No ClamAV scanner found in PATH")
    logger.info("Dedicated scan job ready using %s", scanner)


def _scan_contract(scan_type: str) -> tuple[str, str]:
    if scan_type == "attachment":
        return JobType.ATTACHMENT_SCAN.value, "attachment_id"
    if scan_type == "form_submission_file":
        return JobType.FORM_SUBMISSION_FILE_SCAN.value, "submission_file_id"
    raise ValueError(f"Unsupported scan type: {scan_type}")


def _require_current_claim(
    *,
    job,
    scan_type: str,
    resource_id: UUID,
    claim_token: UUID | None,
) -> None:
    expected_job_type, resource_key = _scan_contract(scan_type)
    token_matches = (
        job.claim_token is None
        if claim_token is None
        else job.claim_token is not None and job.claim_token == claim_token
    )
    if (
        job.status != JobStatus.RUNNING.value
        or job.job_type != expected_job_type
        or (job.payload or {}).get(resource_key) != str(resource_id)
        or not token_matches
    ):
        raise job_service.JobClaimLost("job claim is no longer current")


def run_scan_job(
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
    claim_token: UUID | None = None,
) -> int:
    db = SessionLocal()
    try:
        job = job_service.get_job(db, job_id)
        if job is None:
            raise job_service.JobClaimLost("job claim is no longer current")
        _require_current_claim(
            job=job,
            scan_type=scan_type,
            resource_id=resource_id,
            claim_token=claim_token,
        )

        _prepare_scanner()

        if scan_type == "attachment":
            success = scan_attachment_job(resource_id)
        else:
            success = scan_form_submission_file_job(resource_id)

        if success:
            job_service.complete_claimed_job(
                db,
                job_id=job.id,
                claim_token=claim_token,
            )
            return 0

        error = f"{scan_type} scan did not complete successfully"
        job_service.fail_claimed_job(
            db,
            job_id=job.id,
            claim_token=claim_token,
            error=error,
        )
        return 1
    finally:
        db.close()


def main() -> int:
    args = _parse_args()
    return run_scan_job(
        scan_type=args.scan_type,
        resource_id=UUID(args.resource_id),
        job_id=UUID(args.job_id),
        claim_token=UUID(args.claim_token) if args.claim_token else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
