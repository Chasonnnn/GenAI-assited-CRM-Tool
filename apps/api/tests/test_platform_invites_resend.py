"""Tests for platform invite resend support."""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_platform_list_invites_includes_resend_fields(authed_client, db, test_org, test_user):
    from app.db.enums import Role
    from app.db.models import OrgInvite

    test_user.is_platform_admin = True
    db.commit()

    invite = OrgInvite(
        organization_id=test_org.id,
        email="invitee@example.com",
        role=Role.ADMIN.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()

    response = await authed_client.get(f"/platform/orgs/{test_org.id}/invites")
    assert response.status_code == 200
    data = response.json()
    item = next(i for i in data if i["id"] == str(invite.id))
    assert item["resend_count"] == 0
    assert item["can_resend"] is True
    assert item["resend_cooldown_seconds"] is None


@pytest.mark.asyncio
async def test_platform_resend_invite_updates_state(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.enums import Role
    from app.db.models import OrgInvite
    from app.services import invite_email_service
    from app.services import platform_email_service

    test_user.is_platform_admin = True
    db.commit()

    invite = OrgInvite(
        organization_id=test_org.id,
        email="invitee@example.com",
        role=Role.ADMIN.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()

    async def fake_send_invite_email(*_args, **_kwargs):
        return {"success": True}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fake_send_invite_email)
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    response = await authed_client.post(f"/platform/orgs/{test_org.id}/invites/{invite.id}/resend")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(invite.id)
    assert payload["resend_count"] == 1

    db.refresh(invite)
    assert invite.resend_count == 1
    assert invite.last_resent_at is not None

    list_response = await authed_client.get(f"/platform/orgs/{test_org.id}/invites")
    item = next(i for i in list_response.json() if i["id"] == str(invite.id))
    assert item["resend_count"] == 1
    assert item["can_resend"] is False
    assert item["resend_cooldown_seconds"] is not None
