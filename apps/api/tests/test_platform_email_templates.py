import pytest


@pytest.mark.asyncio
async def test_platform_email_status_requires_admin_flag(authed_client):
    res = await authed_client.get("/platform/email/status")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_platform_email_status_allows_admin_flag(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.get("/platform/email/status")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "resend"
    assert data["configured"] is False


@pytest.mark.asyncio
async def test_platform_get_system_email_template_creates_default(
    authed_client, db, test_user, test_org
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.get(f"/platform/orgs/{test_org.id}/email/system-templates/org_invite")
    assert res.status_code == 200
    data = res.json()
    assert data["system_key"] == "org_invite"
    assert data["from_email"] is None
    assert "{{org_name}}" in data["subject"]
    assert "invite_url" in data["body"]


@pytest.mark.asyncio
async def test_platform_update_system_email_template_increments_version(
    authed_client, db, test_user, test_org
):
    from app.services import system_email_template_service

    test_user.is_platform_admin = True
    db.commit()

    tpl = system_email_template_service.ensure_system_template(
        db, org_id=test_org.id, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    db.commit()
    start_version = tpl.current_version

    res = await authed_client.put(
        f"/platform/orgs/{test_org.id}/email/system-templates/org_invite",
        json={
            "from_email": "Invites <invites@surrogacyforce.com>",
            "subject": "Invite: {{org_name}}",
            "body": "<p>Hello {{org_name}}</p>",
            "is_active": True,
            "expected_version": start_version,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["from_email"] == "Invites <invites@surrogacyforce.com>"
    assert data["subject"] == "Invite: {{org_name}}"
    assert data["current_version"] == start_version + 1


@pytest.mark.asyncio
async def test_platform_send_test_system_email_uses_platform_sender(
    authed_client, db, test_user, test_org, monkeypatch
):
    from app.services import platform_email_service

    test_user.is_platform_admin = True
    db.commit()

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    async def fake_send_email_logged(**kwargs):
        assert kwargs["org_id"] == test_org.id
        assert kwargs["to_email"] == "test@example.com"
        assert kwargs["template_id"] is not None
        assert kwargs["from_email"] == "Invites <invites@surrogacyforce.com>"
        return {"success": True, "message_id": "msg_123", "email_log_id": "log_123"}

    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    # Seed template with a custom From address
    from app.services import system_email_template_service

    tpl = system_email_template_service.ensure_system_template(
        db, org_id=test_org.id, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()

    res = await authed_client.post(
        f"/platform/orgs/{test_org.id}/email/system-templates/org_invite/test",
        json={"to_email": "test@example.com"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sent"] is True
    assert data["message_id"] == "msg_123"
