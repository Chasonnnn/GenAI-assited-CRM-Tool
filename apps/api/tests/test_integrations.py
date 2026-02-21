"""Tests for user integrations (Zoom/Gmail OAuth + meeting endpoint guards)."""

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.core.encryption import hash_email
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_zoom_connect_sets_state_cookie_and_returns_auth_url(
    authed_client: AsyncClient,
):
    response = await authed_client.get("/integrations/zoom/connect")
    assert response.status_code == 200

    data = response.json()
    assert "auth_url" in data

    parsed = urlparse(data["auth_url"])
    qs = parse_qs(parsed.query)
    assert "state" in qs
    state = qs["state"][0]

    # httpx stores the cookie value with RFC6265 escapes (e.g. \054 for commas),
    # so parse from the response Set-Cookie header to get the unescaped JSON.
    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    cookie_value = cookie.get("integration_oauth_state_zoom")
    assert cookie_value
    payload = json.loads(cookie_value.value)
    assert payload["state"] == state
    assert "ua_hash" in payload


@pytest.mark.asyncio
async def test_zoom_connect_uses_cross_site_cookie_settings_when_enabled(
    authed_client: AsyncClient,
    monkeypatch,
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "none")

    response = await authed_client.get("/integrations/zoom/connect")
    assert response.status_code == 200

    cookie_headers = response.headers.get_list("set-cookie")
    zoom_cookie = next(
        header for header in cookie_headers if "integration_oauth_state_zoom=" in header
    )
    zoom_cookie_lower = zoom_cookie.lower()
    assert "samesite=none" in zoom_cookie_lower
    assert "secure" in zoom_cookie_lower


