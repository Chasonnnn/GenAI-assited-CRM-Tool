"""Tests for email sending from cases."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_send_email_requires_auth(client: AsyncClient):
    """Test send email endpoint requires authentication."""
    surrogate_id = uuid4()
    response = await client.post(
        f"/surrogates/{surrogate_id}/send-email",
        json={"template_id": str(uuid4())},
    )
    # Should fail with 403 (CSRF) or 401 (no auth)
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_send_email_case_not_found(authed_client: AsyncClient):
    """Test send email with non-existent case returns 404."""
    surrogate_id = uuid4()
    response = await authed_client.post(
        f"/surrogates/{surrogate_id}/send-email",
        json={"template_id": str(uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_email_template_not_found(authed_client: AsyncClient, db, test_org, test_user):
    """Test send email with non-existent template returns 404."""
    from app.services import surrogate_service
    from app.schemas.surrogate import SurrogateCreate
    from app.db.enums import SurrogateSource

    # Create a case
    case_data = SurrogateCreate(
        full_name="Test Case",
        email="test@example.com",
        source=SurrogateSource.MANUAL,
    )
    case = surrogate_service.create_surrogate(db, test_org.id, test_user.id, case_data)

    # Try to send with non-existent template
    response = await authed_client.post(
        f"/surrogates/{case.id}/send-email",
        json={"template_id": str(uuid4())},
    )
    assert response.status_code == 404
    assert "template" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_email_no_provider_returns_error(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    """Test send email when no provider available returns error."""
    from app.services import surrogate_service, email_service
    from app.schemas.surrogate import SurrogateCreate
    from app.db.enums import SurrogateSource

    # Create a case
    case_data = SurrogateCreate(
        full_name="Test Case",
        email="test@example.com",
        source=SurrogateSource.MANUAL,
    )
    case = surrogate_service.create_surrogate(db, test_org.id, test_user.id, case_data)

    # Create a template
    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Welcome Template",
        subject="Hello {{full_name}}",
        body="<p>Welcome {{full_name}}!</p>",
    )

    # Ensure no Resend API key and no Gmail connected
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    # Send with auto provider (no providers available)
    response = await authed_client.post(
        f"/surrogates/{case.id}/send-email",
        json={"template_id": str(template.id), "provider": "auto"},
    )

    assert response.status_code == 200  # Returns success=False in body
    data = response.json()
    assert data["success"] is False
    assert "no email provider" in data["error"].lower()


@pytest.mark.asyncio
async def test_send_email_suppressed_returns_error(
    authed_client: AsyncClient, db, test_org, test_user
):
    """Suppressed recipients should be skipped before provider selection."""
    from app.services import surrogate_service, email_service, campaign_service
    from app.schemas.surrogate import SurrogateCreate
    from app.db.enums import SurrogateSource

    case_data = SurrogateCreate(
        full_name="Suppressed Case",
        email="suppressed@example.com",
        source=SurrogateSource.MANUAL,
    )
    case = surrogate_service.create_surrogate(db, test_org.id, test_user.id, case_data)

    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Suppressed Template",
        subject="Hello {{full_name}}",
        body="<p>Welcome {{full_name}}!</p>",
    )

    campaign_service.add_to_suppression(
        db,
        org_id=test_org.id,
        email="suppressed@example.com",
        reason="opt_out",
    )

    response = await authed_client.post(
        f"/surrogates/{case.id}/send-email",
        json={"template_id": str(template.id), "provider": "auto"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "suppressed" in (data.get("error") or "").lower()
