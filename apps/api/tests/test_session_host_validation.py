import pytest


@pytest.mark.asyncio
async def test_session_host_validation_rejects_wrong_subdomain(
    authed_client, db, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await authed_client.get(
        "/auth/me",
        headers={"host": "other.surrogacyforce.com"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_session_host_validation_allows_matching_subdomain(
    authed_client, db, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await authed_client.get(
        "/auth/me",
        headers={"host": "ewi.surrogacyforce.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_session_host_validation_allows_localhost(authed_client, db, test_org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await authed_client.get(
        "/auth/me",
        headers={"host": "localhost"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_platform_admin_host_validation_rejects_wrong_subdomain(
    authed_client, db, test_user, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.get(
        "/platform/me",
        headers={"host": "other.surrogacyforce.com"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_oauth_callback_allows_api_host_with_external_referer(
    authed_client, db, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await authed_client.get(
        "/integrations/gmail/callback",
        params={"code": "dummy", "state": "dummy"},
        headers={
            "host": "api.surrogacyforce.com",
            "referer": "https://accounts.google.com/",
        },
        follow_redirects=False,
    )
    # Missing state cookie should redirect, not fail host validation.
    assert response.status_code == 302
