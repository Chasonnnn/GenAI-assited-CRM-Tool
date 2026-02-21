"""Attachment behavior for surrogate email compose sends."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.db.enums import AuditEventType, SurrogateSource, SurrogateActivityType
from app.db.models import AuditLog, EmailLogAttachment, SurrogateActivityLog
from app.schemas.surrogate import SurrogateCreate
from app.services import attachment_service, email_service, surrogate_service


def _create_surrogate(db, test_org, test_user, *, email: str = "test@example.com"):
    return surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Attachment Test Surrogate",
            email=email,
            source=SurrogateSource.MANUAL,
        ),
    )


def _create_template(db, test_org, test_user):
    return email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"Attachment Template {uuid4()}",
        subject="Hello {{full_name}}",
        body="<p>Welcome {{full_name}}!</p>",
        scope="org",
    )


def _create_attachment(db, test_org, test_user, surrogate_id):
    payload = b"%PDF-1.4 attachment-bytes"
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="welcome.pdf",
        content_type="application/pdf",
        file=BytesIO(payload),
        file_size=len(payload),
        surrogate_id=surrogate_id,
    )
    attachment.scan_status = "clean"
    attachment.quarantined = False
    db.flush()
    return attachment


@pytest.mark.asyncio
async def test_send_email_with_non_clean_attachment_returns_422(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    from app.services import oauth_service

    surrogate = _create_surrogate(db, test_org, test_user, email="pending@example.com")
    template = _create_template(db, test_org, test_user)
    attachment = _create_attachment(db, test_org, test_user, surrogate.id)
    attachment.scan_status = "pending"
    attachment.quarantined = True
    db.commit()

    monkeypatch.setattr(oauth_service, "get_user_integration", lambda *_args, **_kwargs: object())

    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/send-email",
        json={
            "template_id": str(template.id),
            "provider": "gmail",
            "attachment_ids": [str(attachment.id)],
        },
    )

    assert response.status_code == 422
    assert "not ready" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_email_with_attachment_from_other_surrogate_returns_404(
    authed_client: AsyncClient, db, test_org, test_user
):
    surrogate = _create_surrogate(db, test_org, test_user, email="primary@example.com")
    other_surrogate = _create_surrogate(db, test_org, test_user, email="other@example.com")
    template = _create_template(db, test_org, test_user)
    other_attachment = _create_attachment(db, test_org, test_user, other_surrogate.id)
    db.commit()

    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/send-email",
        json={
            "template_id": str(template.id),
            "provider": "gmail",
            "attachment_ids": [str(other_attachment.id)],
        },
    )

    assert response.status_code == 404
    assert "attachment" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_email_gmail_passes_attachments_and_logs_activity_details(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    from app.services import gmail_service, oauth_service

    surrogate = _create_surrogate(db, test_org, test_user, email="gmail@example.com")
    template = _create_template(db, test_org, test_user)
    attachment = _create_attachment(db, test_org, test_user, surrogate.id)
    db.commit()

    monkeypatch.setattr(oauth_service, "get_user_integration", lambda *_args, **_kwargs: object())

    captured: dict[str, object] = {}

    async def fake_send_email_logged(**kwargs):
        captured["attachment_ids"] = kwargs.get("attachment_ids") or []
        return {"success": True, "message_id": "gmail-msg-1", "email_log_id": uuid4()}

    monkeypatch.setattr(gmail_service, "send_email_logged", fake_send_email_logged)

    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/send-email",
        json={
            "template_id": str(template.id),
            "provider": "gmail",
            "attachment_ids": [str(attachment.id)],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    sent_attachment_ids = captured["attachment_ids"]
    assert isinstance(sent_attachment_ids, list)
    assert sent_attachment_ids == [attachment.id]

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate.id,
            SurrogateActivityLog.activity_type == SurrogateActivityType.EMAIL_SENT.value,
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    attachments = details.get("attachments") or []
    assert len(attachments) == 1
    assert attachments[0]["attachment_id"] == str(attachment.id)
    assert attachments[0]["filename"] == attachment.filename
    assert details.get("subject", "").startswith("Hello ")
    assert details.get("template_id") == str(template.id)

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == AuditEventType.DATA_EMAIL_SENT.value,
            AuditLog.target_type == "surrogate",
            AuditLog.target_id == surrogate.id,
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit_log is not None
    assert audit_log.actor_user_id == test_user.id
    assert (audit_log.details or {}).get("email_log_id") == details.get("email_log_id")


@pytest.mark.asyncio
async def test_send_email_resend_links_attachments_to_email_log(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    from app.services import oauth_service

    surrogate = _create_surrogate(db, test_org, test_user, email="resend@example.com")
    template = _create_template(db, test_org, test_user)
    attachment = _create_attachment(db, test_org, test_user, surrogate.id)
    db.commit()

    monkeypatch.setattr(oauth_service, "get_user_integration", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/send-email",
        json={
            "template_id": str(template.id),
            "provider": "resend",
            "attachment_ids": [str(attachment.id)],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True, data
    assert data["email_log_id"] is not None
    email_log_id = UUID(data["email_log_id"])

    links = (
        db.query(EmailLogAttachment).filter(EmailLogAttachment.email_log_id == email_log_id).all()
    )
    assert len(links) == 1
    assert links[0].attachment_id == attachment.id

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate.id,
            SurrogateActivityLog.activity_type == SurrogateActivityType.EMAIL_SENT.value,
        )
        .first()
    )
    assert activity is None

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == AuditEventType.DATA_EMAIL_SENT.value,
            AuditLog.target_id == surrogate.id,
        )
        .first()
    )
    assert audit is None
