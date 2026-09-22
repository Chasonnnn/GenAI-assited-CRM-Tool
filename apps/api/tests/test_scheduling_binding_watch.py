"""Binding watch renewal preserves tenant identity and a working old channel."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.db.models import CalendarBinding, UserIntegration
from app.services import calendar_service, google_calendar_watch_service, oauth_service


@pytest.fixture
def watch_binding(db, test_auth, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="google_calendar",
        account_email="calendar@example.test",
        access_token_encrypted=oauth_service.encrypt_token("fake-local-only"),
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="bookings@example.test",
        display_name="Bookings",
        access_role="owner",
        channel_id="old-channel",
        resource_id="old-resource",
        channel_token_encrypted=oauth_service.encrypt_token("old-token"),
        channel_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(binding)
    db.flush()

    @contextmanager
    def credentials():
        yield db

    monkeypatch.setattr(google_calendar_watch_service, "SessionLocal", credentials)
    monkeypatch.setattr(calendar_service, "get_google_access_token", AsyncMock(return_value="fake"))
    return binding


@pytest.mark.asyncio
async def test_watch_replaces_channel_before_stopping_old(db, watch_binding, monkeypatch):
    calls = []

    async def create(**kwargs):
        assert kwargs["calendar_id"] == watch_binding.calendar_id
        assert watch_binding.channel_id == "old-channel"
        calls.append("create")
        return {
            "channel_id": kwargs["channel_id"],
            "resource_id": "new-resource",
            "expires_at": datetime.now(UTC) + timedelta(days=7),
        }

    async def stop(**kwargs):
        assert watch_binding.resource_id == "new-resource"
        assert kwargs["channel_id"] == "old-channel"
        calls.append("stop")
        return True

    monkeypatch.setattr(calendar_service, "_post_google_events_watch", create)
    monkeypatch.setattr(calendar_service, "_post_google_channel_stop", stop)
    assert await google_calendar_watch_service.ensure_binding_watch(
        db, binding_id=watch_binding.id, org_id=watch_binding.organization_id
    )
    assert calls == ["create", "stop"]
    assert watch_binding.channel_id != "old-channel"
    assert watch_binding.channel_token_encrypted != "old-token"


@pytest.mark.asyncio
async def test_watch_failure_preserves_old_channel(db, watch_binding, monkeypatch):
    stop = AsyncMock()
    monkeypatch.setattr(calendar_service, "_post_google_events_watch", AsyncMock(return_value=None))
    monkeypatch.setattr(calendar_service, "_post_google_channel_stop", stop)
    with pytest.raises(ValueError, match="renewal failed"):
        await google_calendar_watch_service.ensure_binding_watch(
            db, binding_id=watch_binding.id, org_id=watch_binding.organization_id
        )
    assert watch_binding.channel_id == "old-channel"
    stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_watch_cross_org_denied_before_provider_access(db, watch_binding, monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(calendar_service, "_post_google_events_watch", create)
    assert not await google_calendar_watch_service.ensure_binding_watch(
        db, binding_id=watch_binding.id, org_id=uuid4()
    )
    create.assert_not_awaited()
    calendar_service.get_google_access_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_watch_revocation_during_io_does_not_publish_channel(db, watch_binding, monkeypatch):
    async def create(**kwargs):
        watch_binding.is_active = False
        db.flush()
        return {
            "channel_id": "discarded-channel",
            "resource_id": "discarded-resource",
            "expires_at": datetime.now(UTC) + timedelta(days=7),
        }

    stop = AsyncMock(return_value=True)
    monkeypatch.setattr(calendar_service, "_post_google_events_watch", create)
    monkeypatch.setattr(calendar_service, "_post_google_channel_stop", stop)
    assert not await google_calendar_watch_service.ensure_binding_watch(
        db, binding_id=watch_binding.id, org_id=watch_binding.organization_id
    )
    stop.assert_awaited_once_with(
        access_token="fake", channel_id="discarded-channel", resource_id="discarded-resource"
    )


@pytest.mark.asyncio
async def test_sync_handler_routes_binding_and_preserves_deferred_job(db, test_auth, monkeypatch):
    from types import SimpleNamespace

    from app.jobs.handlers import appointments
    from app.services import appointment_google_sync_service, calendar_binding_service

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    sync = AsyncMock()
    monkeypatch.setattr(calendar_binding_service, "sync_binding", sync)
    binding_id = uuid4()
    job = SimpleNamespace(organization_id=test_auth.org.id, payload={"binding_id": str(binding_id)})
    await appointments.process_google_calendar_sync(db, job)
    sync.assert_awaited_once_with(db, binding_id=binding_id, org_id=test_auth.org.id)
    monkeypatch.setattr(
        appointment_google_sync_service, "process_job", AsyncMock(return_value=False)
    )
    assert await appointments.process_appointment_google_sync(db, job) is False
