"""Dispatch malware scan work to a dedicated Cloud Run job."""

from __future__ import annotations

import logging
import os
from uuid import UUID

import google.auth
from google.auth.transport.requests import Request
import httpx

from app.core.config import settings
from app.services.http_service import DEFAULT_RETRY_STATUSES, request_with_retries


logger = logging.getLogger(__name__)

SCAN_JOB_TIMEOUT_SECONDS = 300.0
RUN_API_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


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


def _run_payload(*, scan_type: str, resource_id: UUID, job_id: UUID) -> dict[str, object]:
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
                    ]
                }
            ],
            "taskCount": 1,
            "timeout": "600s",
        }
    }


async def _dispatch_scan_job(*, scan_type: str, resource_id: UUID, job_id: UUID) -> None:
    token = _access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = _run_payload(scan_type=scan_type, resource_id=resource_id, job_id=job_id)

    async with httpx.AsyncClient(timeout=SCAN_JOB_TIMEOUT_SECONDS) as client:

        async def request_fn() -> httpx.Response:
            return await client.post(_run_job_url(), headers=headers, json=payload)

        response = await request_with_retries(
            request_fn,
            max_attempts=3,
            base_delay=0.5,
            max_delay=4.0,
            retry_statuses=DEFAULT_RETRY_STATUSES,
        )

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


async def dispatch_attachment_scan_job(*, job_id: UUID, attachment_id: UUID) -> None:
    await _dispatch_scan_job(
        scan_type="attachment",
        resource_id=attachment_id,
        job_id=job_id,
    )


async def dispatch_form_submission_file_scan_job(*, job_id: UUID, submission_file_id: UUID) -> None:
    await _dispatch_scan_job(
        scan_type="form_submission_file",
        resource_id=submission_file_id,
        job_id=job_id,
    )
