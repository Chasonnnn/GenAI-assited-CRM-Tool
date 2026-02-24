from __future__ import annotations

from datetime import date

import pytest


@pytest.mark.asyncio
async def test_internal_contact_reminders_endpoint_runs_service(client, db, monkeypatch):
    from app.core.config import settings
    from app.routers import internal as internal_router
    from app.services import contact_reminder_service

    monkeypatch.setattr(settings, "INTERNAL_SECRET", "secret")

    class _TestSession:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(internal_router, "SessionLocal", lambda: _TestSession())
    monkeypatch.setattr(
        contact_reminder_service,
        "process_contact_reminder_jobs",
        lambda _session: {
            "orgs_processed": 2,
            "total_surrogates_checked": 5,
            "total_notifications_created": 3,
            "errors": [],
        },
    )

    response = await client.post(
        "/internal/scheduled/contact-reminders",
        headers={"X-Internal-Secret": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "orgs_processed": 2,
        "total_surrogates_checked": 5,
        "total_notifications_created": 3,
        "errors": [],
    }


def test_contact_reminder_service_respects_user_setting(monkeypatch, db, test_org, test_user):
    from app.services import contact_reminder_service, notification_facade

    surrogate_data = {
        "id": test_org.id,
        "surrogate_number": "S10001",
        "owner_id": test_user.id,
        "distinct_attempt_days": 1,
        "assigned_day": date(2026, 2, 20),
        "today": date(2026, 2, 24),
    }

    monkeypatch.setattr(
        contact_reminder_service,
        "get_surrogates_needing_followup",
        lambda _session, _org_id, _org_tz: [surrogate_data],
    )

    created: dict = {"calls": 0}

    def fake_create_notification(**kwargs):
        created["calls"] += 1
        created["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(notification_facade, "create_notification", fake_create_notification)
    monkeypatch.setattr(notification_facade, "should_notify", lambda *_args, **_kwargs: False)

    skipped = contact_reminder_service.check_contact_reminders_for_org(db, test_org.id)
    assert skipped["surrogates_checked"] == 1
    assert skipped["notifications_created"] == 0
    assert created["calls"] == 0

    monkeypatch.setattr(notification_facade, "should_notify", lambda *_args, **_kwargs: True)
    created_result = contact_reminder_service.check_contact_reminders_for_org(db, test_org.id)
    assert created_result["surrogates_checked"] == 1
    assert created_result["notifications_created"] == 1
    assert created["calls"] == 1
