from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from app.db.models import Membership, UserIntegration
from app.services import oauth_service


class _HTTPResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    def json(self):
        return self._payload


class _AsyncClient:
    def __init__(self, post_payload: dict | None = None, get_payload: dict | None = None, fail: bool = False):
        self._post_payload = post_payload or {"access_token": "a1"}
        self._get_payload = get_payload or {"email": "user@example.com"}
        self._fail = fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self._fail:
            raise RuntimeError("request failed")
        return _HTTPResponse(self._post_payload)

    async def get(self, *args, **kwargs):
        if self._fail:
            raise RuntimeError("request failed")
        return _HTTPResponse(self._get_payload)


def test_oauth_helper_time_and_encryption():
    now = oauth_service._now_utc()
    assert now.tzinfo == timezone.utc
    assert oauth_service._is_expired(now - timedelta(seconds=1)) is True
    assert oauth_service._is_expired((now + timedelta(minutes=1)).replace(tzinfo=None)) is False

    encrypted = oauth_service.encrypt_token("secret-token")
    assert encrypted != "secret-token"
    assert oauth_service.decrypt_token(encrypted) == "secret-token"


def test_oauth_save_get_delete_integration(db, test_user):
    integration = oauth_service.save_integration(
        db,
        user_id=test_user.id,
        integration_type="gmail",
        access_token="access-1",
        refresh_token="refresh-1",
        expires_in=3600,
        account_email="acct@example.com",
        granted_scopes=["scope.a"],
    )
    assert integration.integration_type == "gmail"

    loaded = oauth_service.get_user_integration(db, test_user.id, "gmail")
    assert loaded is not None
    assert oauth_service.get_access_token(db, test_user.id, "gmail") == "access-1"

    oauth_service.save_integration(
        db,
        user_id=test_user.id,
        integration_type="gmail",
        access_token="access-2",
        refresh_token="refresh-2",
        expires_in=1200,
        granted_scopes=["scope.b"],
    )
    assert oauth_service.get_access_token(db, test_user.id, "gmail") == "access-2"
    assert oauth_service.delete_integration(db, test_user.id, "gmail") is True
    assert oauth_service.get_user_integration(db, test_user.id, "gmail") is None


def test_oauth_get_access_token_refreshes_when_expired(monkeypatch, db, test_user):
    integration = oauth_service.save_integration(
        db,
        user_id=test_user.id,
        integration_type="gmail",
        access_token="old-access",
        refresh_token="refresh-token",
        expires_in=1,
    )
    integration.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.add(integration)
    db.commit()

    def _refresh(session, integration_obj, integration_type):
        integration_obj.access_token_encrypted = oauth_service.encrypt_token("refreshed-access")
        session.commit()
        return True

    monkeypatch.setattr(oauth_service, "refresh_token", _refresh)
    assert oauth_service.get_access_token(db, test_user.id, "gmail") == "refreshed-access"


@pytest.mark.asyncio
async def test_oauth_get_access_token_async_refresh_failure(monkeypatch, db, test_user):
    integration = oauth_service.save_integration(
        db,
        user_id=test_user.id,
        integration_type="gmail",
        access_token="old-access",
        refresh_token="refresh-token",
        expires_in=1,
    )
    integration.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.add(integration)
    db.commit()

    async def _refresh_fail(*args, **kwargs):
        return False

    monkeypatch.setattr(oauth_service, "refresh_token_async", _refresh_fail)
    token = await oauth_service.get_access_token_async(db, test_user.id, "gmail")
    assert token is None


def test_oauth_auth_url_builders():
    gmail = oauth_service.get_gmail_auth_url("https://app/callback", "state-1")
    parsed = parse_qs(urlparse(gmail).query)
    assert parsed["state"] == ["state-1"]
    assert "gmail.readonly" in parsed["scope"][0]

    gcal = oauth_service.get_google_calendar_auth_url("https://app/callback", "state-2")
    assert "calendar.events" in parse_qs(urlparse(gcal).query)["scope"][0]

    gcp = oauth_service.get_gcp_auth_url("https://app/callback", "state-3")
    assert "cloud-platform.read-only" in parse_qs(urlparse(gcp).query)["scope"][0]

    zoom = oauth_service.get_zoom_auth_url("https://app/zoom-callback", "z-state")
    assert parse_qs(urlparse(zoom).query)["state"] == ["z-state"]


