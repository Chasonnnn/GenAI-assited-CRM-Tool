"""Tests for organization settings and slug-based portal URLs."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_booking_link_uses_slug_based_domain(
    authed_client: AsyncClient,
    test_org,
    db,
    monkeypatch,
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await authed_client.get("/appointments/booking-link")
    assert response.status_code == 200
    data = response.json()
    assert data["full_url"].startswith("https://ewi.surrogacyforce.com/book/")


@pytest.mark.asyncio
async def test_booking_link_regenerate_keeps_existing_slug(
    authed_client: AsyncClient,
):
    created_response = await authed_client.get("/appointments/booking-link")
    assert created_response.status_code == 200
    created = created_response.json()

    refreshed_response = await authed_client.post("/appointments/booking-link/regenerate")
    assert refreshed_response.status_code == 200
    refreshed = refreshed_response.json()

    assert refreshed["public_slug"] == created["public_slug"]
    assert refreshed["full_url"] == created["full_url"]
