from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import EmailTemplate, Membership, User, UserIntegration
from app.main import app
from app.services import resend_settings_service, session_service


@asynccontextmanager
async def authed_client_for_user(db, user: User, org_id: uuid.UUID, role: Role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_test_send_org_template_uses_resend_when_configured(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.models import EmailLog

    resend_settings_service.update_resend_settings(
        db,
        test_org.id,
        test_user.id,
        email_provider="resend",
        api_key="re_test_key",
        from_email="no-reply@example.com",
        from_name="Test Org",
    )

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Test Template",
        subject="Hello {{full_name}}",
        body="<p>Hello {{full_name}}</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    async def fake_send_email_direct(*args, **kwargs):
        return True, None, "resend_123"

    from app.services import resend_email_service

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    res = await authed_client.post(
        f"/email-templates/{template.id}/test",
        json={"to_email": "test@example.com"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["provider_used"] == "resend"
    assert data["message_id"] == "resend_123"
    assert data["email_log_id"]

    log_id = uuid.UUID(data["email_log_id"])
    log = db.query(EmailLog).filter(EmailLog.id == log_id).first()
    assert log is not None
    assert log.status == "sent"
    assert log.external_id == "resend_123"
    assert log.resend_status == "sent"
    assert log.template_id == template.id


@pytest.mark.asyncio
async def test_test_send_org_template_uses_org_gmail_when_configured(
    authed_client, db, test_org, test_user, monkeypatch
):
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

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Test Template",
        subject="Hello {{full_name}}",
        body="<p>Hello {{full_name}}</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
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
        return {"success": True, "message_id": "gmail_123", "email_log_id": str(uuid.uuid4())}

    from app.services import gmail_service

    monkeypatch.setattr(gmail_service, "send_email_logged", fake_send_email_logged)

    res = await authed_client.post(
        f"/email-templates/{template.id}/test",
        json={"to_email": "test@example.com"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["provider_used"] == "gmail"
    assert data["message_id"] == "gmail_123"
    assert called["user_id"] == str(sender.id)


@pytest.mark.asyncio
async def test_test_send_org_template_requires_manage_permission(db, test_org, monkeypatch):
    user = User(
        id=uuid.uuid4(),
        email=f"cm-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Case Manager",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=test_org.id,
            role=Role.CASE_MANAGER.value,
            is_active=True,
        )
    )
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="Org Template",
        subject="Hello {{full_name}}",
        body="<p>Hello</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    async with authed_client_for_user(db, user, test_org.id, Role.CASE_MANAGER) as client:
        res = await client.post(
            f"/email-templates/{template.id}/test",
            json={"to_email": "test@example.com"},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_test_send_personal_template_only_owner_can_send(db, test_org, monkeypatch):
    owner = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Owner",
        token_version=1,
        is_active=True,
    )
    other = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other",
        token_version=1,
        is_active=True,
    )
    db.add_all([owner, other])
    db.flush()
    db.add_all(
        [
            Membership(
                id=uuid.uuid4(),
                user_id=owner.id,
                organization_id=test_org.id,
                role=Role.CASE_MANAGER.value,
                is_active=True,
            ),
            Membership(
                id=uuid.uuid4(),
                user_id=other.id,
                organization_id=test_org.id,
                role=Role.CASE_MANAGER.value,
                is_active=True,
            ),
        ]
    )
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=owner.id,
        name="Personal Template",
        subject="Hello {{full_name}}",
        body="<p>Hello</p>",
        scope="personal",
        owner_user_id=owner.id,
        is_active=True,
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
        return {"success": True, "message_id": "gmail_789", "email_log_id": str(uuid.uuid4())}

    from app.services import gmail_service

    monkeypatch.setattr(gmail_service, "send_email_logged", fake_send_email_logged)

    async with authed_client_for_user(db, owner, test_org.id, Role.CASE_MANAGER) as client:
        res = await client.post(
            f"/email-templates/{template.id}/test",
            json={"to_email": "test@example.com"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["provider_used"] == "gmail"
        assert data["message_id"] == "gmail_789"
        assert called["user_id"] == str(owner.id)

    async with authed_client_for_user(db, other, test_org.id, Role.CASE_MANAGER) as client:
        res = await client.post(
            f"/email-templates/{template.id}/test",
            json={"to_email": "test@example.com"},
        )
        assert res.status_code == 403
