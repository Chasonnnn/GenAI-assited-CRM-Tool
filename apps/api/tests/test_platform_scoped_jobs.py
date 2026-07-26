"""Contract tests for organization- and platform-scoped background jobs."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.db.enums import JobScope, JobStatus, JobType
from app.db.models import Job
from app.services import job_service


def test_platform_job_enqueues_without_an_organization(db):
    job = job_service.enqueue_platform_job(
        db=db,
        job_type=JobType.NOTIFICATION,
        payload={"operation": "readiness_check"},
    )

    assert job.job_scope == "platform"
    assert job.organization_id is None


def test_existing_enqueue_callers_remain_organization_scoped(db, test_org):
    job = job_service.enqueue_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.NOTIFICATION,
        payload={"operation": "tenant_notification"},
    )

    assert job.job_scope == "organization"
    assert job.organization_id == test_org.id


def test_database_rejects_incoherent_job_scope_and_organization(db, test_org):
    invalid_jobs = [
        Job(
            job_scope=JobScope.PLATFORM.value,
            organization_id=test_org.id,
            job_type=JobType.NOTIFICATION.value,
            payload={},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        ),
        Job(
            job_scope=JobScope.ORGANIZATION.value,
            organization_id=None,
            job_type=JobType.NOTIFICATION.value,
            payload={},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        ),
    ]

    for invalid_job in invalid_jobs:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(invalid_job)
                db.flush()


def test_tenant_job_queries_cannot_see_or_replay_platform_jobs(db, test_org):
    platform_job = job_service.enqueue_platform_job(
        db=db,
        job_type=JobType.NOTIFICATION,
        payload={"operation": "readiness_check"},
        idempotency_key="platform-readiness-query-boundary",
    )
    platform_job.status = JobStatus.FAILED.value
    platform_job.attempts = platform_job.max_attempts
    platform_job.last_error = "control_plane_unavailable"
    db.commit()

    assert job_service.get_job(db, platform_job.id, org_id=test_org.id) is None
    assert (
        job_service.get_job_by_idempotency_key(
            db,
            org_id=test_org.id,
            idempotency_key="platform-readiness-query-boundary",
        )
        is None
    )
    assert platform_job.id not in {job.id for job in job_service.list_jobs(db, org_id=test_org.id)}
    assert platform_job.id not in {
        job.id for job in job_service.list_dead_letter_jobs(db, org_id=test_org.id)
    }
    with pytest.raises(ValueError, match="Job not found"):
        job_service.replay_failed_job(
            db,
            org_id=test_org.id,
            job_id=platform_job.id,
        )


@pytest.mark.asyncio
async def test_tenant_job_api_hides_platform_jobs(
    authed_client: AsyncClient,
    db,
):
    platform_job = job_service.enqueue_platform_job(
        db=db,
        job_type=JobType.NOTIFICATION,
        payload={"operation": "readiness_check"},
    )
    platform_job.status = JobStatus.FAILED.value
    platform_job.attempts = platform_job.max_attempts
    platform_job.last_error = "control_plane_unavailable"
    db.commit()

    jobs = await authed_client.get("/jobs")
    assert jobs.status_code == 200
    assert str(platform_job.id) not in {item["id"] for item in jobs.json()}

    dead_letters = await authed_client.get("/jobs/dlq")
    assert dead_letters.status_code == 200
    assert str(platform_job.id) not in {item["id"] for item in dead_letters.json()}

    detail = await authed_client.get(f"/jobs/{platform_job.id}")
    assert detail.status_code == 404

    replay = await authed_client.post(
        f"/jobs/{platform_job.id}/replay",
        json={"reason": "must remain platform-owned"},
    )
    assert replay.status_code == 404
