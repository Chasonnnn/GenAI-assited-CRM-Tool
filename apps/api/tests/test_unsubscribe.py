"""Tests for email unsubscribe flow."""

import pytest


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_adds_suppression(client, db, test_org):
    from app.services import unsubscribe_service, campaign_service
    from app.db.enums import SuppressionReason
    from app.db.models import EmailSuppression

    token = unsubscribe_service.generate_unsubscribe_token(
        org_id=test_org.id,
        email="User@Example.com",
    )

    resp = await client.get(f"/email/unsubscribe/{token}")
    assert resp.status_code == 200

    assert campaign_service.is_email_suppressed(
        db,
        test_org.id,
        "user@example.com",
    )
    suppression = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == test_org.id,
            EmailSuppression.email == "user@example.com",
        )
        .first()
    )
    assert suppression is not None
    assert suppression.reason == SuppressionReason.OPT_OUT.value


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_handles_invalid_token(client, db, test_org):
    from app.services import campaign_service

    resp = await client.get("/email/unsubscribe/invalid-token")
    assert resp.status_code == 200

    assert (
        campaign_service.is_email_suppressed(
            db,
            test_org.id,
            "user@example.com",
        )
        is False
    )
