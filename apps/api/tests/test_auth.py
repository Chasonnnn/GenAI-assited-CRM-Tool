"""Tests for Authentication."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_redirects_to_google(client: AsyncClient):
    """GET /auth/google/login should redirect to Google."""
    response = await client.get("/auth/google/login", follow_redirects=False)
    # Should redirect (302 or 307)
    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location or "google" in location.lower()


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
