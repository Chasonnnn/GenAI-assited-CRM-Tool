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
