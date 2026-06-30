"""Tests for Authentication."""

import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.fixture
def rate_limiter_reset():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


def test_auth_error_response_sets_masked_account_hint_cookie():
    from app.services.auth_callback_service import (
        AUTH_ERROR_ACCOUNT_HINT_COOKIE,
        _error_response,
    )
    from app.services.audit_service import hash_email

    response = _error_response(
        "no_membership",
        return_to="app",
        selected_email="renamed.member@example.com",
    )

    location = response.headers["location"]
    assert "renamed.member" not in location
    assert hash_email("renamed.member@example.com") not in location

    cookies = _response_cookies(response)
    assert cookies[AUTH_ERROR_ACCOUNT_HINT_COOKIE].value == "ren...@example.com"


def test_auth_error_response_clears_account_hint_without_selected_email():
    from app.services.auth_callback_service import AUTH_ERROR_ACCOUNT_HINT_COOKIE, _error_response

    response = _error_response("state_expired", return_to="app")

    cookies = _response_cookies(response)
    assert AUTH_ERROR_ACCOUNT_HINT_COOKIE in cookies
    assert cookies[AUTH_ERROR_ACCOUNT_HINT_COOKIE]["max-age"] == "0"


def test_session_revocation_routes_are_rate_limit_exempt():
    # Make sure we load the routes so the decorators execute and register them in the limiter
    import app.routers.auth  # noqa
    from app.core.rate_limit import limiter

    # Depending on test environment (FailOpenLimiter vs Limiter), _exempt_routes may be on a wrapped object
    if hasattr(limiter, "_redis"):
        exempt_routes = getattr(limiter._redis, "_exempt_routes", set())
    else:
        exempt_routes = getattr(limiter, "_exempt_routes", set())

    assert "app.routers.auth.revoke_session" in exempt_routes
    assert "app.routers.auth.revoke_all_sessions" in exempt_routes
    assert "app.routers.auth.logout" in exempt_routes


def _response_cookies(response) -> SimpleCookie:
    cookies = SimpleCookie()
    for key, value in response.raw_headers:
        if key.lower() == b"set-cookie":
            cookies.load(value.decode())
    return cookies


@pytest.mark.asyncio
async def test_login_redirects_to_google(client: AsyncClient):
    """GET /auth/google/login should redirect to Google."""
    response = await client.get("/auth/google/login", follow_redirects=False)
    # Should redirect (302 or 307)
    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location or "google" in location.lower()
    params = parse_qs(urlparse(location).query)
    assert params["prompt"] == ["select_account"]


@pytest.mark.asyncio
async def test_login_preserves_invite_id_in_oauth_state(client: AsyncClient):
    """Invite SSO should carry the clicked invite through Google's redirect."""
    invite_id = uuid4()

    response = await client.get(
        f"/auth/google/login?return_to=app&invite_id={invite_id}",
        follow_redirects=False,
    )

    assert response.status_code in [302, 307]
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    assert "oauth_state" in cookies
    payload = json.loads(cookies["oauth_state"].value)
    assert payload["invite_id"] == str(invite_id)


