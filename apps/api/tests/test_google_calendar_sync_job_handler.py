import uuid

import pytest


@pytest.mark.asyncio
async def test_google_calendar_sync_job_handler_invokes_reconciler(db, test_auth, monkeypatch):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_sync_manual_google_events_for_appointments_async(
        db,
        *,
        user_id,
        org_id,
        date_start=None,
        date_end=None,
    ):
        called["user_id"] = user_id
        called["org_id"] = org_id
        called["date_start"] = date_start
        called["date_end"] = date_end
        return 2

    monkeypatch.setattr(
        "app.services.appointment_integrations.sync_manual_google_events_for_appointments_async",
        fake_sync_manual_google_events_for_appointments_async,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_calendar_sync(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["org_id"] == test_auth.org.id
    assert called["date_start"] is None
    assert called["date_end"] is None


@pytest.mark.asyncio
async def test_google_calendar_watch_refresh_job_handler_invokes_watch_ensure(
    db, test_auth, monkeypatch
):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_ensure_google_calendar_watch(*, db, user_id, calendar_id="primary"):
        called["user_id"] = user_id
        called["calendar_id"] = calendar_id
        return True

    monkeypatch.setattr(
        "app.services.calendar_service.ensure_google_calendar_watch",
        fake_ensure_google_calendar_watch,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_calendar_watch_refresh(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["calendar_id"] == "primary"


@pytest.mark.asyncio
async def test_google_tasks_sync_job_handler_invokes_reconciler(db, test_auth, monkeypatch):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_sync_google_tasks_for_user_async(db, *, user_id, org_id):
        called["user_id"] = user_id
        called["org_id"] = org_id
        return 3

    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.sync_google_tasks_for_user_async",
        fake_sync_google_tasks_for_user_async,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_tasks_sync(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["org_id"] == test_auth.org.id
