"""Tests for user integrations (Zoom/Gmail OAuth + meeting endpoint guards)."""

import json
import uuid
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

    from app.core.security import parse_oauth_state_payload
    payload = parse_oauth_state_payload(cookie_value.value)
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

    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    cookie_value = cookie.get("integration_oauth_state_google_calendar")
    assert cookie_value

    from app.core.security import parse_oauth_state_payload
    payload = parse_oauth_state_payload(cookie_value.value)
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

    from app.core.security import parse_oauth_state_payload
    payload = parse_oauth_state_payload(cookie_value.value)
    assert payload["state"] == state
    assert "ua_hash" in payload


@pytest.mark.asyncio
async def test_google_calendar_callback_happy_path_saves_integration(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.db.models import UserIntegration
    from app.services import oauth_service

    async def fake_exchange_code(code: str, redirect_uri: str):
        return {
            "access_token": "calendar-access-token",
            "refresh_token": "calendar-refresh-token",
            "expires_in": 3600,
        }

    async def fake_get_user_info(access_token: str):
        return {"email": "calendaruser@test.com"}

    monkeypatch.setattr(oauth_service, "exchange_google_calendar_code", fake_exchange_code)
    monkeypatch.setattr(oauth_service, "get_google_calendar_user_info", fake_get_user_info)

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
