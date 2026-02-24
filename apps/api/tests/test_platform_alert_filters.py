"""Tests for platform alert filter validation."""

import pytest


@pytest.mark.asyncio
async def test_platform_alert_filters_reject_invalid_values(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    invalid_status = await authed_client.get("/platform/alerts?status=invalid")
    assert invalid_status.status_code == 422

    invalid_severity = await authed_client.get("/platform/alerts?severity=info")
    assert invalid_severity.status_code == 422


@pytest.mark.asyncio
async def test_platform_alert_filters_accept_supported_values(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.get("/platform/alerts?status=snoozed&severity=warn")
    assert response.status_code == 200
