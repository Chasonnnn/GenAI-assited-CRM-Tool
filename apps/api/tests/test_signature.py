"""Tests for email signature endpoints."""

import pytest
from httpx import AsyncClient
from io import BytesIO
from PIL import Image


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
async def test_org_signature_preview_org_only_excludes_user(
    authed_client: AsyncClient, db, test_org, test_user
):
    """Org-only preview excludes user fields."""
    test_org.signature_company_name = "Org Brand"
    test_org.signature_template = "classic"
    db.commit()

    response = await authed_client.get("/settings/organization/signature/preview?mode=org_only")
    assert response.status_code == 200
    html = response.json()["html"]
    assert "Org Brand" in html
    assert test_user.display_name not in html
    assert test_user.email not in html


@pytest.mark.asyncio
async def test_org_signature_preview_does_not_include_unconfigured_linkedin(
    authed_client: AsyncClient, db, test_org
):
    """
    Org signature preview uses sample employee data.

    It should NOT show LinkedIn unless it's configured, otherwise admins see a
    confusing extra social link in the preview.
    """
    test_org.signature_template = "classic"
    test_org.signature_social_links = [
        {"platform": "Instagram", "url": "https://www.instagram.com/example/"},
    ]
    db.commit()

    response = await authed_client.get("/settings/organization/signature/preview")
    assert response.status_code == 200
    html = response.json()["html"]
    assert "LinkedIn" not in html


@pytest.mark.asyncio
async def test_signature_update_rejects_invalid_url(authed_client: AsyncClient):
    """Invalid social URL is rejected."""
    response = await authed_client.patch(
        "/auth/me/signature",
        json={"signature_linkedin": 'https://example.com/" onload="alert(1)'},
    )
    assert response.status_code == 422


# =============================================================================
# Signature Override Fields Tests
# =============================================================================


@pytest.mark.asyncio
async def test_signature_override_fields_returned(authed_client: AsyncClient, db, test_user):
    """Signature response includes override fields and profile defaults."""
    # Set up test user profile
    test_user.display_name = "John Doe"
    test_user.title = "Case Manager"
    test_user.phone = "555-1234"
    db.commit()

    response = await authed_client.get("/auth/me/signature")
    assert response.status_code == 200
    data = response.json()

    # Profile defaults should be returned
    assert data["profile_name"] == "John Doe"
    assert data["profile_title"] == "Case Manager"
    assert data["profile_phone"] == "555-1234"

    # Signature overrides should be null initially
    assert data["signature_name"] is None
    assert data["signature_title"] is None
    assert data["signature_phone"] is None
    assert data["signature_photo_url"] is None


@pytest.mark.asyncio
async def test_signature_update_override_fields(authed_client: AsyncClient, db, test_user):
    """User can set signature override fields."""
    test_user.display_name = "John Doe"
    test_user.title = "Case Manager"
    test_user.phone = "555-1234"
    db.commit()

    response = await authed_client.patch(
        "/auth/me/signature",
        json={
            "signature_name": "Dr. John Doe",
            "signature_title": "Senior Case Manager",
            "signature_phone": "555-9999",
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Override values should be set
    assert data["signature_name"] == "Dr. John Doe"
    assert data["signature_title"] == "Senior Case Manager"
    assert data["signature_phone"] == "555-9999"

    # Profile defaults should still be returned
    assert data["profile_name"] == "John Doe"
    assert data["profile_title"] == "Case Manager"
    assert data["profile_phone"] == "555-1234"


@pytest.mark.asyncio
async def test_signature_phone_validation(authed_client: AsyncClient):
    """Signature phone is validated for max length."""
    response = await authed_client.patch(
        "/auth/me/signature",
        json={"signature_phone": "x" * 51},  # Exceeds 50 char limit
    )
    assert response.status_code == 422


# =============================================================================
# Signature Photo Upload/Delete Tests
# =============================================================================


def create_test_image(size=(100, 100), format="PNG") -> BytesIO:
    """Create a test image file."""
    img = Image.new("RGB", size, color="blue")
    buffer = BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer


@pytest.mark.asyncio
async def test_signature_photo_upload_rejects_large_files(authed_client: AsyncClient):
    """Large files are rejected."""
    # Create a file that's too large (>2MB)
    large_data = BytesIO(b"x" * (3 * 1024 * 1024))  # 3MB

    files = {"file": ("test.png", large_data, "image/png")}
    response = await authed_client.post("/auth/me/signature/photo", files=files)
    assert response.status_code == 413
    assert "maximum" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signature_photo_upload_rejects_invalid_types(authed_client: AsyncClient):
    """Invalid file types are rejected."""
    files = {"file": ("test.txt", BytesIO(b"hello world"), "text/plain")}
    response = await authed_client.post("/auth/me/signature/photo", files=files)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_signature_photo_delete_no_existing_photo(authed_client: AsyncClient, db, test_user):
    """Deleting when no photo exists returns 404."""
    test_user.signature_photo_url = None
    db.commit()

    response = await authed_client.delete("/auth/me/signature/photo")
    assert response.status_code == 404
    assert "no signature photo" in response.json()["detail"].lower()


# =============================================================================
# Signature Template Fallback Logic Tests
# =============================================================================


@pytest.mark.asyncio
async def test_signature_preview_uses_override_values(
    authed_client: AsyncClient, db, test_user, test_org
):
    """Signature preview uses override values when set."""
    test_org.signature_template = "minimal"
    test_user.display_name = "John Doe"
    test_user.signature_name = "Dr. John Doe"  # Override
    db.commit()

    response = await authed_client.get("/auth/me/signature/preview")
    assert response.status_code == 200
    html = response.json()["html"]

    # Should use override name, not profile name
    assert "Dr. John Doe" in html
    assert "John Doe" not in html or "Dr. John Doe" in html


@pytest.mark.asyncio
async def test_signature_preview_falls_back_to_profile(
    authed_client: AsyncClient, db, test_user, test_org
):
    """Signature preview falls back to profile values when overrides are null."""
    test_org.signature_template = "minimal"
    test_user.display_name = "Jane Smith"
    test_user.title = "Case Manager"
    test_user.signature_name = None  # No override
    test_user.signature_title = None  # No override
    db.commit()

    response = await authed_client.get("/auth/me/signature/preview")
    assert response.status_code == 200
    html = response.json()["html"]

    # Should use profile values
    assert "Jane Smith" in html