@pytest.mark.asyncio
async def test_zoom_callback_requires_state_cookie(authed_client: AsyncClient):
    response = await authed_client.get(
        "/integrations/zoom/callback",
        params={"code": "dummy", "state": "dummy"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/settings/integrations?error=invalid_state" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_zoom_callback_happy_path_saves_integration(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.db.models import UserIntegration
    from app.services import oauth_service

    async def fake_exchange_zoom_code(code: str, redirect_uri: str):
        return {
            "access_token": "zoom-access-token",
            "refresh_token": "zoom-refresh-token",
            "expires_in": 3600,
        }

    async def fake_get_zoom_user_info(access_token: str):
        return {"email": "zoomuser@test.com"}

    monkeypatch.setattr(oauth_service, "exchange_zoom_code", fake_exchange_zoom_code)
    monkeypatch.setattr(oauth_service, "get_zoom_user_info", fake_get_zoom_user_info)

    connect = await authed_client.get("/integrations/zoom/connect")
    assert connect.status_code == 200
    state = parse_qs(urlparse(connect.json()["auth_url"]).query)["state"][0]

    callback = await authed_client.get(
        "/integrations/zoom/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert "/settings/integrations?success=zoom" in callback.headers.get("location", "")

    integration = (
        db.query(UserIntegration)
        .filter(UserIntegration.user_id == test_auth.user.id)
        .filter(UserIntegration.integration_type == "zoom")
        .first()
    )
    assert integration is not None
    assert integration.account_email == "zoomuser@test.com"


@pytest.mark.asyncio
async def test_google_calendar_connect_sets_state_cookie_and_returns_auth_url(
    authed_client: AsyncClient,
):
    response = await authed_client.get("/integrations/google-calendar/connect")
    assert response.status_code == 200

    data = response.json()
    assert "auth_url" in data

    parsed = urlparse(data["auth_url"])
    qs = parse_qs(parsed.query)
    assert "state" in qs
    state = qs["state"][0]
    assert "scope" in qs
    scopes = set(qs["scope"][0].split(" "))
    assert "https://www.googleapis.com/auth/calendar.events" in scopes
    assert "https://www.googleapis.com/auth/tasks" in scopes
    assert qs.get("access_type") == ["offline"]
    assert qs.get("include_granted_scopes") == ["true"]

    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    cookie_value = cookie.get("integration_oauth_state_google_calendar")
    assert cookie_value
    payload = json.loads(cookie_value.value)
    assert payload["state"] == state
    assert "ua_hash" in payload


@pytest.mark.asyncio
async def test_gcp_connect_sets_state_cookie_and_returns_auth_url(
    authed_client: AsyncClient,
):
    response = await authed_client.get("/integrations/gcp/connect")
    assert response.status_code == 200

    data = response.json()
    assert "auth_url" in data

    parsed = urlparse(data["auth_url"])
    qs = parse_qs(parsed.query)
    assert "state" in qs
    state = qs["state"][0]

    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    cookie_value = cookie.get("integration_oauth_state_gcp")
    assert cookie_value
    payload = json.loads(cookie_value.value)
    assert payload["state"] == state
    assert "ua_hash" in payload


@pytest.mark.asyncio
async def test_google_calendar_callback_happy_path_saves_integration(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.db.models import UserIntegration
    from app.services import (
        appointment_integrations,
        calendar_service,
        google_tasks_sync_service,
        oauth_service,
    )

    async def fake_exchange_code(code: str, redirect_uri: str):
        return {
            "access_token": "calendar-access-token",
            "refresh_token": "calendar-refresh-token",
            "expires_in": 3600,
        }

    async def fake_get_user_info(access_token: str):
        return {"email": "calendaruser@test.com"}

    watch_calls: list[uuid.UUID] = []
    appointment_sync_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
    task_sync_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def fake_ensure_google_calendar_watch(*, db, user_id, calendar_id="primary"):
        watch_calls.append(user_id)
        return True

    async def fake_sync_manual_google_events_for_appointments_async(
        db, *, user_id, org_id, date_start=None, date_end=None
    ):
        del date_start, date_end
        appointment_sync_calls.append((user_id, org_id))
        return 2

    async def fake_sync_google_tasks_for_user_async(db, *, user_id, org_id):
        task_sync_calls.append((user_id, org_id))
        return 3

    monkeypatch.setattr(oauth_service, "exchange_google_calendar_code", fake_exchange_code)
    monkeypatch.setattr(oauth_service, "get_google_calendar_user_info", fake_get_user_info)
    monkeypatch.setattr(
        calendar_service,
        "ensure_google_calendar_watch",
        fake_ensure_google_calendar_watch,
    )
    monkeypatch.setattr(
        appointment_integrations,
        "sync_manual_google_events_for_appointments_async",
        fake_sync_manual_google_events_for_appointments_async,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "sync_google_tasks_for_user_async",
        fake_sync_google_tasks_for_user_async,
    )

    connect = await authed_client.get("/integrations/google-calendar/connect")
    assert connect.status_code == 200
    state = parse_qs(urlparse(connect.json()["auth_url"]).query)["state"][0]

    callback = await authed_client.get(
        "/integrations/google-calendar/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert "/settings/integrations?success=google_calendar" in callback.headers.get("location", "")

    integration = (
        db.query(UserIntegration)
        .filter(UserIntegration.user_id == test_auth.user.id)
        .filter(UserIntegration.integration_type == "google_calendar")
        .first()
    )
    assert integration is not None
    assert integration.account_email == "calendaruser@test.com"
    assert watch_calls == [test_auth.user.id]
    assert appointment_sync_calls == [(test_auth.user.id, test_auth.org.id)]
    assert task_sync_calls == [(test_auth.user.id, test_auth.org.id)]


@pytest.mark.asyncio
async def test_google_calendar_status_includes_tasks_access_diagnostics(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.models import UserIntegration
    from app.services import google_tasks_sync_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token-1",
            account_email="owner@example.com",
        )
    )
    db.commit()

    def fake_check_google_tasks_access(db, user_id):
        assert user_id == test_auth.user.id
        return True, None

    monkeypatch.setattr(
        google_tasks_sync_service,
        "check_google_tasks_access",
        fake_check_google_tasks_access,
    )

    response = await authed_client.get("/integrations/google-calendar/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["tasks_accessible"] is True
    assert data["tasks_error"] is None
    assert data["last_sync_at"] is not None


@pytest.mark.asyncio
async def test_google_calendar_manual_sync_runs_reconciliation_and_updates_last_sync(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.models import UserIntegration
    from app.services import (
        appointment_integrations,
        calendar_service,
        google_tasks_sync_service,
    )

    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="google_calendar",
        access_token_encrypted="token-1",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    previous_updated_at = integration.updated_at

    watch_calls: list[uuid.UUID] = []

    async def fake_ensure_google_calendar_watch(*, db, user_id, calendar_id="primary"):
        del db, calendar_id
        watch_calls.append(user_id)
        return True

    monkeypatch.setattr(
        calendar_service,
        "ensure_google_calendar_watch",
        fake_ensure_google_calendar_watch,
    )
    monkeypatch.setattr(
        appointment_integrations,
        "backfill_confirmed_appointments_to_google",
        lambda **kwargs: 1,
    )

    async def fake_sync_manual_google_events_for_appointments_async(
        db, *, user_id, org_id, date_start=None, date_end=None
    ):
        del db, date_start, date_end
        assert user_id == test_auth.user.id
        assert org_id == test_auth.org.id
        return 2

    async def fake_sync_google_tasks_for_user_async(db, *, user_id, org_id):
        del db
        assert user_id == test_auth.user.id
        assert org_id == test_auth.org.id
        return 3

    monkeypatch.setattr(
        appointment_integrations,
        "sync_manual_google_events_for_appointments_async",
        fake_sync_manual_google_events_for_appointments_async,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "sync_google_tasks_for_user_async",
        fake_sync_google_tasks_for_user_async,
    )

    response = await authed_client.post("/integrations/google-calendar/sync")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["connected"] is True
    assert payload["outbound_backfilled"] == 1
    assert payload["appointment_changes"] == 2
    assert payload["task_changes"] == 3
    assert payload["warnings"] == []
    assert payload["last_sync_at"] is not None
    assert watch_calls == [test_auth.user.id]

    db.refresh(integration)
    assert integration.updated_at >= previous_updated_at


@pytest.mark.asyncio
async def test_appointments_list_imports_manual_google_calendar_event(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment
    from app.services import calendar_service

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    end = start + timedelta(minutes=45)

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
                    "id": "google_manual_1",
                    "summary": "Manual intake consult",
                    "start": start,
                    "end": end,
                    "html_link": "https://calendar.google.com/event?eid=manual1",
                    "is_all_day": False,
                }
            ],
            "error": None,
        }

    monkeypatch.setattr(calendar_service, "get_user_calendar_events", fake_get_user_calendar_events)

    response = await authed_client.get("/appointments", params={"status": "confirmed"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["client_name"] == "Manual intake consult"
    assert item["status"] == AppointmentStatus.CONFIRMED.value
    assert item["meeting_mode"] == MeetingMode.GOOGLE_MEET.value
    assert item["appointment_type_name"] is None

    stored = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_auth.org.id,
            Appointment.user_id == test_auth.user.id,
            Appointment.google_event_id == "google_manual_1",
        )
        .first()
    )
    assert stored is not None
    assert stored.scheduled_start == start
    assert stored.scheduled_end == end


@pytest.mark.asyncio
async def test_appointments_list_imports_google_event_from_non_primary_calendar(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.models import Appointment
    from app.services import calendar_service

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=5)
    end = start + timedelta(minutes=30)
    calendar_calls: list[str] = []

    async def fake_list_user_google_calendar_ids(db, user_id):
        assert user_id == test_auth.user.id
        return ["primary", "team-calendar"]

    async def fake_get_user_calendar_events(
        db,
        user_id,
        time_min,
        time_max,
        calendar_id="primary",
    ):
        assert user_id == test_auth.user.id
        calendar_calls.append(calendar_id)
        if calendar_id == "team-calendar":
            return {
                "connected": True,
                "events": [
                    {
                        "id": "google_team_1",
                        "summary": "Team calendar sync event",
                        "start": start,
                        "end": end,
                        "html_link": "https://calendar.google.com/event?eid=team1",
                        "is_all_day": False,
                    }
                ],
                "error": None,
            }
        return {"connected": True, "events": [], "error": None}

    monkeypatch.setattr(
        calendar_service,
        "list_user_google_calendar_ids",
        fake_list_user_google_calendar_ids,
        raising=False,
    )
    monkeypatch.setattr(calendar_service, "get_user_calendar_events", fake_get_user_calendar_events)

    response = await authed_client.get("/appointments", params={"status": "confirmed"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["client_name"] == "Team calendar sync event"
    assert set(calendar_calls) == {"primary", "team-calendar"}

    stored = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_auth.org.id,
            Appointment.user_id == test_auth.user.id,
            Appointment.google_event_id == "google_team_1",
        )
        .first()
    )
    assert stored is not None
    assert stored.scheduled_start == start
    assert stored.scheduled_end == end


@pytest.mark.asyncio
async def test_appointments_list_backfills_missing_google_event_for_confirmed_platform_appointment(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType
    from app.services import appointment_integrations, calendar_service

    appt_type = AppointmentType(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        name="Backfill Test",
        slug=f"backfill-test-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        meeting_modes=[MeetingMode.ZOOM.value],
        reminder_hours_before=24,
        is_active=True,
    )
    db.add(appt_type)
    db.flush()

    scheduled_start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)
    appointment = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=appt_type.id,
        client_name="Backfill Client",
        client_email="backfill@example.com",
        client_phone="+1-555-000-1234",
        client_timezone="UTC",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id=None,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    sync_calls: list[tuple[str, str]] = []

    def fake_sync_to_google_calendar(db, appt, action):
        sync_calls.append((str(appt.id), action))
        return "google_evt_backfilled"

    monkeypatch.setattr(
        appointment_integrations,
        "sync_to_google_calendar",
        fake_sync_to_google_calendar,
    )
    monkeypatch.setattr(
        appointment_integrations,
        "sync_manual_google_events_for_appointments",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        calendar_service,
        "check_user_has_google_calendar",
        lambda _db, _user_id: True,
    )

    response = await authed_client.get("/appointments", params={"status": "confirmed"})
    assert response.status_code == 200

    db.refresh(appointment)
    assert sync_calls == [(str(appointment.id), "create")]
    assert appointment.google_event_id == "google_evt_backfilled"


@pytest.mark.asyncio
async def test_staff_reschedule_slots_endpoint_returns_slots_for_owned_appointment(
    authed_client: AsyncClient,
    db,
    test_auth,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType, AvailabilityRule

    timezone_name = "America/Los_Angeles"

    appt_type = AppointmentType(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        name="Reschedule Endpoint Type",
        slug=f"reschedule-endpoint-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=10,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        meeting_modes=[MeetingMode.GOOGLE_MEET.value],
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()

    # Monday availability 9:00-17:00 in Pacific
    db.add(
        AvailabilityRule(
            organization_id=test_auth.org.id,
            user_id=test_auth.user.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone=timezone_name,
        )
    )
    db.flush()

    target_date = date(2026, 2, 23)  # Monday
    scheduled_start = datetime(2026, 2, 23, 20, 0, tzinfo=timezone.utc)  # 12:00 PT
    appointment = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=appt_type.id,
        client_name="Reschedule Owner",
        client_email="reschedule-owner@example.com",
        client_phone="+1-555-777-9999",
        client_timezone=timezone_name,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id="g_evt_123",
    )
    db.add(appointment)
    db.commit()

    response = await authed_client.get(
        f"/appointments/{appointment.id}/reschedule/slots",
        params={
            "date_start": target_date.isoformat(),
            "date_end": target_date.isoformat(),
            "client_timezone": timezone_name,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["appointment_type"]["id"] == str(appt_type.id)
    assert len(data["slots"]) > 0


@pytest.mark.asyncio
async def test_staff_reschedule_endpoint_accepts_valid_available_slot(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType, AvailabilityRule
    from app.routers import appointments as appointments_router
    from app.services import appointment_integrations

    timezone_name = "America/Los_Angeles"

    appt_type = AppointmentType(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        name="Reschedule Submit Type",
        slug=f"reschedule-submit-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=10,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        meeting_modes=[MeetingMode.GOOGLE_MEET.value],
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()

    db.add(
        AvailabilityRule(
            organization_id=test_auth.org.id,
            user_id=test_auth.user.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone=timezone_name,
        )
    )
    db.flush()

    scheduled_start = datetime(2026, 2, 23, 20, 0, tzinfo=timezone.utc)  # 12:00 PT
    appointment = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=appt_type.id,
        client_name="Reschedule Submit",
        client_email="reschedule-submit@example.com",
        client_phone="+1-555-111-2222",
        client_timezone=timezone_name,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id="google_evt_reschedule",
    )
    db.add(appointment)
    db.commit()

    def fake_update_google_meet_event(db, appointment, new_start, new_end):
        del db, appointment, new_start, new_end
        return None

    monkeypatch.setattr(
        appointment_integrations,
        "update_google_meet_event",
        fake_update_google_meet_event,
    )
    monkeypatch.setattr(
        appointments_router.appointment_email_service,
        "send_rescheduled",
        lambda db, appt, old_start, base_url: None,
    )

    response = await authed_client.post(
        f"/appointments/{appointment.id}/reschedule",
        json={"scheduled_start": "2026-02-23T18:00:00Z"},  # 10:00 PT
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == str(appointment.id)
    assert payload["scheduled_start"] in {
        "2026-02-23T18:00:00Z",
        "2026-02-23T18:00:00+00:00",
    }

    db.refresh(appointment)
    assert appointment.scheduled_start == datetime(2026, 2, 23, 18, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_google_calendar_events_endpoint_fetches_across_calendars(
    authed_client: AsyncClient,
    test_auth,
    monkeypatch,
):
    from app.services import calendar_service

    start = datetime(2026, 2, 19, 18, 30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    called: dict[str, object] = {}

    async def fake_get_user_calendar_events_across_calendars(
        db,
        user_id,
        time_min,
        time_max,
        calendar_ids=None,
    ):
        called["user_id"] = user_id
        called["time_min"] = time_min
        called["time_max"] = time_max
        called["calendar_ids"] = calendar_ids
        return {
            "connected": True,
            "events": [
                {
                    "id": "google_multi_1",
                    "summary": "Cross-calendar event",
                    "start": start,
                    "end": end,
                    "html_link": "https://calendar.google.com/event?eid=multi1",
                    "is_all_day": False,
                }
            ],
            "error": None,
        }

    monkeypatch.setattr(
        calendar_service,
        "get_user_calendar_events_across_calendars",
        fake_get_user_calendar_events_across_calendars,
    )

    response = await authed_client.get(
        "/integrations/google/calendar/events",
        params={
            "date_start": "2026-02-01",
            "date_end": "2026-02-28",
            "timezone": "America/Los_Angeles",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert called["user_id"] == test_auth.user.id
    assert payload["connected"] is True
    assert payload["error"] is None
    assert len(payload["events"]) == 1
    assert payload["events"][0]["id"] == "google_multi_1"
    assert payload["events"][0]["summary"] == "Cross-calendar event"
    assert payload["events"][0]["source"] == "google"


@pytest.mark.asyncio
async def test_get_google_events_encodes_calendar_id_in_request(monkeypatch):
    from app.services import calendar_service

    requested_urls: list[str] = []

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"items": []}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            requested_urls.append(str(url))
            return _FakeResponse()

    monkeypatch.setattr(calendar_service.httpx, "AsyncClient", _FakeAsyncClient)

    await calendar_service.get_google_events(
        access_token="token",
        calendar_id="en.usa#holiday@group.v.calendar.google.com",
        time_min=datetime(2026, 2, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 2, 2, tzinfo=timezone.utc),
    )

    assert requested_urls
    assert "en.usa%23holiday%40group.v.calendar.google.com" in requested_urls[0], (
        "Calendar ID must be URL-encoded in path requests"
    )


@pytest.mark.asyncio
async def test_get_google_events_defaults_blank_summary_to_no_title(monkeypatch):
    from app.services import calendar_service

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "items": [
                    {
                        "id": "evt-blank-summary",
                        "summary": "",
                        "start": {"dateTime": "2026-02-19T18:30:00-05:00"},
                        "end": {"dateTime": "2026-02-19T19:30:00-05:00"},
                        "htmlLink": "https://calendar.google.com/event?eid=blank",
                    }
                ]
            }

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            return _FakeResponse()

    monkeypatch.setattr(calendar_service.httpx, "AsyncClient", _FakeAsyncClient)

    events = await calendar_service.get_google_events(
        access_token="token",
        calendar_id="primary",
        time_min=datetime(2026, 2, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 2, 2, tzinfo=timezone.utc),
    )

    assert len(events) == 1
    assert events[0]["summary"] == "(No title)"


@pytest.mark.asyncio
async def test_appointments_list_cancels_removed_imported_google_event(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment
    from app.services import calendar_service

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)
    appt = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=None,
        client_name="Google imported event",
        client_email="google-calendar-sync@local.invalid",
        client_phone="google-calendar",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id="google_removed_1",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    async def fake_get_user_calendar_events(
        db,
        user_id,
        time_min,
        time_max,
        calendar_id="primary",
    ):
        assert user_id == test_auth.user.id
        return {"connected": True, "events": [], "error": None}

    monkeypatch.setattr(calendar_service, "get_user_calendar_events", fake_get_user_calendar_events)

    confirmed_response = await authed_client.get("/appointments", params={"status": "confirmed"})
    assert confirmed_response.status_code == 200
    assert confirmed_response.json()["total"] == 0

    db.refresh(appt)
    assert appt.status == AppointmentStatus.CANCELLED.value
    assert appt.cancelled_at is not None
    assert appt.cancelled_by_client is False
    assert appt.cancellation_reason == "Cancelled in Google Calendar"

    cancelled_response = await authed_client.get("/appointments", params={"status": "cancelled"})
    assert cancelled_response.status_code == 200
    payload = cancelled_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(appt.id)


@pytest.mark.asyncio
async def test_appointments_list_cancels_removed_app_created_google_event(
    authed_client: AsyncClient,
    db,
    test_auth,
    monkeypatch,
):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType

    from app.services import calendar_service

    appt_type = AppointmentType(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        name="Initial Consultation",
        slug=f"initial-consult-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        meeting_modes=[MeetingMode.ZOOM.value],
        reminder_hours_before=24,
        is_active=True,
    )
    db.add(appt_type)
    db.flush()

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=4)
    appt = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=appt_type.id,
        client_name="App-created event",
        client_email="intake@example.com",
        client_phone="+1-555-123-4567",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id="google_removed_app_1",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    async def fake_get_user_calendar_events(
        db,
        user_id,
        time_min,
        time_max,
        calendar_id="primary",
    ):
        assert user_id == test_auth.user.id
        return {"connected": True, "events": [], "error": None}

    monkeypatch.setattr(calendar_service, "get_user_calendar_events", fake_get_user_calendar_events)

    confirmed_response = await authed_client.get("/appointments", params={"status": "confirmed"})
    assert confirmed_response.status_code == 200
    assert confirmed_response.json()["total"] == 0

    db.refresh(appt)
    assert appt.status == AppointmentStatus.CANCELLED.value
    assert appt.cancelled_at is not None
    assert appt.cancelled_by_client is False
    assert appt.cancellation_reason == "Cancelled in Google Calendar"

    cancelled_response = await authed_client.get("/appointments", params={"status": "cancelled"})
    assert cancelled_response.status_code == 200
    payload = cancelled_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(appt.id)


@pytest.mark.asyncio
async def test_gcp_callback_happy_path_saves_integration(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.db.models import UserIntegration
    from app.services import oauth_service

    async def fake_exchange_code(code: str, redirect_uri: str):
        return {
            "access_token": "gcp-access-token",
            "refresh_token": "gcp-refresh-token",
            "expires_in": 3600,
        }

    async def fake_get_user_info(access_token: str):
        return {"email": "gcpuser@test.com"}

    monkeypatch.setattr(oauth_service, "exchange_gcp_code", fake_exchange_code)
    monkeypatch.setattr(oauth_service, "get_gcp_user_info", fake_get_user_info)

    connect = await authed_client.get("/integrations/gcp/connect")
    assert connect.status_code == 200
    state = parse_qs(urlparse(connect.json()["auth_url"]).query)["state"][0]

    callback = await authed_client.get(
        "/integrations/gcp/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert "/settings/integrations?success=gcp" in callback.headers.get("location", "")

    integration = (
        db.query(UserIntegration)
        .filter(UserIntegration.user_id == test_auth.user.id)
        .filter(UserIntegration.integration_type == "gcp")
        .first()
    )
    assert integration is not None
    assert integration.account_email == "gcpuser@test.com"


@pytest.mark.asyncio
async def test_create_zoom_meeting_surrogate_not_found_returns_404(
    authed_client: AsyncClient,
):
    response = await authed_client.post(
        "/integrations/zoom/meetings",
        json={
            "entity_type": "surrogate",
            "entity_id": str(uuid.uuid4()),
            "topic": "Test Meeting",
            "duration": 30,
        },
    )
    assert response.status_code == 404
    assert response.json().get("detail") == "Surrogate not found"


@pytest.mark.asyncio
async def test_create_zoom_meeting_intended_parent_not_found_returns_404(
    authed_client: AsyncClient,
):
    response = await authed_client.post(
        "/integrations/zoom/meetings",
        json={
            "entity_type": "intended_parent",
            "entity_id": str(uuid.uuid4()),
            "topic": "Test Meeting",
            "duration": 30,
        },
    )
    assert response.status_code == 404
    assert response.json().get("detail") == "Intended parent not found"


@pytest.mark.asyncio
async def test_create_zoom_meeting_returns_response_when_service_mocked(
    authed_client: AsyncClient, db, test_auth, default_stage, monkeypatch
):
    from app.db.enums import OwnerType
    from app.db.models import Surrogate, UserIntegration
    from app.services import zoom_service

    # Create a minimal surrogate in-org
    normalized_email = normalize_email("surrogate@example.com")
    surrogate = Surrogate(
        surrogate_number="S10001",
        organization_id=test_auth.org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_auth.user.id,
        full_name="Test Surrogate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    # Mark Zoom as connected for current user
    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="zoom",
        access_token_encrypted="dummy",
        account_email="zoomuser@test.com",
    )
    db.add(integration)
    db.flush()

    async def fake_schedule_zoom_meeting(**kwargs):
        return zoom_service.CreateMeetingResult(
            meeting=zoom_service.ZoomMeeting(
                id=123,
                uuid="test",
                topic=kwargs["topic"],
                start_time=None,
                duration=kwargs.get("duration", 30),
                timezone="UTC",
                join_url="https://zoom.us/j/123",
                start_url="https://zoom.us/s/123",
                password=None,
            ),
            note_id=uuid.uuid4(),
            task_id=None,
        )

    monkeypatch.setattr(zoom_service, "schedule_zoom_meeting", fake_schedule_zoom_meeting)

    response = await authed_client.post(
        "/integrations/zoom/meetings",
        json={
            "entity_type": "surrogate",
            "entity_id": str(surrogate.id),
            "topic": "Call with Test Case",
            "duration": 30,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["join_url"] == "https://zoom.us/j/123"
    assert data["meeting_id"] == 123
