from uuid import uuid4

import pytest

from app.db.enums import JobType


def test_job_registry_resolves_known_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.SEND_EMAIL.value)
    assert callable(handler)


def test_job_registry_resolves_google_calendar_sync_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.GOOGLE_CALENDAR_SYNC.value)
    assert callable(handler)


def test_job_registry_resolves_google_calendar_watch_refresh_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value)
    assert callable(handler)


def test_job_registry_resolves_google_tasks_sync_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.GOOGLE_TASKS_SYNC.value)
    assert callable(handler)


def test_job_registry_resolves_google_task_remote_delete_handler():
    from app.jobs.handlers.appointments import process_google_task_remote_delete
    from app.jobs.registry import resolve_job_handler

    assert (
        resolve_job_handler(JobType.GOOGLE_TASK_REMOTE_DELETE.value)
        is process_google_task_remote_delete
    )


def test_job_registry_resolves_google_task_creation_reconcile_handler():
    from app.jobs.handlers.appointments import process_google_task_creation_reconcile
    from app.jobs.registry import resolve_job_handler

    assert (
        resolve_job_handler(JobType.GOOGLE_TASK_CREATION_RECONCILE.value)
        is process_google_task_creation_reconcile
    )


def test_job_registry_resolves_ticket_outbound_send_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.TICKET_OUTBOUND_SEND.value)
    assert callable(handler)


def test_job_registry_unknown_raises():
    from app.jobs.registry import resolve_job_handler

    with pytest.raises(ValueError):
        resolve_job_handler("nope")


def test_job_registry_resolves_storage_delete_handler():
    from app.jobs.handlers.storage import process_storage_delete
    from app.jobs.registry import resolve_job_handler

    assert resolve_job_handler(JobType.STORAGE_DELETE.value) is process_storage_delete


@pytest.mark.asyncio
async def test_storage_delete_handler_is_retryable_and_org_scoped(monkeypatch):
    from app import worker
    from app.jobs.handlers import storage

    assert JobType.STORAGE_DELETE.value in worker.WORKER_STALE_CLAIM_RETRY_SAFE_JOB_TYPES

    org_id = uuid4()
    deleted: list[str] = []
    monkeypatch.setattr(storage.attachment_service, "delete_file", deleted.append)
    job = type(
        "Job",
        (),
        {
            "organization_id": org_id,
            "payload": {
                "storage_keys": [
                    f"{org_id}/donors/profile.png",
                    f"messaging/{org_id}/asset.png",
                ]
            },
        },
    )()

    await storage.process_storage_delete(None, job)

    assert deleted == job.payload["storage_keys"]

    job.payload = {"storage_keys": [f"{uuid4()}/donors/profile.png"]}
    with pytest.raises(ValueError, match="outside the job organization"):
        await storage.process_storage_delete(None, job)


