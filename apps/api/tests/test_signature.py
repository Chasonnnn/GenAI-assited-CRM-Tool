"""Tests for email signature endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signature_read_only_org_fields(authed_client: AsyncClient, db, test_org):
    """User signature response includes org branding fields."""
    test_org.signature_company_name = "Acme Health"
    test_org.signature_address = "123 Main St"
    test_org.signature_phone = "555-0100"
    test_org.signature_website = "https://acme.example"
    db.commit()

    response = await authed_client.get("/auth/me/signature")
    assert response.status_code == 200
    data = response.json()
    assert data["org_signature_company_name"] == "Acme Health"
    assert data["org_signature_address"] == "123 Main St"
    assert data["org_signature_phone"] == "555-0100"
    assert data["org_signature_website"] == "https://acme.example"


@pytest.mark.asyncio
async def test_signature_preview_returns_html(authed_client: AsyncClient, db, test_org):
    """Signature preview returns HTML."""
    test_org.signature_template = "minimal"
    db.commit()

    response = await authed_client.get("/auth/me/signature/preview")
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<table" in html


@pytest.mark.asyncio
async def test_signature_update_rejects_invalid_url(authed_client: AsyncClient):
    """Invalid social URL is rejected."""
    response = await authed_client.patch(
        "/auth/me/signature",
        json={"signature_linkedin": 'https://example.com/" onload="alert(1)'},
    )
    assert response.status_code == 422
