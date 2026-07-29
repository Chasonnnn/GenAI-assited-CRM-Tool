"""Dispatch malware scan work to a dedicated Cloud Run job."""

from __future__ import annotations

import logging
import os
from uuid import UUID

import google.auth
import httpx
from google.auth.transport.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)

SCAN_JOB_TIMEOUT_SECONDS = 300.0
SCAN_EXECUTION_TIMEOUT_SECONDS = 600
SCAN_STALE_LEASE_MARGIN_SECONDS = 60
RUN_API_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class ScanDispatchAmbiguousError(RuntimeError):
    """Cloud Run may have accepted the execution, so the claim must stay fenced."""


def _dispatch_outcome_is_ambiguous(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500


def scan_stale_lease_seconds() -> int:
    """Keep stale recovery beyond the longest accepted Cloud Run execution."""
    configured = max(0, settings.ATTACHMENT_SCAN_STALE_RUNNING_SECONDS)
    return max(
        configured,
        SCAN_EXECUTION_TIMEOUT_SECONDS + SCAN_STALE_LEASE_MARGIN_SECONDS,
    )


def _scan_job_name() -> str:
    return (settings.ATTACHMENT_SCAN_CLOUD_RUN_JOB_NAME or "").strip()


def _scan_job_region() -> str:
    return (
        (settings.ATTACHMENT_SCAN_CLOUD_RUN_REGION or "").strip()
        or os.getenv("GOOGLE_CLOUD_REGION", "").strip()
        or os.getenv("REGION", "").strip()
    )


def remote_scan_dispatch_configured() -> bool:
    return bool(settings.gcp_project_id and _scan_job_name() and _scan_job_region())


def _job_resource_name() -> str:
    if not remote_scan_dispatch_configured():
        raise RuntimeError(
            "Dedicated scan job is not configured. Set GCP_PROJECT_ID, "
            "ATTACHMENT_SCAN_CLOUD_RUN_JOB_NAME, and ATTACHMENT_SCAN_CLOUD_RUN_REGION."
        )
    return (
        f"projects/{settings.gcp_project_id}/locations/{_scan_job_region()}/jobs/{_scan_job_name()}"
    )


def _run_job_url() -> str:
    return f"https://run.googleapis.com/v2/{_job_resource_name()}:run"


def _access_token() -> str:
    credentials, _project = google.auth.default(scopes=[RUN_API_SCOPE])
    credentials.refresh(Request())
    token = getattr(credentials, "token", None)
    if not token:
        raise RuntimeError("Failed to acquire access token for Cloud Run job execution")
    return str(token)


def _run_payload(
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
    claim_token: UUID,
) -> dict[str, object]:
    return {
        "overrides": {
            "containerOverrides": [
                {
                    "args": [
                        "--scan-type",
                        scan_type,
                        "--resource-id",
                        str(resource_id),
                        "--job-id",
                        str(job_id),
                        "--claim-token",
                        str(claim_token),
                    ]
                }
            ],
            "taskCount": 1,
            "timeout": f"{SCAN_EXECUTION_TIMEOUT_SECONDS}s",
        }
    }


async def _dispatch_scan_job(
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
    claim_token: UUID,
) -> None:
    token = _access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = _run_payload(
        scan_type=scan_type,
        resource_id=resource_id,
        job_id=job_id,
        claim_token=claim_token,
    )

    try:
        async with httpx.AsyncClient(timeout=SCAN_JOB_TIMEOUT_SECONDS) as client:
            response = await client.post(_run_job_url(), headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise ScanDispatchAmbiguousError("Dedicated scan job dispatch outcome is unknown") from exc

    if 200 <= response.status_code < 300:
        logger.info(
            "Dispatched dedicated scan job type=%s resource_id=%s db_job_id=%s",
            scan_type,
            resource_id,
            job_id,
        )
        return

    if _dispatch_outcome_is_ambiguous(response.status_code):
        raise ScanDispatchAmbiguousError(
            f"Dedicated scan job dispatch outcome is unknown ({response.status_code})"
        )

    detail = None
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("message") or data.get("error")
    except Exception:
        detail = None

    if detail:
        raise RuntimeError(f"Dedicated scan job dispatch failed: {response.status_code} ({detail})")
    raise RuntimeError(f"Dedicated scan job dispatch failed: {response.status_code}")


def _raise_for_dispatch_response(
    response: httpx.Response,
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
) -> None:
    if 200 <= response.status_code < 300:
        logger.info(
            "Dispatched dedicated scan job type=%s resource_id=%s db_job_id=%s",
            scan_type,
            resource_id,
            job_id,
        )
        return

    detail = None
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("message") or data.get("error")
    except Exception:
        detail = None

    if detail:
        raise RuntimeError(f"Dedicated scan job dispatch failed: {response.status_code} ({detail})")
    raise RuntimeError(f"Dedicated scan job dispatch failed: {response.status_code}")


def _dispatch_scan_job_sync(
    *,
    scan_type: str,
    resource_id: UUID,
    job_id: UUID,
    claim_token: UUID,
) -> None:
    token = _access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = _run_payload(
        scan_type=scan_type,
        resource_id=resource_id,
        job_id=job_id,
        claim_token=claim_token,
    )

    try:
        with httpx.Client(timeout=SCAN_JOB_TIMEOUT_SECONDS) as client:
            response = client.post(_run_job_url(), headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise ScanDispatchAmbiguousError("Dedicated scan job dispatch outcome is unknown") from exc

    if _dispatch_outcome_is_ambiguous(response.status_code):
        raise ScanDispatchAmbiguousError(
            f"Dedicated scan job dispatch outcome is unknown ({response.status_code})"
        )

    _raise_for_dispatch_response(
        response,
        scan_type=scan_type,
        resource_id=resource_id,
        job_id=job_id,
    )


async def dispatch_attachment_scan_job(
    *,
    job_id: UUID,
    attachment_id: UUID,
    claim_token: UUID,
) -> None:
    await _dispatch_scan_job(
        scan_type="attachment",
        resource_id=attachment_id,
        job_id=job_id,
        claim_token=claim_token,
    )


async def dispatch_form_submission_file_scan_job(
    *,
    job_id: UUID,
    submission_file_id: UUID,
    claim_token: UUID,
) -> None:
    await _dispatch_scan_job(
        scan_type="form_submission_file",
        resource_id=submission_file_id,
        job_id=job_id,
        claim_token=claim_token,
    )


def dispatch_attachment_scan_job_sync(
    *,
    job_id: UUID,
    attachment_id: UUID,
    claim_token: UUID,
) -> None:
    _dispatch_scan_job_sync(
        scan_type="attachment",
        resource_id=attachment_id,
        job_id=job_id,
        claim_token=claim_token,
    )


def dispatch_form_submission_file_scan_job_sync(
    *,
    job_id: UUID,
    submission_file_id: UUID,
    claim_token: UUID,
) -> None:
    _dispatch_scan_job_sync(
        scan_type="form_submission_file",
        resource_id=submission_file_id,
        job_id=job_id,
        claim_token=claim_token,
    )
