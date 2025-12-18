"""Tests for Authentication."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_redirects_to_google(client: AsyncClient):
    """GET /auth/login should redirect to Google OAuth."""
    response = await client.get("/auth/login", follow_redirects=False)
    # Should redirect (302 or 307)
    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location or "google" in location.lower()


@pytest.mark.asyncio
async def test_protected_endpoint_requires_session(client: AsyncClient):
    """Protected endpoints should require authentication."""
    # /me requires session
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pipelines_requires_session(client: AsyncClient):
    """Pipelines endpoint requires authentication."""
    response = await client.get("/pipelines")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cases_requires_session(client: AsyncClient):
    """Cases endpoint requires authentication."""
    response = await client.get("/cases")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authed_me_returns_user(authed_client: AsyncClient, mock_session):
    """Authenticated /me should return user info."""
    response = await authed_client.get("/auth/me")
    # Should work with mocked session
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == mock_session.email
