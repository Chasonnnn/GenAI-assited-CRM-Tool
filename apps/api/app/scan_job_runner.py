"""On-demand Cloud Run job entrypoint for malware scanning."""

from __future__ import annotations

import argparse
import hashlib
import logging
from uuid import UUID

from sqlalchemy import select, text

from app.db.enums import JobStatus, JobType
from app.db.models import Attachment, FormSubmissionFile, Job, MessageMediaAsset
from app.db.session import SessionLocal
from app.jobs.scan_attachment import (
    get_available_scanner,
    scan_attachment_job,
    scan_form_submission_file_job,
    scan_message_media_asset_job,
)
from app.services import clamav_signature_service, job_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a dedicated malware scan job")
    parser.add_argument(
        "--scan-type",
        choices=["attachment", "form_submission_file", "message_media"],
        required=True,
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
    if scan_type == "message_media":
        return JobType.MESSAGE_MEDIA_SCAN.value, "media_asset_id"
    raise ValueError(f"Unsupported scan type: {scan_type}")


def _scan_model(scan_type: str):
    if scan_type == "attachment":
        return Attachment
    if scan_type == "form_submission_file":
        return FormSubmissionFile
    if scan_type == "message_media":
        return MessageMediaAsset
    raise ValueError(f"Unsupported scan type: {scan_type}")


def _terminal_scan_statuses(scan_type: str) -> frozenset[str]:
    if scan_type == "message_media":
        return frozenset({"clean", "quarantined", "rejected"})
    return frozenset({"clean", "infected", "error"})


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


def _lock_job(db, job_id: UUID) -> Job | None:
    return db.execute(
        select(Job)
        .where(Job.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _resource_scan_status(
    db,
    *,
    scan_type: str,
    resource_id: UUID,
    organization_id: UUID,
) -> str | None:
    model = _scan_model(scan_type)
    return db.execute(
        select(model.scan_status).where(
            model.id == resource_id,
            model.organization_id == organization_id,
        )
    ).scalar_one_or_none()


def _lock_scan_resource(db, *, scan_type: str, resource_id: UUID) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(
        f"scan-resource:{scan_type}:{resource_id}".encode(),
        digest_size=8,
    ).digest()
    lock_key = int.from_bytes(digest, byteorder="big", signed=True)
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key},
    )


def _lock_current_claim_and_resource(
    db,
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
    claim_token: UUID | None,
) -> tuple[Job, str | None]:
    job = _lock_job(db, job_id)
    if job is None:
        raise job_service.JobClaimLost("job claim is no longer current")
    _require_current_claim(
        job=job,
        scan_type=scan_type,
        resource_id=resource_id,
        claim_token=claim_token,
    )
    _lock_scan_resource(db, scan_type=scan_type, resource_id=resource_id)
    return job, _resource_scan_status(
        db,
        scan_type=scan_type,
        resource_id=resource_id,
        organization_id=job.organization_id,
    )


def _fail_missing_or_cross_org_resource(
    db,
    *,
    job: Job,
    claim_token: UUID | None,
    scan_type: str,
) -> int:
    job_service.fail_claimed_job(
        db,
        job_id=job.id,
        claim_token=claim_token,
        error=f"{scan_type} scan resource was not found in the job organization",
    )
    return 1


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

        initial_status = _resource_scan_status(
            db,
            scan_type=scan_type,
            resource_id=resource_id,
            organization_id=job.organization_id,
        )
        terminal_statuses = _terminal_scan_statuses(scan_type)
        if initial_status not in {*terminal_statuses, None}:
            _prepare_scanner()

        job, resource_status = _lock_current_claim_and_resource(
            db,
            scan_type=scan_type,
            resource_id=resource_id,
            job_id=job_id,
            claim_token=claim_token,
        )
        if resource_status is None:
            return _fail_missing_or_cross_org_resource(
                db,
                job=job,
                claim_token=claim_token,
                scan_type=scan_type,
            )
        if resource_status in terminal_statuses:
            job_service.complete_claimed_job(
                db,
                job_id=job.id,
                claim_token=claim_token,
            )
            return 0

        if scan_type == "attachment":
            success = scan_attachment_job(resource_id)
        elif scan_type == "form_submission_file":
            success = scan_form_submission_file_job(resource_id)
        else:
            success = scan_message_media_asset_job(resource_id)

        resource_is_terminal = _resource_scan_status(
            db,
            scan_type=scan_type,
            resource_id=resource_id,
            organization_id=job.organization_id,
        ) in terminal_statuses
        if success or resource_is_terminal:
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
