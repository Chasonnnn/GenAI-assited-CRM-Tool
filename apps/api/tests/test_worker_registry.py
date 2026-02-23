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


def test_job_registry_resolves_ticket_outbound_send_handler():
    from app.jobs.registry import resolve_job_handler

    handler = resolve_job_handler(JobType.TICKET_OUTBOUND_SEND.value)
    assert callable(handler)


def test_job_registry_unknown_raises():
    from app.jobs.registry import resolve_job_handler

    with pytest.raises(ValueError):
        resolve_job_handler("nope")


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
