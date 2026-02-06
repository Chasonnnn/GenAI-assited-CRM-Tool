"""Tests for template variables catalog endpoints (org + platform admin)."""

import pytest


@pytest.mark.asyncio
async def test_org_email_template_variables_endpoint(authed_client):
    res = await authed_client.get("/email-templates/variables")
    assert res.status_code == 200
    variables = res.json()

    names = {v["name"] for v in variables}
    assert "status_label" in names
    assert "state" in names
    assert "unsubscribe_url" in names


@pytest.mark.asyncio
async def test_platform_email_template_variables_endpoint_requires_platform_admin(
    authed_client,
):
    res = await authed_client.get("/platform/templates/email/variables")
    # Default test user is not platform admin unless tests set it.
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_platform_email_template_variables_endpoint_platform_admin(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.get("/platform/templates/email/variables")
    assert res.status_code == 200
    variables = res.json()

    names = {v["name"] for v in variables}
    assert "status_label" in names
    assert "state" in names
    assert "unsubscribe_url" in names


@pytest.mark.asyncio
async def test_platform_system_template_variables_endpoint_platform_admin(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.get("/platform/email/system-templates/org_invite/variables")
    assert res.status_code == 200
    variables = res.json()

    names = {v["name"] for v in variables}
    assert "org_name" in names
    assert "invite_url" in names
    assert "platform_logo_block" in names


@pytest.mark.asyncio
async def test_platform_system_template_variables_endpoint_allows_custom_key(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.get(
        "/platform/email/system-templates/custom_announcement/variables"
    )
    assert res.status_code == 200
    variables = res.json()

    names = {v["name"] for v in variables}
    assert "org_name" in names
    assert "invite_url" in names
    assert "platform_logo_block" in names
