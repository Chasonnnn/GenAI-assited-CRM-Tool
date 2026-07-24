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
async def test_platform_list_invites_uses_monotonic_send_revision_for_engagement(
    authed_client, db, test_org, test_user
):
    from app.db.enums import EmailStatus, Role
    from app.db.models import EmailLog, OrgInvite

    test_user.is_platform_admin = True
    invite = OrgInvite(
        organization_id=test_org.id,
        email="engaged-invitee@example.com",
        role=Role.ADMIN.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        resend_count=2,
        send_revision=7,
    )
    db.add(invite)
    db.flush()
    opened_at = datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc)
    clicked_at = datetime(2026, 7, 23, 13, 5, tzinfo=timezone.utc)
    db.add(
        EmailLog(
            organization_id=test_org.id,
            recipient_email=invite.email,
            subject="Invitation",
            body="<p>Invitation</p>",
            status=EmailStatus.SENT.value,
            idempotency_key=f"invite:{invite.id}:v{invite.send_revision}",
            opened_at=opened_at,
            open_count=3,
            clicked_at=clicked_at,
            click_count=1,
        )
    )
    db.commit()

    response = await authed_client.get(f"/platform/orgs/{test_org.id}/invites")

    assert response.status_code == 200
    item = next(row for row in response.json() if row["id"] == str(invite.id))
    assert item["open_count"] == 3
    assert item["opened_at"] == opened_at.isoformat()
    assert item["click_count"] == 1
    assert item["clicked_at"] == clicked_at.isoformat()


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


@pytest.mark.asyncio
async def test_platform_create_invite_reuses_expired_pending_invite(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.enums import Role
    from app.db.models import OrgInvite
    from app.services import invite_email_service
    from app.services import platform_email_service

    test_user.is_platform_admin = True
    db.commit()

    existing = OrgInvite(
        organization_id=test_org.id,
        email="invitee@example.com",
        role=Role.CASE_MANAGER.value,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(existing)
    db.commit()

    async def fake_send_invite_email(*_args, **_kwargs):
        return {"success": True}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fake_send_invite_email)
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/invites",
        json={"email": "invitee@example.com", "role": "admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(existing.id)
    assert payload["role"] == Role.ADMIN.value
    assert payload["status"] == "pending"

    db.refresh(existing)
    assert existing.expires_at is not None
    assert existing.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_platform_create_invite_allows_inactive_prior_member(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.enums import Role
    from app.db.models import Membership, User
    from app.services import invite_email_service
    from app.services import platform_email_service

    test_user.is_platform_admin = True
    prior_user = User(
        email="former-member@example.com",
        display_name="Former Member",
        is_active=False,
    )
    db.add(prior_user)
    db.flush()
    db.add(
        Membership(
            user_id=prior_user.id,
            organization_id=test_org.id,
            role=Role.CASE_MANAGER.value,
            is_active=False,
        )
    )
    db.commit()

    async def fake_send_invite_email(*_args, **_kwargs):
        return {"success": True}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fake_send_invite_email)
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/invites",
        json={"email": "former-member@example.com", "role": "admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "former-member@example.com"
    assert payload["role"] == Role.ADMIN.value


@pytest.mark.asyncio
async def test_platform_create_invite_rolls_back_when_delivery_cannot_be_queued(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.models import OrgInvite
    from app.services import invite_email_service, platform_email_service

    test_user.is_platform_admin = True
    db.commit()
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    async def fail_enqueue(*_args, **_kwargs):
        return {"success": False, "error": "Outbox unavailable"}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fail_enqueue)

    response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/invites",
        json={"email": "atomic-platform-invite@example.com", "role": "admin"},
    )

    assert response.status_code == 503
    assert (
        db.query(OrgInvite)
        .filter(
            OrgInvite.organization_id == test_org.id,
            OrgInvite.email == "atomic-platform-invite@example.com",
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_platform_resend_invite_rolls_back_revision_when_delivery_cannot_be_queued(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.enums import Role
    from app.db.models import OrgInvite
    from app.services import invite_email_service, platform_email_service

    test_user.is_platform_admin = True
    invite = OrgInvite(
        organization_id=test_org.id,
        email="atomic-platform-resend@example.com",
        role=Role.ADMIN.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()
    initial_revision = invite.send_revision
    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    async def fail_enqueue(*_args, **_kwargs):
        return {"success": False, "error": "Outbox unavailable"}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fail_enqueue)

    response = await authed_client.post(f"/platform/orgs/{test_org.id}/invites/{invite.id}/resend")

    assert response.status_code == 503
    db.expire_all()
    persisted = db.get(OrgInvite, invite.id)
    assert persisted.resend_count == 0
    assert persisted.send_revision == initial_revision
    assert persisted.last_resent_at is None
