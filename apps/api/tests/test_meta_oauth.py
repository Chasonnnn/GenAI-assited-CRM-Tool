"""Tests for Meta OAuth integration."""

import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.services.meta_oauth_service import REQUIRED_SCOPES, PaginatedResult


@pytest.mark.asyncio
async def test_meta_oauth_connect_sets_state_cookie_and_returns_auth_url(
    authed_client: AsyncClient, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "META_APP_ID", "test-meta-app-id")
    monkeypatch.setattr(
        settings,
        "META_OAUTH_REDIRECT_URI",
        "https://test/integrations/meta/callback",
        raising=False,
    )

    response = await authed_client.get("/integrations/meta/connect")
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
    cookie_value = cookie.get("meta_oauth_state")
    assert cookie_value
    payload = json.loads(cookie_value.value)
    assert payload["state"] == state
    assert "ua_hash" in payload


@pytest.mark.asyncio
async def test_meta_oauth_callback_requires_state_cookie(authed_client: AsyncClient):
    response = await authed_client.get(
        "/integrations/meta/callback",
        params={"code": "dummy", "state": "dummy"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "error=invalid_state" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_meta_oauth_callback_rejects_missing_scopes(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.core.config import settings
    from app.services import meta_oauth_service

    monkeypatch.setattr(settings, "META_APP_ID", "test-meta-app-id")
    monkeypatch.setattr(
        settings,
        "META_OAUTH_REDIRECT_URI",
        "https://test/integrations/meta/callback",
        raising=False,
    )

    async def fake_exchange_code(code: str):
        return {"access_token": "short-token"}

    async def fake_exchange_long_lived_token(short_token: str):
        return {"access_token": "long-token", "expires_in": 3600}

    async def fake_get_user_info(token: str):
        return {"id": "123", "name": "Meta User"}

    async def fake_debug_token(token: str):
        return ["ads_management"]  # Missing required scopes

    monkeypatch.setattr(meta_oauth_service, "exchange_code_for_token", fake_exchange_code)
    monkeypatch.setattr(
        meta_oauth_service,
        "exchange_for_long_lived_token",
        fake_exchange_long_lived_token,
    )
    monkeypatch.setattr(meta_oauth_service, "get_user_info", fake_get_user_info)
    monkeypatch.setattr(meta_oauth_service, "debug_token", fake_debug_token)

    connect = await authed_client.get("/integrations/meta/connect")
    assert connect.status_code == 200
    state = parse_qs(urlparse(connect.json()["auth_url"]).query)["state"][0]

    callback = await authed_client.get(
        "/integrations/meta/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert "error=missing_scopes" in callback.headers.get("location", "")

    from app.db.models import MetaOAuthConnection

    connection = (
        db.query(MetaOAuthConnection)
        .filter(MetaOAuthConnection.organization_id == test_auth.org.id)
        .first()
    )
    assert connection is None


@pytest.mark.asyncio
async def test_meta_oauth_callback_creates_connection(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.core.config import settings
    from app.core.encryption import decrypt_token
    from app.services import meta_oauth_service

    monkeypatch.setattr(settings, "META_APP_ID", "test-meta-app-id")
    monkeypatch.setattr(
        settings,
        "META_OAUTH_REDIRECT_URI",
        "https://test/integrations/meta/callback",
        raising=False,
    )

    async def fake_exchange_code(code: str):
        return {"access_token": "short-token"}

    async def fake_exchange_long_lived_token(short_token: str):
        return {"access_token": "long-token", "expires_in": 3600}

    async def fake_get_user_info(token: str):
        return {"id": "123", "name": "Meta User"}

    async def fake_debug_token(token: str):
        return list(REQUIRED_SCOPES)

    monkeypatch.setattr(meta_oauth_service, "exchange_code_for_token", fake_exchange_code)
    monkeypatch.setattr(
        meta_oauth_service,
        "exchange_for_long_lived_token",
        fake_exchange_long_lived_token,
    )
    monkeypatch.setattr(meta_oauth_service, "get_user_info", fake_get_user_info)
    monkeypatch.setattr(meta_oauth_service, "debug_token", fake_debug_token)

    connect = await authed_client.get("/integrations/meta/connect")
    assert connect.status_code == 200
    state = parse_qs(urlparse(connect.json()["auth_url"]).query)["state"][0]

    callback = await authed_client.get(
        "/integrations/meta/callback",
        params={"code": "dummy", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    # Successful callback redirects to asset selection
    assert "step=select-assets" in callback.headers.get("location", "")

    from app.db.models import MetaOAuthConnection

    connection = (
        db.query(MetaOAuthConnection)
        .filter(MetaOAuthConnection.organization_id == test_auth.org.id)
        .first()
    )
    assert connection is not None
    assert connection.meta_user_id == "123"
    assert connection.meta_user_name == "Meta User"
    assert decrypt_token(connection.access_token_encrypted) == "long-token"
    assert set(connection.granted_scopes) >= REQUIRED_SCOPES


@pytest.mark.asyncio
async def test_meta_oauth_connect_assets_overwrite_flow(
    authed_client: AsyncClient, db, test_auth, monkeypatch
):
    from app.core.encryption import decrypt_token, encrypt_token
    from app.services import meta_oauth_service
    from app.db.models import MetaOAuthConnection, MetaAdAccount, MetaPageMapping

    async def fake_fetch_user_pages(token: str, cursor: str | None = None):
        return PaginatedResult(
            data=[{"id": "page_1", "name": "Page One", "access_token": "page-token"}],
            next_cursor=None,
        )

    async def fake_fetch_user_ad_accounts(token: str, cursor: str | None = None):
        return PaginatedResult(
            data=[{"id": "act_1", "name": "Account One"}],
            next_cursor=None,
        )

    async def fake_subscribe_page_to_leadgen(token: str, page_id: str):
        return True

    monkeypatch.setattr(meta_oauth_service, "fetch_user_pages", fake_fetch_user_pages)
    monkeypatch.setattr(meta_oauth_service, "fetch_user_ad_accounts", fake_fetch_user_ad_accounts)
    monkeypatch.setattr(
        meta_oauth_service, "subscribe_page_to_leadgen", fake_subscribe_page_to_leadgen
    )

    conn_a = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="111",
        meta_user_name="Conn A",
        access_token_encrypted=encrypt_token("token-a"),
        token_expires_at=None,
        granted_scopes=list(REQUIRED_SCOPES),
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )
    conn_b = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="222",
        meta_user_name="Conn B",
        access_token_encrypted=encrypt_token("token-b"),
        token_expires_at=None,
        granted_scopes=list(REQUIRED_SCOPES),
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )
    db.add_all([conn_a, conn_b])
    db.flush()

    account = MetaAdAccount(
        organization_id=test_auth.org.id,
        ad_account_external_id="act_1",
        ad_account_name="Account One",
        oauth_connection_id=conn_a.id,
        is_active=True,
    )
    db.add(account)
    db.flush()
    db.commit()

    response = await authed_client.post(
        f"/integrations/meta/connections/{conn_b.id}/connect-assets",
        json={"ad_account_ids": ["act_1"], "page_ids": ["page_1"], "overwrite_existing": False},
    )
    assert response.status_code == 409

    response = await authed_client.post(
        f"/integrations/meta/connections/{conn_b.id}/connect-assets",
        json={"ad_account_ids": ["act_1"], "page_ids": ["page_1"], "overwrite_existing": True},
    )
    assert response.status_code == 200

    db.refresh(account)
    assert account.oauth_connection_id == conn_b.id

    page_mapping = (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.organization_id == test_auth.org.id,
            MetaPageMapping.page_id == "page_1",
        )
        .first()
    )
    assert page_mapping is not None
    assert page_mapping.oauth_connection_id == conn_b.id
    assert decrypt_token(page_mapping.access_token_encrypted) == "page-token"


@pytest.mark.asyncio
async def test_meta_oauth_disconnect_unlinks_assets(authed_client: AsyncClient, db, test_auth):
    from app.core.encryption import encrypt_token
    from app.db.models import MetaOAuthConnection, MetaAdAccount, MetaPageMapping

    conn = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="333",
        meta_user_name="Conn C",
        access_token_encrypted=encrypt_token("token-c"),
        token_expires_at=None,
        granted_scopes=list(REQUIRED_SCOPES),
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )
    db.add(conn)
    db.flush()

    account = MetaAdAccount(
        organization_id=test_auth.org.id,
        ad_account_external_id="act_2",
        ad_account_name="Account Two",
        oauth_connection_id=conn.id,
        is_active=True,
    )
    page = MetaPageMapping(
        organization_id=test_auth.org.id,
        page_id="page_2",
        page_name="Page Two",
        oauth_connection_id=conn.id,
        is_active=True,
    )
    db.add_all([account, page])
    db.flush()
    db.commit()

    response = await authed_client.delete(
        f"/integrations/meta/connections/{conn.id}",
    )
    assert response.status_code == 200

    db.refresh(conn)
    db.refresh(account)
    db.refresh(page)
    assert conn.is_active is False
    assert account.oauth_connection_id is None
    assert page.oauth_connection_id is None


@pytest.mark.asyncio
async def test_meta_oauth_list_connections(authed_client: AsyncClient, db, test_auth):
    from app.core.encryption import encrypt_token
    from app.db.models import MetaOAuthConnection

    conn = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="444",
        meta_user_name="Test User",
        access_token_encrypted=encrypt_token("token-test"),
        token_expires_at=None,
        granted_scopes=list(REQUIRED_SCOPES),
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )
    db.add(conn)
    db.commit()

    response = await authed_client.get("/integrations/meta/connections")
    assert response.status_code == 200
    data = response.json()
    assert "connections" in data
    assert len(data["connections"]) >= 1
    assert any(c["meta_user_id"] == "444" for c in data["connections"])
