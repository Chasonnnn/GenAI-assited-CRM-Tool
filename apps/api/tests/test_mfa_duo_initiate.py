import pytest


@pytest.mark.asyncio
async def test_duo_initiate_prefers_ops_return_to(authed_client, monkeypatch):
    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(settings, "OPS_FRONTEND_URL", "https://ops.example.com")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com")
    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    captured = {}

    def fake_create_auth_url(*, user_id, username, state, redirect_uri=None):
        captured["redirect_uri"] = redirect_uri
        return "https://duo.example.com/auth"

    monkeypatch.setattr(duo_service, "create_auth_url", fake_create_auth_url)

    response = await authed_client.post("/mfa/duo/initiate?return_to=ops")
    assert response.status_code == 200
    assert captured["redirect_uri"] == "https://ops.example.com/auth/duo/callback"


@pytest.mark.asyncio
async def test_duo_initiate_ignores_invalid_return_to(authed_client, monkeypatch):
    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(settings, "OPS_FRONTEND_URL", "https://ops.example.com")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com")
    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    captured = {}

    def fake_create_auth_url(*, user_id, username, state, redirect_uri=None):
        captured["redirect_uri"] = redirect_uri
        return "https://duo.example.com/auth"

    monkeypatch.setattr(duo_service, "create_auth_url", fake_create_auth_url)

    response = await authed_client.post("/mfa/duo/initiate?return_to=evil")
    assert response.status_code == 200
    assert captured["redirect_uri"] == "https://app.example.com/auth/duo/callback"
