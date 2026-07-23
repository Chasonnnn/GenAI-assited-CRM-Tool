import re
from uuid import uuid4

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
    assert "as <strong>{{role_title}}</strong>." in body
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
        assert kwargs["idempotency_key"] == (
            f"platform-system-test:org_invite:{test_occurrence_id}"
        )
        return {
            "success": True,
            "queued": True,
            "message_id": None,
            "email_log_id": "log_123",
        }

    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    # Seed template with a custom From address
    from app.services import system_email_template_service

    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()
    test_occurrence_id = uuid4()

    res = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json={
            "to_email": "test@example.com",
            "org_id": str(test_org.id),
            "idempotency_key": str(test_occurrence_id),
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["queued"] is True
    assert "sent" not in data
    assert data["message_id"] is None
    assert data["email_log_id"] == "log_123"

    org_scoped_response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/email/system-templates/org_invite/test",
        json={
            "to_email": "test@example.com",
            "idempotency_key": str(test_occurrence_id),
        },
    )
    assert org_scoped_response.status_code == 200
    assert org_scoped_response.json()["queued"] is True


@pytest.mark.asyncio
async def test_platform_send_test_system_email_requires_idempotency_key(
    authed_client, db, test_user, test_org
):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json={"to_email": "test@example.com", "org_id": str(test_org.id)},
    )

    assert response.status_code == 422
    assert "idempotency_key" in response.text


@pytest.mark.asyncio
async def test_platform_send_test_system_email_reuses_one_occurrence_but_allows_a_new_send(
    authed_client, db, test_user, test_org, monkeypatch
):
    from app.db.models import EmailLog
    from app.services import platform_email_service, system_email_template_service

    test_user.is_platform_admin = True
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    template = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    template.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()

    first_occurrence_id = uuid4()
    request_body = {
        "to_email": "test@example.com",
        "org_id": str(test_org.id),
        "idempotency_key": str(first_occurrence_id),
    }
    first = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json=request_body,
    )
    retry = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json=request_body,
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json()["queued"] is True
    assert retry.json()["queued"] is True
    first_key = f"platform-system-test:org_invite:{first_occurrence_id}"
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == first_key,
        )
        .count()
        == 1
    )

    second_occurrence_id = uuid4()
    second = await authed_client.post(
        "/platform/email/system-templates/org_invite/test",
        json={
            **request_body,
            "idempotency_key": str(second_occurrence_id),
        },
    )

    assert second.status_code == 200
    second_key = f"platform-system-test:org_invite:{second_occurrence_id}"
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key.in_([first_key, second_key]),
        )
        .count()
        == 2
    )


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
    campaign_occurrence_id = uuid4()

    res = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json={
            "campaign_occurrence_id": str(campaign_occurrence_id),
            "targets": [{"org_id": str(test_org.id), "user_ids": [str(test_user.id)]}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["queued"] == 1
    assert "sent" not in data
    assert data["failed"] == 0
    assert data["suppressed"] == 0
    assert data["recipients"] == 1


@pytest.mark.asyncio
async def test_platform_system_email_campaign_requires_occurrence_id(
    authed_client, db, test_user, test_org
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json={"targets": [{"org_id": str(test_org.id), "user_ids": [str(test_user.id)]}]},
    )

    assert res.status_code == 422
    assert "campaign_occurrence_id" in res.text


@pytest.mark.asyncio
async def test_platform_system_email_campaign_occurrence_is_idempotent_but_distinct_campaigns_queue(
    authed_client, db, test_user, test_org, monkeypatch
):
    from app.db.models import EmailLog
    from app.services import platform_email_service, system_email_template_service

    test_user.is_platform_admin = True
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    template = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    template.from_email = "Invites <invites@surrogacyforce.com>"
    db.commit()

    first_occurrence_id = uuid4()
    request_body = {
        "campaign_occurrence_id": str(first_occurrence_id),
        "targets": [{"org_id": str(test_org.id), "user_ids": [str(test_user.id)]}],
    }

    first = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json=request_body,
    )
    retry = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json=request_body,
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    first_key = f"platform-campaign:org_invite:{first_occurrence_id}:{test_org.id}:{test_user.id}"
    first_logs = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == first_key,
        )
        .all()
    )
    assert len(first_logs) == 1

    second_occurrence_id = uuid4()
    second = await authed_client.post(
        "/platform/email/system-templates/org_invite/campaign",
        json={
            **request_body,
            "campaign_occurrence_id": str(second_occurrence_id),
        },
    )

    assert second.status_code == 200
    second_key = f"platform-campaign:org_invite:{second_occurrence_id}:{test_org.id}:{test_user.id}"
    second_logs = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key.in_([first_key, second_key]),
        )
        .all()
    )
    assert len(second_logs) == 2
    assert {log.idempotency_key for log in second_logs} == {first_key, second_key}


@pytest.mark.asyncio
async def test_platform_create_system_email_template_and_list_includes_it(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.post(
        "/platform/email/system-templates",
        json={
            "system_key": "custom_announcement",
            "name": "Custom Announcement",
            "subject": "Announcement for {{org_name}}",
            "from_email": "Ops <ops@surrogacyforce.com>",
            "body": "<p>Hello {{org_name}}</p>",
            "is_active": True,
        },
    )
    assert res.status_code == 201
    created = res.json()
    assert created["system_key"] == "custom_announcement"
    assert created["name"] == "Custom Announcement"
    assert created["subject"] == "Announcement for {{org_name}}"
    assert created["from_email"] == "Ops <ops@surrogacyforce.com>"
    assert created["is_active"] is True
    assert created["current_version"] == 1

    list_res = await authed_client.get("/platform/email/system-templates")
    assert list_res.status_code == 200
    keys = {row["system_key"] for row in list_res.json()}
    assert "custom_announcement" in keys


@pytest.mark.asyncio
async def test_platform_create_system_email_template_rejects_reserved_new_key(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.post(
        "/platform/email/system-templates",
        json={
            "system_key": "new",
            "name": "Bad",
            "subject": "Bad",
            "body": "<p>Bad</p>",
            "is_active": True,
        },
    )
    assert res.status_code == 422
