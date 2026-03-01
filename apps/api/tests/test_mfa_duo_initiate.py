import pytest


@pytest.fixture
def rate_limiter_reset():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_duo_initiate_prefers_ops_return_to(authed_client, db, test_org, monkeypatch):
    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    monkeypatch.setattr(settings, "ENV", "prod", raising=False)
    monkeypatch.setattr(settings, "FRONTEND_URL", "", raising=False)
    test_org.slug = "ewi"
    db.commit()
    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    captured = {}

    def fake_create_auth_url(*, user_id, username, state, redirect_uri=None):
        captured["redirect_uri"] = redirect_uri
        return "https://duo.example.com/auth"

    monkeypatch.setattr(duo_service, "create_auth_url", fake_create_auth_url)

    response = await authed_client.post(
        "/mfa/duo/initiate?return_to=ops",
        headers={"host": "ewi.surrogacyforce.com"},
    )
    assert response.status_code == 200
    assert captured["redirect_uri"] == "https://ops.surrogacyforce.com/auth/duo/callback"


@pytest.mark.asyncio
async def test_duo_initiate_ignores_invalid_return_to(authed_client, db, test_org, monkeypatch):
    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    monkeypatch.setattr(settings, "ENV", "prod", raising=False)
    monkeypatch.setattr(settings, "FRONTEND_URL", "", raising=False)
    test_org.slug = "ewi"
    db.commit()
    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    captured = {}

    def fake_create_auth_url(*, user_id, username, state, redirect_uri=None):
        captured["redirect_uri"] = redirect_uri
        return "https://duo.example.com/auth"

    monkeypatch.setattr(duo_service, "create_auth_url", fake_create_auth_url)

    response = await authed_client.post(
        "/mfa/duo/initiate?return_to=evil",
        headers={"host": "ewi.surrogacyforce.com"},
    )
    assert response.status_code == 200
    assert captured["redirect_uri"] == "https://ewi.surrogacyforce.com/auth/duo/callback"


@pytest.mark.asyncio
async def test_duo_initiate_rate_limited_after_five_attempts(
    authed_client,
    monkeypatch,
    rate_limiter_reset,
):
    from app.services import duo_service

    monkeypatch.setattr(duo_service, "is_available", lambda: True)
    monkeypatch.setattr(
        duo_service,
        "create_auth_url",
        lambda **_kwargs: "https://duo.example.com/auth",
    )

    for _ in range(5):
        response = await authed_client.post("/mfa/duo/initiate")
        assert response.status_code == 200, response.text

    blocked = await authed_client.post("/mfa/duo/initiate")
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_duo_callback_rate_limited_after_five_attempts(
    authed_client,
    monkeypatch,
    rate_limiter_reset,
):
    from app.services import duo_service

    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    for _ in range(5):
        response = await authed_client.post(
            "/mfa/duo/callback",
            json={"code": "duo-code", "state": "state-1"},
        )
        assert response.status_code == 400, response.text

    blocked = await authed_client.post(
        "/mfa/duo/callback",
        json={"code": "duo-code", "state": "state-1"},
    )
    assert blocked.status_code == 429