@pytest.mark.asyncio
async def test_oauth_exchange_and_user_info_http_paths(monkeypatch):
    monkeypatch.setattr(oauth_service.httpx, "AsyncClient", lambda: _AsyncClient())

    gmail_tokens = await oauth_service.exchange_gmail_code("code", "https://callback")
    gmail_user = await oauth_service.get_gmail_user_info("tok")
    assert gmail_tokens["access_token"] == "a1"
    assert gmail_user["email"] == "user@example.com"

    zoom_tokens = await oauth_service.exchange_zoom_code("code", "https://callback")
    zoom_user = await oauth_service.get_zoom_user_info("tok")
    assert zoom_tokens["access_token"] == "a1"
    assert zoom_user["email"] == "user@example.com"

    monkeypatch.setattr(oauth_service.httpx, "AsyncClient", lambda: _AsyncClient(fail=True))
    assert await oauth_service.refresh_gmail_token("refresh") is None
    assert await oauth_service.refresh_zoom_token("refresh") is None


def test_oauth_refresh_token_success(monkeypatch, db, test_user):
    integration = UserIntegration(
        id=uuid4(),
        user_id=test_user.id,
        integration_type="gmail",
        access_token_encrypted=oauth_service.encrypt_token("old-access"),
        refresh_token_encrypted=oauth_service.encrypt_token("old-refresh"),
    )
    db.add(integration)
    db.commit()

    def _run_async_success(coro):
        coro.close()
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 120}

    monkeypatch.setattr(oauth_service, "run_async", _run_async_success)
    monkeypatch.setattr(oauth_service, "_log_token_refresh", lambda *args, **kwargs: None)
    ok = oauth_service.refresh_token(db, integration, "gmail")
    assert ok is True
    assert oauth_service.decrypt_token(integration.access_token_encrypted) == "new-access"
    assert oauth_service.decrypt_token(integration.refresh_token_encrypted) == "new-refresh"
    assert integration.token_expires_at is not None


def test_oauth_refresh_token_failure_alert(monkeypatch, db, test_user):
    integration = UserIntegration(
        id=uuid4(),
        user_id=test_user.id,
        integration_type="gmail",
        access_token_encrypted=oauth_service.encrypt_token("old-access"),
        refresh_token_encrypted=oauth_service.encrypt_token("old-refresh"),
    )
    db.add(integration)
    db.commit()

    alerts: list[tuple[str, str]] = []
    def _run_async_fail(coro):
        coro.close()
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(oauth_service, "run_async", _run_async_fail)
    monkeypatch.setattr(
        oauth_service,
        "_create_token_refresh_alert",
        lambda _db, user_id, integration_type, error_msg: alerts.append((integration_type, error_msg)),
    )
    ok = oauth_service.refresh_token(db, integration, "gmail")
    assert ok is False
    assert alerts == [("gmail", "refresh failed")]


@pytest.mark.asyncio
async def test_oauth_refresh_token_async_and_alert_paths(monkeypatch, db, test_user, test_org):
    original_create_alert = oauth_service._create_token_refresh_alert

    integration = UserIntegration(
        id=uuid4(),
        user_id=test_user.id,
        integration_type="google_calendar",
        access_token_encrypted=oauth_service.encrypt_token("old-access"),
        refresh_token_encrypted=oauth_service.encrypt_token("old-refresh"),
    )
    db.add(integration)
    db.commit()

    async def _refresh_ok(token):
        return {"access_token": "new-access", "expires_in": 90}

    monkeypatch.setattr(oauth_service, "refresh_google_calendar_token", _refresh_ok)
    monkeypatch.setattr(oauth_service, "_create_token_refresh_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(oauth_service, "_log_token_refresh", lambda *args, **kwargs: None)
    ok = await oauth_service.refresh_token_async(db, integration, "google_calendar")
    assert ok is True
    assert oauth_service.decrypt_token(integration.access_token_encrypted) == "new-access"

    async def _refresh_boom(token):
        raise RuntimeError("boom")

    monkeypatch.setattr(oauth_service, "refresh_google_calendar_token", _refresh_boom)
    alerts: list[str] = []
    monkeypatch.setattr(oauth_service, "_create_token_refresh_alert", lambda *args, **kwargs: alerts.append("alerted"))
    ok = await oauth_service.refresh_token_async(db, integration, "google_calendar")
    assert ok is False
    assert alerts == ["alerted"]

    alert_calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.alert_service.record_alert_isolated",
        lambda **kwargs: alert_calls.append(kwargs),
    )
    monkeypatch.setattr(oauth_service, "_create_token_refresh_alert", original_create_alert)
    oauth_service._create_token_refresh_alert(db, test_user.id, "gmail", "refresh failure")
    assert alert_calls
