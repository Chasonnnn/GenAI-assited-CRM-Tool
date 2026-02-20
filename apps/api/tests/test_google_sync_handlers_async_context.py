from datetime import datetime, timedelta, timezone
import uuid

import pytest


@pytest.mark.asyncio
async def test_google_calendar_sync_job_handler_imports_event_in_async_context(
    db,
    test_auth,
    monkeypatch,
):
    from app.db.models import Appointment, UserIntegration
    from app.jobs.handlers import appointments as appointments_handler
    from app.services import calendar_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token-1",
            account_email="owner@example.com",
        )
    )
    db.commit()

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    end = start + timedelta(minutes=30)

    async def fake_list_user_google_calendar_ids(db, user_id):
        assert user_id == test_auth.user.id
        return ["primary"]

    async def fake_get_user_calendar_events(
        db,
        user_id,
        time_min,
        time_max,
        calendar_id="primary",
    ):
        assert user_id == test_auth.user.id
        return {
            "connected": True,
            "events": [
                {
                    "id": "async_evt_1",
                    "summary": "Async handler event",
                    "start": start,
                    "end": end,
                    "html_link": "https://calendar.google.com/event?eid=async1",
                    "is_all_day": False,
                }
            ],
            "error": None,
        }

    monkeypatch.setattr(
        calendar_service,
        "list_user_google_calendar_ids",
        fake_list_user_google_calendar_ids,
    )
    monkeypatch.setattr(
        calendar_service,
        "get_user_calendar_events",
        fake_get_user_calendar_events,
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

    stored = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_auth.org.id,
            Appointment.user_id == test_auth.user.id,
            Appointment.google_event_id == "async_evt_1",
        )
        .first()
    )
    assert stored is not None
    assert stored.client_name == "Async handler event"


@pytest.mark.asyncio
async def test_google_tasks_sync_job_handler_imports_task_in_async_context(
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import OwnerType
    from app.db.models import Task, UserIntegration
    from app.jobs.handlers import appointments as appointments_handler
    from app.services import google_tasks_sync_service, oauth_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token-1",
            account_email="owner@example.com",
        )
    )
    db.commit()

    async def fake_get_access_token_async(db, user_id, integration_type):
        assert user_id == test_auth.user.id
        assert integration_type == "google_calendar"
        return "token"

    async def fake_list_google_task_lists(access_token):
        assert access_token == "token"
        return [{"id": "@default"}]

    async def fake_list_google_tasks(access_token, task_list_id):
        assert access_token == "token"
        assert task_list_id == "@default"
        return [
            {
                "id": "g_task_1",
                "title": "Async handler task",
                "notes": "from google",
                "status": "needsAction",
                "updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        ]

    monkeypatch.setattr(oauth_service, "get_access_token_async", fake_get_access_token_async)
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_list_google_task_lists",
        fake_list_google_task_lists,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_list_google_tasks",
        fake_list_google_tasks,
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

    stored = (
        db.query(Task)
        .filter(
            Task.organization_id == test_auth.org.id,
            Task.owner_type == OwnerType.USER.value,
            Task.owner_id == test_auth.user.id,
            Task.google_task_id == "g_task_1",
        )
        .first()
    )
    assert stored is not None
    assert stored.title == "Async handler task"
