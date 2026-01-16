"""Tests for organization settings with portal domains."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_org_settings_sets_portal_domain(
    authed_client: AsyncClient,
    test_org,
    db,
):
    payload = {"portal_domain": "https://Portal.EWIFamilyGlobal.com/"}
    response = await authed_client.patch("/settings/organization", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["portal_domain"] == "portal.ewifamilyglobal.com"

    db.refresh(test_org)
    assert test_org.portal_domain == "portal.ewifamilyglobal.com"


@pytest.mark.asyncio
async def test_booking_link_uses_org_portal_domain(
    authed_client: AsyncClient,
    test_org,
    db,
):
    test_org.portal_domain = "portal.ewifamilyglobal.com"
    db.commit()

    response = await authed_client.get("/appointments/booking-link")
    assert response.status_code == 200
    data = response.json()
    assert data["full_url"].startswith("https://portal.ewifamilyglobal.com/book/")
