import re

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

    res = await authed_client.get("/platform/email/system-templates/org_invite")
    assert res.status_code == 200
    data = res.json()
    body = data["body"]
    assert data["system_key"] == "org_invite"
    assert data["from_email"] is None
    assert "{{org_name}}" in data["subject"]
    assert "invite_url" in body
    assert "Accept Invitation" in body
    assert "background-color:#f5f5f7" in body.replace(" ", "")
    assert "{{inviter_text}}" not in body
    assert "You've been invited to join" in body
    assert "as a <strong>{{role_title}}</strong>." in body
    assert re.search(r"<h1[^>]*>\s*You're invited to join\s*</h1>", body)
    assert re.search(r"<div[^>]*font-size:\s*22px[^>]*>\s*{{org_name}}\s*</div>", body)


@pytest.mark.asyncio
async def test_platform_update_system_email_template_increments_version(
    authed_client, db, test_user, test_org
):
    from app.services import system_email_template_service

    test_user.is_platform_admin = True
    db.commit()

    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    db.commit()
    start_version = tpl.current_version

    res = await authed_client.put(
        "/platform/email/system-templates/org_invite",
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
        assert kwargs["template_id"] is None
        assert kwargs["from_email"] == "Invites <invites@surrogacyforce.com>"
        return {"success": True, "message_id": "msg_123", "email_log_id": "log_123"}

    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    # Seed template with a custom From address
    from app.services import system_email_template_service

    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()

    res = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json={"to_email": "test@example.com", "org_id": str(test_org.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sent"] is True
    assert data["message_id"] == "msg_123"


@pytest.mark.asyncio
async def test_platform_system_email_campaign_sends_selected_users(
    authed_client, db, test_user, test_org, monkeypatch
):
    from app.services import platform_email_service, system_email_template_service

    test_user.is_platform_admin = True
    db.commit()

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    async def fake_send_email_logged(**kwargs):
        assert kwargs["org_id"] == test_org.id
        assert kwargs["to_email"] == test_user.email
        assert kwargs["template_id"] is None
        assert kwargs["from_email"] == "Invites <invites@surrogacyforce.com>"
        return {"success": True}

    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()

    res = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json={"targets": [{"org_id": str(test_org.id), "user_ids": [str(test_user.id)]}]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sent"] == 1
    assert data["failed"] == 0
    assert data["suppressed"] == 0
    assert data["recipients"] == 1