@pytest.mark.asyncio
async def test_google_task_remote_delete_handler_is_idempotent_and_org_scoped(
    db,
    test_auth,
    monkeypatch,
):
    from app.jobs.handlers import appointments
    from app.services import google_tasks_sync_service

    async def access_token(*_args, **_kwargs):
        return "token"

    requests: list[tuple[str, str]] = []

    async def google_request(*, access_token, method, path, params=None, json_body=None):
        del access_token, params, json_body
        requests.append((method, path))
        return 404, None

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_access_token_async",
        access_token,
    )
    monkeypatch.setattr(google_tasks_sync_service, "_google_request", google_request)
    job = type(
        "Job",
        (),
        {
            "organization_id": test_auth.org.id,
            "payload": {
                "user_id": str(test_auth.user.id),
                "google_task_id": "remote/task",
                "google_task_list_id": "donor list",
            },
        },
    )()

    await appointments.process_google_task_remote_delete(db, job)

    assert requests == [("DELETE", "/lists/donor%20list/tasks/remote%2Ftask")]

    job.organization_id = uuid4()
    with pytest.raises(ValueError, match="outside the job organization"):
        await appointments.process_google_task_remote_delete(db, job)
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_google_task_remote_delete_persists_concrete_default_identity(
    db,
    test_auth,
    monkeypatch,
):
    from app.jobs.handlers import appointments
    from app.services import google_tasks_cleanup_service, google_tasks_sync_service

    job = google_tasks_cleanup_service.enqueue_remote_deletion(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        source_task_id=uuid4(),
        google_task_id="legacy-default-remote",
        google_task_list_id="@default",
    )
    db.commit()

    async def access_token(*_args, **_kwargs):
        return "token"

    requests: list[tuple[str, str]] = []

    async def google_request(
        *, access_token, method, path, params=None, json_body=None, max_attempts=3
    ):
        del access_token, params, json_body, max_attempts
        requests.append((method, path))
        if method == "GET":
            return 200, {"id": "concrete-default-list"}
        return 404, None

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_access_token_async",
        access_token,
    )
    monkeypatch.setattr(google_tasks_sync_service, "_google_request", google_request)

    await appointments.process_google_task_remote_delete(db, job)

    db.refresh(job)
    assert requests == [
        ("GET", "/users/@me/lists/%40default"),
        ("DELETE", "/lists/concrete-default-list/tasks/legacy-default-remote"),
    ]
    assert job.payload["google_task_list_id"] == "concrete-default-list"
    deduplicated = google_tasks_cleanup_service.enqueue_remote_deletion(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        source_task_id=uuid4(),
        google_task_id="legacy-default-remote",
        google_task_list_id="concrete-default-list",
    )
    assert deduplicated.id == job.id


@pytest.mark.asyncio
async def test_google_task_remote_delete_failure_retries_without_dropping_tombstone(
    db,
    test_auth,
    monkeypatch,
):
    from app import worker
    from app.db.enums import JobStatus
    from app.db.models import Job
    from app.services import google_tasks_cleanup_service, google_tasks_sync_service, job_service

    assert (
        JobType.GOOGLE_TASK_REMOTE_DELETE.value
        in worker.WORKER_STALE_CLAIM_RETRY_SAFE_JOB_TYPES
    )

    job = Job(
        organization_id=test_auth.org.id,
        job_type=JobType.GOOGLE_TASK_REMOTE_DELETE.value,
        payload={
            "user_id": str(test_auth.user.id),
            "source_task_id": str(uuid4()),
            "google_task_id": "retry-remote",
            "google_task_list_id": "retry-list",
        },
        max_attempts=2,
    )
    db.add(job)
    db.commit()

    async def provider_unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        google_tasks_sync_service,
        "delete_google_task_for_cleanup",
        provider_unavailable,
    )

    for expected_status in (JobStatus.PENDING.value, JobStatus.FAILED.value):
        job_service.mark_job_running(db, job)
        with pytest.raises(RuntimeError, match="provider unavailable"):
            await worker.process_job(db, job)
        job_service.mark_job_failed(db, job, "provider unavailable")
        assert job.status == expected_status
        assert google_tasks_cleanup_service.list_tombstoned_remote_keys(
            db,
            org_id=test_auth.org.id,
            user_id=test_auth.user.id,
        ) == {("retry-list", "retry-remote")}


@pytest.mark.asyncio
async def test_process_job_uses_registry(monkeypatch):
    from app import worker

    calls: dict[str, str] = {}

    async def stub_handler(_db, job):
        calls["job_type"] = job.job_type

    def stub_resolver(job_type: str):
        calls["resolved"] = job_type
        return stub_handler

    monkeypatch.setattr(worker, "resolve_job_handler", stub_resolver)

    job = type(
        "Job",
        (),
        {
            "id": "job-id",
            "job_type": JobType.SEND_EMAIL.value,
            "attempts": 0,
            "payload": {},
            "organization_id": None,
        },
    )()

    await worker.process_job(None, job)

    assert calls["resolved"] == JobType.SEND_EMAIL.value
    assert calls["job_type"] == JobType.SEND_EMAIL.value
