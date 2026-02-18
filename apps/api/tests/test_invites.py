"""Tests for invite service and email sending."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def test_accept_invite_creates_membership(db, test_org):
    """Accepting an invite should not access missing user fields."""
    from app.db.models import User, OrgInvite, Membership
    from app.services import invite_service

    user = User(
        id=uuid4(),
        email="invited-user@example.com",
        display_name="Invited User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    invite = OrgInvite(
        id=uuid4(),
        organization_id=test_org.id,
        email=user.email,
        role="intake_specialist",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.flush()

    result = invite_service.accept_invite(db, invite.id, user.id)

    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.organization_id == test_org.id,
        )
        .first()
    )

    assert membership is not None
    assert invite.accepted_at is not None
    assert result["organization_id"] == str(test_org.id)


def test_create_invite_rejects_invalid_role(db, test_org, test_user):
    """Invalid invite roles should be rejected."""
    from app.services import invite_service

    with pytest.raises(ValueError):
        invite_service.create_invite(
            db=db,
            org_id=test_org.id,
            email="new-user@example.com",
            role="member",
            invited_by_user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_send_invite_email_includes_inviter_name(db, test_org, test_user, monkeypatch):
    """Invite emails should include the inviter display name when available."""
    from app.core.config import settings
    from app.db.models import OrgInvite
    from app.services import invite_email_service, platform_email_service

    monkeypatch.setattr(settings, "PLATFORM_RESEND_API_KEY", "test-resend-key")

    invite = OrgInvite(
        id=uuid4(),
        organization_id=test_org.id,
        email="new-user@example.com",
        role="case_manager",
        invited_by_user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.flush()

    captured = {}

    async def fake_send_email_logged(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message_id": "msg_123"}

    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    result = await invite_email_service.send_invite_email(db, invite)

    assert result["success"] is True
    text_body = captured.get("text") or ""
    html_body = captured.get("html") or ""
    assert "You've been invited" in text_body
    assert test_user.display_name in text_body
    assert test_user.display_name in html_body
    assert "Case Manager" in text_body
    assert "Case_Manager" not in text_body
    assert "Case Manager" in html_body
    assert "Case_Manager" not in html_body
    assert "as Case Manager." in text_body
    assert "as a Case Manager." not in text_body
    assert "as <strong>Case Manager</strong>." in html_body
    assert "as a <strong>Case Manager</strong>." not in html_body


@pytest.mark.asyncio
async def test_send_invite_email_uses_platform_sender_when_configured(db, test_org, monkeypatch):
    """Platform sender should be able to send invites without inviter Gmail."""
    from app.core.config import settings
    from app.db.models import OrgInvite
    from app.services import (
        invite_email_service,
        platform_email_service,
        system_email_template_service,
    )

    monkeypatch.setattr(settings, "PLATFORM_RESEND_API_KEY", "test-resend-key")

    # Sender is configured per system template (no global From required).
    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = "Invites <invites@surrogacyforce.com>"
    tpl.is_active = False
    db.flush()

    invite = OrgInvite(
        id=uuid4(),
        organization_id=test_org.id,
        email="new-user@example.com",
        role="case_manager",
        invited_by_user_id=None,  # No inviter -> must not require Gmail
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.flush()

    captured: dict[str, object] = {}

    async def fake_send_email_logged(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message_id": "msg_123"}

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)
    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    result = await invite_email_service.send_invite_email(db, invite)

    assert result["success"] is True
    assert captured["to_email"] == invite.email


@pytest.mark.asyncio
async def test_send_invite_email_uses_template_from_email_when_platform_sender(
    db, test_org, monkeypatch
):
    """If the org invite system template sets from_email, platform sender should use it."""
    from app.core.config import settings
    from app.db.models import OrgInvite
    from app.services import (
        invite_email_service,
        platform_email_service,
        system_email_template_service,
    )

    monkeypatch.setattr(settings, "PLATFORM_RESEND_API_KEY", "test-resend-key")

    template_from = "Invites <invites@surrogacyforce.com>"
    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    tpl.from_email = template_from
    tpl.is_active = True
    db.flush()

    invite = OrgInvite(
        id=uuid4(),
        organization_id=test_org.id,
        email="new-user@example.com",
        role="case_manager",
        invited_by_user_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.flush()

    captured: dict[str, object] = {}

    async def fake_send_email_logged(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message_id": "msg_123"}

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)
    monkeypatch.setattr(platform_email_service, "send_email_logged", fake_send_email_logged)

    result = await invite_email_service.send_invite_email(db, invite)

    assert result["success"] is True
    assert captured["from_email"] == template_from


@pytest.mark.asyncio
async def test_create_invite_allows_platform_sender_without_gmail(authed_client, monkeypatch):
    """Invites API should allow invite creation when platform sender is configured."""
    from app.core.config import settings
    from app.services import platform_email_service

    monkeypatch.setattr(settings, "PLATFORM_RESEND_API_KEY", "test-resend-key")

    async def fake_send_resend_email(**kwargs):
        return {"success": True, "message_id": "msg_123"}

    monkeypatch.setattr(platform_email_service, "_send_resend_email", fake_send_resend_email)

    res = await authed_client.post(
        "/settings/invites",
        json={"email": "new-user@example.com", "role": "case_manager"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["email"] == "new-user@example.com"
    assert data["role"] == "case_manager"


@pytest.mark.asyncio
async def test_create_invite_reuses_expired_pending_invite(
    authed_client, db, test_org, test_user, monkeypatch
):
    """Creating an invite for an expired pending invite should reactivate the existing row."""
    from app.db.enums import Role
    from app.db.models import OrgInvite
    from app.services import invite_email_service, platform_email_service

    existing = OrgInvite(
        organization_id=test_org.id,
        email="expired-user@example.com",
        role=Role.CASE_MANAGER.value,
        invited_by_user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
        resend_count=0,
    )
    db.add(existing)
    db.commit()

    async def fake_send_invite_email(*_args, **_kwargs):
        return {"success": True}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fake_send_invite_email)
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    res = await authed_client.post(
        "/settings/invites",
        json={"email": "expired-user@example.com", "role": "admin"},
    )

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == str(existing.id)
    assert data["status"] == "pending"
    assert data["role"] == Role.ADMIN.value

    db.refresh(existing)
    assert existing.expires_at is not None
    assert existing.expires_at > datetime.now(timezone.utc)
