from __future__ import annotations

import uuid

import pytest

from app.db.enums import Role
from app.db.models import Membership, PlatformEmailTemplate, User, UserIntegration
from app.services import resend_settings_service


@pytest.mark.asyncio
async def test_platform_email_template_test_send_respects_org_provider_settings(
    authed_client, db, test_org, test_user, monkeypatch
):
    test_user.is_platform_admin = True
    db.commit()

    sender = User(
        id=uuid.uuid4(),
        email=f"sender-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Sender",
        token_version=1,
        is_active=True,
    )
    db.add(sender)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=sender.id,
            organization_id=test_org.id,
            role=Role.ADMIN.value,
            is_active=True,
        )
    )
    db.add(
        UserIntegration(
            id=uuid.uuid4(),
            user_id=sender.id,
            integration_type="gmail",
            access_token_encrypted="test",
            refresh_token_encrypted=None,
            token_expires_at=None,
            account_email="sender@gmail.com",
            current_version=1,
        )
    )
    db.commit()

    resend_settings_service.update_resend_settings(
        db,
        test_org.id,
        test_user.id,
        email_provider="gmail",
        default_sender_user_id=sender.id,
    )

    template = PlatformEmailTemplate(
        id=uuid.uuid4(),
        name="Ops Template",
        subject="Hello {{org_name}}",
        body="<p>Hello {{full_name}}</p>",
        from_email="Ops <ops@example.com>",
        category="ops",
        status="draft",
        current_version=1,
        published_version=0,
        is_published_globally=False,
    )
    db.add(template)
    db.commit()

    called: dict[str, object] = {}

    async def fake_send_email_logged(
        *,
        db,
        org_id,
        user_id,
        to,
        subject,
        body,
        html,
        template_id=None,
        surrogate_id=None,
        idempotency_key=None,
        headers=None,
    ):
        called["user_id"] = user_id
        return {"success": True, "message_id": "gmail_ops_1", "email_log_id": str(uuid.uuid4())}

    from app.services import gmail_service

    monkeypatch.setattr(gmail_service, "send_email_logged", fake_send_email_logged)

    res = await authed_client.post(
        f"/platform/templates/email/{template.id}/test",
        json={"org_id": str(test_org.id), "to_email": "test@example.com"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["provider_used"] == "gmail"
    assert data["message_id"] == "gmail_ops_1"
    assert called["user_id"] == str(sender.id)
