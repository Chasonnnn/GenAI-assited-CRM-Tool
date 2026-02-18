import json
from http.cookies import SimpleCookie

import pytest

from app.core.deps import COOKIE_NAME
from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from app.core.security import create_session_token
from app.services import session_service


def _get_cookie_payload(response, cookie_name: str) -> dict:
    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    morsel = cookie.get(cookie_name)
    assert morsel, f"Missing cookie {cookie_name}"
    return json.loads(morsel.value)


@pytest.mark.asyncio
async def test_google_login_return_to_allowlist(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OPS_FRONTEND_URL", "https://ops.example.com")

    response = await client.get("/auth/google/login?return_to=ops", follow_redirects=False)
    assert response.status_code == 302
    payload = _get_cookie_payload(response, "oauth_state")
    assert payload["return_to"] == "ops"

    response = await client.get("/auth/google/login?return_to=evil", follow_redirects=False)
    assert response.status_code == 302
    payload = _get_cookie_payload(response, "oauth_state")
    assert payload["return_to"] == "app"


@pytest.mark.asyncio
async def test_dev_login_sets_cookie_domain_for_session_and_csrf(
    client, db, test_user, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".surrogacyforce.com")

    response = await client.post(
        f"/dev/login-as/{test_user.id}",
        headers={"X-Dev-Secret": settings.DEV_SECRET},
    )
    assert response.status_code == 200

    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(h for h in cookie_headers if h.startswith(f"{COOKIE_NAME}="))
    csrf_cookie = next(h for h in cookie_headers if h.startswith(f"{CSRF_COOKIE_NAME}="))

    assert "domain=.surrogacyforce.com" in session_cookie.lower()
    assert "domain=.surrogacyforce.com" in csrf_cookie.lower()


@pytest.mark.asyncio
async def test_logout_clears_cookie_domain_for_session_and_csrf(authed_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".surrogacyforce.com")

    response = await authed_client.post("/auth/logout")
    assert response.status_code == 200

    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(h for h in cookie_headers if h.startswith(f"{COOKIE_NAME}="))
    csrf_cookie = next(h for h in cookie_headers if h.startswith(f"{CSRF_COOKIE_NAME}="))

    assert "domain=.surrogacyforce.com" in session_cookie.lower()
    assert "domain=.surrogacyforce.com" in csrf_cookie.lower()


@pytest.mark.asyncio
async def test_platform_me_requires_admin_flag(authed_client):
    response = await authed_client.get("/platform/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_platform_me_allows_admin_flag(authed_client, db, test_user):
    from app.core.config import settings

    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.get("/platform/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["is_platform_admin"] is True
    assert data["support_session_allow_read_only"] is settings.SUPPORT_SESSION_ALLOW_READ_ONLY


@pytest.mark.asyncio
async def test_platform_me_allows_admin_without_membership(client, db, test_org):
    from app.db.models import User
    from app.db.enums import Role

    user = User(
        email="platform.admin@test.com",
        display_name="Platform Admin",
        token_version=1,
        is_active=True,
        is_platform_admin=True,
    )
    db.add(user)
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=test_org.id, token=token)

    client.cookies.set(COOKIE_NAME, token)
    csrf_token = generate_csrf_token()
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)

    response = await client.get("/platform/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user.email
    assert data["is_platform_admin"] is True
