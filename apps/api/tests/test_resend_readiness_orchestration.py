"""Public API and worker contracts for durable Resend readiness checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.enums import JobStatus, JobType
from app.db.models import Job, Organization
from app.db.session import SessionLocal
from app.services import job_service


@pytest.mark.asyncio
async def test_organization_readiness_check_queues_one_scoped_job(
    authed_client,
    db,
    test_org,
):
    response = await authed_client.post("/email-operations/readiness/check")

    assert response.status_code == 202
    assert response.json()["check_status"] == "queued"
    jobs = (
        db.query(Job)
        .filter(
            Job.job_type == "resend_readiness_check",
            Job.organization_id == test_org.id,
        )
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].job_scope == "organization"
    assert jobs[0].payload == {"provider_scope": "organization"}


@pytest.mark.asyncio
async def test_duplicate_organization_readiness_checks_coalesce(
    authed_client,
    db,
    test_org,
):
    first = await authed_client.post("/email-operations/readiness/check")
    second = await authed_client.post("/email-operations/readiness/check")

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["check_status"] == "queued"
    assert (
        db.query(Job)
        .filter(
            Job.job_type == "resend_readiness_check",
            Job.organization_id == test_org.id,
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_completed_readiness_check_does_not_block_a_future_check(
    authed_client,
    db,
    test_org,
):
    first = await authed_client.post("/email-operations/readiness/check")
    first_job = (
        db.query(Job)
        .filter(
            Job.job_type == JobType.RESEND_READINESS_CHECK.value,
            Job.organization_id == test_org.id,
        )
        .one()
    )
    job_service.mark_job_running(db, first_job)
    job_service.mark_job_completed(db, first_job)

    second = await authed_client.post("/email-operations/readiness/check")

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["check_status"] == "queued"
    assert (
        db.query(Job)
        .filter(
            Job.job_type == JobType.RESEND_READINESS_CHECK.value,
            Job.organization_id == test_org.id,
        )
        .count()
        == 2
    )


@pytest.mark.asyncio
async def test_organization_live_readiness_get_is_cache_only(
    authed_client,
    monkeypatch,
):
    from app.services import resend_control_plane

    monkeypatch.setattr(
        resend_control_plane,
        "ResendControlPlaneClient",
        lambda **_kwargs: pytest.fail("cache-only GET attempted provider I/O"),
    )

    response = await authed_client.get("/email-operations/readiness/live")

    assert response.status_code == 200
    assert response.json() == {
        "check_status": "idle",
        "last_snapshot": {
            "freshness": "never_checked",
            "probe_status": None,
            "overall_status": "unknown",
            "domain_status": "unknown",
            "webhook_status": "unknown",
            "sending_status": "unknown",
            "delivery_tracking_status": "unknown",
            "engagement_tracking_status": "unknown",
            "verified_domain_count": 0,
            "enabled_webhook_count": 0,
            "issue_codes": [],
            "checked_at": None,
            "last_success_at": None,
        },
    }


@pytest.mark.asyncio
async def test_platform_readiness_check_queues_one_platform_job(
    authed_client,
    db,
    test_user,
):
    forbidden = await authed_client.post("/platform/email/readiness/check")
    assert forbidden.status_code == 403

    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post("/platform/email/readiness/check")

    assert response.status_code == 202
    assert response.json()["check_status"] == "queued"
    jobs = (
        db.query(Job)
        .filter(
            Job.job_type == "resend_readiness_check",
            Job.job_scope == "platform",
        )
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].organization_id is None
    assert jobs[0].payload == {"provider_scope": "platform"}


@pytest.mark.asyncio
async def test_worker_executes_organization_readiness_check(
    db,
    test_org,
    monkeypatch,
):
    from app import worker
    from app.services import resend_readiness_service

    calls = []

    async def _refresh(session, *, organization_id):
        calls.append((session, organization_id))
        return resend_readiness_service.ReadinessRefreshResult(
            probe=None,
            persisted=True,
        )

    monkeypatch.setattr(
        resend_readiness_service,
        "refresh_organization_readiness",
        _refresh,
    )
    job = job_service.enqueue_job(
        db,
        org_id=test_org.id,
        job_type=JobType.RESEND_READINESS_CHECK,
        payload={"provider_scope": "organization"},
    )

    completed = await worker.process_job(db, job)

    assert completed is True
    assert calls == [(db, test_org.id)]


def test_simultaneous_organization_readiness_checks_coalesce(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Advisory-lock concurrency requires PostgreSQL")

    from app.services import resend_readiness_orchestration_service

    organization_id = uuid4()
    setup_session = SessionLocal()
    cleanup_session = SessionLocal()
    barrier = Barrier(2)
    try:
        setup_session.add(
            Organization(
                id=organization_id,
                name="Concurrent readiness",
                slug=f"concurrent-readiness-{uuid4().hex[:8]}",
            )
        )
        setup_session.commit()

        def _queue() -> str:
            with SessionLocal() as session:
                barrier.wait()
                return resend_readiness_orchestration_service.queue_organization_check(
                    session,
                    organization_id=organization_id,
                ).check_status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _index: _queue(), range(2)))

        jobs = (
            cleanup_session.query(Job)
            .filter(
                Job.job_type == JobType.RESEND_READINESS_CHECK.value,
                Job.organization_id == organization_id,
                Job.status == JobStatus.PENDING.value,
            )
            .all()
        )
        assert statuses == ["queued", "queued"]
        assert len(jobs) == 1
    finally:
        setup_session.close()
        cleanup_session.query(Job).filter(Job.organization_id == organization_id).delete(
            synchronize_session=False
        )
        cleanup_session.query(Organization).filter(Organization.id == organization_id).delete(
            synchronize_session=False
        )
        cleanup_session.commit()
        cleanup_session.close()


@pytest.mark.asyncio
async def test_worker_keeps_provider_retry_after_internal_and_schedules_retry(
    db,
    test_org,
    monkeypatch,
):
    from app import worker
    from app.services import resend_readiness_service

    async def _refresh(_session, *, organization_id):
        assert organization_id == test_org.id
        return resend_readiness_service.ReadinessRefreshResult(
            probe=None,
            persisted=True,
            retry_after_seconds=73,
        )

    monkeypatch.setattr(
        resend_readiness_service,
        "refresh_organization_readiness",
        _refresh,
    )
    job = job_service.enqueue_job(
        db,
        org_id=test_org.id,
        job_type=JobType.RESEND_READINESS_CHECK,
        payload={"provider_scope": "organization"},
    )
    job_service.mark_job_running(db, job)
    before = datetime.now(timezone.utc)

    with pytest.raises(RuntimeError, match="Resend readiness retry requested") as exc_info:
        await worker.process_job(db, job)
    job_service.mark_job_failed(db, job, str(exc_info.value))

    db.refresh(job)
    assert job.status == JobStatus.PENDING.value
    assert before + timedelta(seconds=72) <= job.run_at <= before + timedelta(seconds=75)
    assert job.last_error == "Resend readiness retry requested"
    assert "73" not in job.last_error


@pytest.mark.asyncio
async def test_live_readiness_get_projects_queued_running_and_idle(
    authed_client,
    db,
    test_org,
):
    job = job_service.enqueue_job(
        db,
        org_id=test_org.id,
        job_type=JobType.RESEND_READINESS_CHECK,
        payload={"provider_scope": "organization"},
    )

    queued = await authed_client.get("/email-operations/readiness/live")
    job_service.mark_job_running(db, job)
    running = await authed_client.get("/email-operations/readiness/live")
    job_service.mark_job_completed(db, job)
    idle = await authed_client.get("/email-operations/readiness/live")

    assert queued.json()["check_status"] == "queued"
    assert running.json()["check_status"] == "running"
    assert idle.json()["check_status"] == "idle"


@pytest.mark.asyncio
async def test_platform_readiness_get_is_admin_only_and_cache_only(
    authed_client,
    db,
    test_user,
    monkeypatch,
):
    from app.services import resend_control_plane

    forbidden = await authed_client.get("/platform/email/readiness")
    assert forbidden.status_code == 403

    test_user.is_platform_admin = True
    db.commit()
    monkeypatch.setattr(
        resend_control_plane,
        "ResendControlPlaneClient",
        lambda **_kwargs: pytest.fail("cache-only GET attempted provider I/O"),
    )

    response = await authed_client.get("/platform/email/readiness")

    assert response.status_code == 200
    assert response.json()["check_status"] == "idle"
    assert response.json()["last_snapshot"]["freshness"] == "never_checked"


@pytest.mark.asyncio
async def test_organization_readiness_check_requires_manage_integrations(
    authed_client,
    db,
    monkeypatch,
):
    from app.services import permission_service

    monkeypatch.setattr(permission_service, "check_permission", lambda *_args, **_kwargs: False)

    response = await authed_client.post("/email-operations/readiness/check")

    assert response.status_code == 403
    assert db.query(Job).filter(Job.job_type == JobType.RESEND_READINESS_CHECK.value).count() == 0


@pytest.mark.asyncio
async def test_readiness_check_mutations_require_csrf(
    authed_client,
    db,
    test_user,
):
    from app.core.csrf import CSRF_HEADER

    authed_client.headers.pop(CSRF_HEADER)
    organization_response = await authed_client.post("/email-operations/readiness/check")

    test_user.is_platform_admin = True
    db.commit()
    platform_response = await authed_client.post("/platform/email/readiness/check")

    assert organization_response.status_code == 403
    assert platform_response.status_code == 403
    assert db.query(Job).filter(Job.job_type == JobType.RESEND_READINESS_CHECK.value).count() == 0


@pytest.mark.asyncio
async def test_worker_executes_platform_readiness_check(
    db,
    monkeypatch,
):
    from app import worker
    from app.services import resend_readiness_service

    calls = []

    async def _refresh(session):
        calls.append(session)
        return resend_readiness_service.ReadinessRefreshResult(
            probe=None,
            persisted=True,
        )

    monkeypatch.setattr(
        resend_readiness_service,
        "refresh_platform_readiness",
        _refresh,
    )
    job = job_service.enqueue_platform_job(
        db,
        job_type=JobType.RESEND_READINESS_CHECK,
        payload={"provider_scope": "platform"},
    )

    completed = await worker.process_job(db, job)

    assert completed is True
    assert calls == [db]


@pytest.mark.asyncio
async def test_completed_worker_result_is_returned_from_cache_only_get(
    authed_client,
    db,
    test_org,
):
    from app import worker

    queued = await authed_client.post("/email-operations/readiness/check")
    job = (
        db.query(Job)
        .filter(
            Job.job_type == JobType.RESEND_READINESS_CHECK.value,
            Job.organization_id == test_org.id,
        )
        .one()
    )
    job_service.mark_job_running(db, job)
    completed = await worker.process_job(db, job)
    job_service.mark_job_completed(db, job)

    response = await authed_client.get("/email-operations/readiness/live")

    assert queued.status_code == 202
    assert completed is True
    assert response.status_code == 200
    assert response.json()["check_status"] == "idle"
    snapshot = response.json()["last_snapshot"]
    assert {
        key: snapshot[key]
        for key in (
            "freshness",
            "probe_status",
            "overall_status",
            "domain_status",
            "webhook_status",
            "sending_status",
            "delivery_tracking_status",
            "engagement_tracking_status",
            "verified_domain_count",
            "enabled_webhook_count",
            "issue_codes",
        )
    } == {
        "freshness": "fresh",
        "probe_status": "succeeded",
        "overall_status": "not_configured",
        "domain_status": "not_configured",
        "webhook_status": "not_configured",
        "sending_status": "not_configured",
        "delivery_tracking_status": "not_configured",
        "engagement_tracking_status": "not_configured",
        "verified_domain_count": 0,
        "enabled_webhook_count": 0,
        "issue_codes": [],
    }
    assert snapshot["checked_at"] is not None
    assert snapshot["last_success_at"] is not None
    assert {
        "config_fingerprint",
        "provider_account_id",
        "organization_id",
        "api_key",
        "webhook_endpoint",
        "retry_after_seconds",
    }.isdisjoint(snapshot)


@pytest.mark.asyncio
async def test_worker_rejects_incoherent_readiness_job_scope(
    db,
    test_org,
    monkeypatch,
):
    from app import worker
    from app.services import resend_readiness_service

    organization_calls = []
    platform_calls = []
    monkeypatch.setattr(
        resend_readiness_service,
        "refresh_organization_readiness",
        lambda *_args, **_kwargs: organization_calls.append(True),
    )
    monkeypatch.setattr(
        resend_readiness_service,
        "refresh_platform_readiness",
        lambda *_args, **_kwargs: platform_calls.append(True),
    )
    job = job_service.enqueue_job(
        db,
        org_id=test_org.id,
        job_type=JobType.RESEND_READINESS_CHECK,
        payload={"provider_scope": "platform"},
    )

    with pytest.raises(ValueError, match="Invalid Resend readiness job scope"):
        await worker.process_job(db, job)

    assert organization_calls == []
    assert platform_calls == []
