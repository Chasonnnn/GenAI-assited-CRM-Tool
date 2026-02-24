from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import NotificationType


@pytest.mark.asyncio
async def test_process_notification_uses_notification_service_create_notification(monkeypatch, db):
    from app.jobs.handlers import notifications

    captured: dict = {}

    def fake_create_notification(**kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr("app.services.notification_service.create_notification", fake_create_notification)

    job = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        payload={
            "user_id": str(uuid4()),
            "title": "Queued notification",
            "message": "Legacy payload body",
            "type": NotificationType.TASK_DUE_SOON.value,
            "entity_type": "task",
            "entity_id": str(uuid4()),
            "dedupe_key": "queued-notification:1",
        },
    )

    await notifications.process_notification(db, job)

    assert captured["kwargs"]["title"] == "Queued notification"
    assert captured["kwargs"]["body"] == "Legacy payload body"
    assert captured["kwargs"]["type"] == NotificationType.TASK_DUE_SOON
    assert captured["kwargs"]["entity_type"] == "task"
    assert captured["kwargs"]["dedupe_key"] == "queued-notification:1"


@pytest.mark.asyncio
async def test_process_reminder_uses_notification_service_create_notification(monkeypatch, db):
    from app.jobs.handlers import reminders

    captured: dict = {}

    def fake_create_notification(**kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr("app.services.notification_service.create_notification", fake_create_notification)

    job = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        payload={
            "user_id": str(uuid4()),
            "title": "Reminder title",
            "message": "Legacy reminder message",
            "type": NotificationType.CONTACT_REMINDER.value,
            "entity_type": "surrogate",
            "entity_id": str(uuid4()),
            "send_email": False,
        },
    )

    await reminders.process_reminder(db, job)

    assert captured["kwargs"]["title"] == "Reminder title"
    assert captured["kwargs"]["body"] == "Legacy reminder message"
    assert captured["kwargs"]["type"] == NotificationType.CONTACT_REMINDER
    assert captured["kwargs"]["entity_type"] == "surrogate"