@pytest.mark.asyncio
async def test_me_returns_user_info(client: AsyncClient):
    """GET /auth/me should require authentication."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authed_me_returns_user(authed_client: AsyncClient, test_auth):
    """Authenticated /me should return user info."""
    response = await authed_client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert "email" in data


@pytest.mark.asyncio
async def test_authed_me_returns_org_display_name(authed_client: AsyncClient, db, test_auth):
    """Authenticated /me should include org display name."""
    test_auth.org.signature_company_name = "Acme Surrogacy"
    db.flush()

    response = await authed_client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["org_display_name"] == "Acme Surrogacy"


@pytest.mark.asyncio
async def test_authed_me_profile_complete_false_when_title_missing(
    authed_client: AsyncClient, db, test_auth
):
    """Profile is incomplete when title is missing."""
    test_auth.user.title = None
    db.flush()

    response = await authed_client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_complete"] is False


@pytest.mark.asyncio
async def test_authed_me_profile_complete_true_when_display_name_and_title_set(
    authed_client: AsyncClient, db, test_auth
):
    """Profile is complete when display_name and title are set."""
    test_auth.user.title = "Case Manager"
    db.flush()

    response = await authed_client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_complete"] is True


def test_existing_google_identity_refreshes_email_for_active_member(db, test_org):
    """A Workspace email rename should not strand an active member."""
    from app.db.enums import AuditEventType, AuthProvider, Role
    from app.db.models import AuditLog, AuthIdentity, Membership, User, UserSession
    from app.services import auth_service
    from app.services.audit_service import hash_email
    from app.services.google_oauth import GoogleUserInfo

    user = User(
        id=uuid4(),
        email="katievanderbur@example.com",
        display_name="Katie Vanderbur",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        is_active=True,
    )
    identity = AuthIdentity(
        id=uuid4(),
        user_id=user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="stable-google-subject",
        email=user.email,
    )
    db.add_all([membership, identity])
    db.commit()

    google_user = GoogleUserInfo(
        sub="stable-google-subject",
        email="katiev@example.com",
        name="Katie Vanderbur",
        picture="https://example.com/avatar.png",
        hd="example.com",
    )

    token, error = auth_service.resolve_user_and_create_session(db, google_user)

    assert token is not None
    assert error is None
    db.refresh(user)
    db.refresh(identity)
    assert user.email == "katiev@example.com"
    assert identity.email == "katiev@example.com"
    assert user.display_name == "Katie Vanderbur"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user.id,
            UserSession.organization_id == test_org.id,
        )
        .count()
        == 1
    )

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type == AuditEventType.AUTH_IDENTITY_EMAIL_REFRESHED.value,
            AuditLog.target_id == user.id,
        )
        .one()
    )
    assert audit_log.details == {
        "provider": AuthProvider.GOOGLE.value,
        "old_email_hash": hash_email("katievanderbur@example.com"),
        "new_email_hash": hash_email("katiev@example.com"),
    }


def test_existing_google_identity_email_refresh_rejects_claimed_email(db, test_org):
    """An email refresh must not take an email already attached to another user."""
    from app.db.enums import AuthProvider, Role
    from app.db.models import AuthIdentity, Membership, User
    from app.services import auth_service
    from app.services.google_oauth import GoogleUserInfo

    member = User(
        id=uuid4(),
        email="active.member.old@example.com",
        display_name="Active Member",
        token_version=1,
        is_active=True,
    )
    claimed = User(
        id=uuid4(),
        email="claimed.member@example.com",
        display_name="Claimed Member",
        token_version=1,
        is_active=True,
    )
    db.add_all([member, claimed])
    db.flush()
    membership = Membership(
        id=uuid4(),
        user_id=member.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        is_active=True,
    )
    identity = AuthIdentity(
        id=uuid4(),
        user_id=member.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="stable-google-subject-conflict",
        email=member.email,
    )
    db.add_all([membership, identity])
    db.commit()

    google_user = GoogleUserInfo(
        sub="stable-google-subject-conflict",
        email="claimed.member@example.com",
        name="Active Member",
        picture=None,
        hd="example.com",
    )

    token, error = auth_service.resolve_user_and_create_session(db, google_user)

    assert token is None
    assert error == "no_membership"
    db.refresh(member)
    db.refresh(identity)
    assert member.email == "active.member.old@example.com"
    assert identity.email == "active.member.old@example.com"


def test_existing_google_identity_email_refresh_rejects_deprovisioned_user(db):
    """A stale identity row must not reactivate a removed member without an invite."""
    from app.db.enums import AuthProvider
    from app.db.models import AuthIdentity, User, UserSession
    from app.services import auth_service
    from app.services.google_oauth import GoogleUserInfo

    removed_user = User(
        id=uuid4(),
        email="removed.member.old@example.com",
        display_name="Removed Member",
        token_version=2,
        is_active=False,
    )
    db.add(removed_user)
    db.flush()
    identity = AuthIdentity(
        id=uuid4(),
        user_id=removed_user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="stale-google-subject",
        email=removed_user.email,
    )
    db.add(identity)
    db.commit()

    google_user = GoogleUserInfo(
        sub="stale-google-subject",
        email="removed.member.new@example.com",
        name="Removed Member",
        picture=None,
        hd="example.com",
    )

    token, error = auth_service.resolve_user_and_create_session(db, google_user)

    assert token is None
    assert error == "no_membership"
    db.refresh(removed_user)
    db.refresh(identity)
    assert removed_user.is_active is False
    assert removed_user.email == "removed.member.old@example.com"
    assert identity.email == "removed.member.old@example.com"
    assert db.query(UserSession).filter(UserSession.user_id == removed_user.id).count() == 0


@pytest.mark.asyncio
async def test_google_callback_rate_limited(client: AsyncClient, rate_limiter_reset):
    for _ in range(5):
        response = await client.get("/auth/google/callback", follow_redirects=False)
        assert response.status_code != 429

    blocked = await client.get("/auth/google/callback", follow_redirects=False)
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_google_login_rate_limit_uses_forwarded_client_ip(
    client: AsyncClient, monkeypatch, rate_limiter_reset
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)

    for _ in range(5):
        response = await client.get(
            "/auth/google/login",
            follow_redirects=False,
            headers={"X-Forwarded-For": "203.0.113.10, 34.54.23.120"},
        )
        assert response.status_code != 429

    response = await client.get(
        "/auth/google/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "198.51.100.22, 34.54.23.120"},
    )
    assert response.status_code != 429


