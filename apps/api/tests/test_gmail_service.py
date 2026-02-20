"""Tests for Gmail service logging/idempotency."""

from io import BytesIO
from uuid import UUID, uuid4

import pytest

from app.db.enums import EmailStatus, SurrogateSource
from app.db.models import EmailLog, EmailLogAttachment, EmailSuppression
from app.schemas.surrogate import SurrogateCreate
from app.services import gmail_service


@pytest.mark.asyncio
async def test_send_email_logged_returns_existing_log(db, test_org, test_user, monkeypatch):
    idempotency_key = "invite:dedupe"
    email_log = EmailLog(
        organization_id=test_org.id,
        template_id=None,
        surrogate_id=None,
        recipient_email="user@example.com",
        subject="Hello",
        body="Body",
        status=EmailStatus.SENT.value,
        external_id="gmail-msg-1",
        idempotency_key=idempotency_key,
    )
    db.add(email_log)
    db.commit()

    async def should_not_send(*args, **kwargs):
        raise AssertionError("send_email should not be called for idempotent requests")

    monkeypatch.setattr(gmail_service, "send_email", should_not_send)

    result = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="user@example.com",
        subject="Hello",
        body="Body",
        html=True,
        template_id=None,
        surrogate_id=None,
        idempotency_key=idempotency_key,
    )

    assert result["success"] is True
    assert result["email_log_id"] == email_log.id
    assert result["message_id"] == "gmail-msg-1"


@pytest.mark.asyncio
async def test_send_email_logged_allows_opt_out_override(db, test_org, test_user, monkeypatch):
    """ignore_opt_out should bypass opt_out suppressions but still log + send."""
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email="optout@example.com",
            reason="opt_out",
        )
    )
    db.commit()

    called = {"count": 0}

    async def fake_send_email(*_args, **_kwargs):
        called["count"] += 1
        return {"success": True, "message_id": "gmail-msg-2"}

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    suppressed = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="optout@example.com",
        subject="Hello",
        body="Body",
        html=True,
        ignore_opt_out=False,
    )
    assert suppressed["success"] is False
    assert suppressed["error"] == "Email suppressed"
    assert called["count"] == 0

    sent = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="optout@example.com",
        subject="Hello",
        body="Body",
        html=True,
        ignore_opt_out=True,
    )
    assert sent["success"] is True
    assert sent["message_id"] == "gmail-msg-2"
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_send_email_logged_with_attachment_ids_loads_bytes_and_persists_links(
    db, test_org, test_user, monkeypatch
):
    from app.services import attachment_service, surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Gmail Attachment Test",
            email="gmail-attachment@test.com",
            source=SurrogateSource.MANUAL,
        ),
    )
    payload = b"%PDF-1.4 attachment-content"
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="attachment.pdf",
        content_type="application/pdf",
        file=BytesIO(payload),
        file_size=len(payload),
        surrogate_id=surrogate.id,
    )
    attachment.scan_status = "clean"
    attachment.quarantined = False
    db.commit()

    captured: dict[str, object] = {}

    async def fake_send_email(*_args, **kwargs):
        captured["attachments"] = kwargs.get("attachments") or []
        return {"success": True, "message_id": "gmail-msg-attachments"}

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    result = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="gmail-attachment@test.com",
        subject="Attachment Subject",
        body="<p>Attachment Body</p>",
        html=True,
        surrogate_id=surrogate.id,
        attachment_ids=[attachment.id],
        idempotency_key=f"attachment-idempotency-{uuid4()}",
    )

    assert result["success"] is True
    sent_attachments = captured["attachments"]
    assert isinstance(sent_attachments, list)
    assert len(sent_attachments) == 1
    assert sent_attachments[0]["filename"] == "attachment.pdf"
    assert sent_attachments[0]["content_type"] == "application/pdf"
    assert sent_attachments[0]["content_bytes"] == payload

    email_log_id = UUID(str(result["email_log_id"]))
    links = (
        db.query(EmailLogAttachment).filter(EmailLogAttachment.email_log_id == email_log_id).all()
    )
    assert len(links) == 1
    assert links[0].attachment_id == attachment.id


@pytest.mark.asyncio
async def test_send_email_logged_attachment_idempotency_reuses_existing_log(
    db, test_org, test_user, monkeypatch
):
    from app.services import attachment_service, surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Gmail Attachment Idempotency",
            email="gmail-idempotent@test.com",
            source=SurrogateSource.MANUAL,
        ),
    )
    payload = b"%PDF-1.4 idempotent-content"
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="idempotent.pdf",
        content_type="application/pdf",
        file=BytesIO(payload),
        file_size=len(payload),
        surrogate_id=surrogate.id,
    )
    attachment.scan_status = "clean"
    attachment.quarantined = False
    db.commit()

    calls = {"count": 0}

    async def fake_send_email(*_args, **_kwargs):
        calls["count"] += 1
        return {"success": True, "message_id": "gmail-msg-idempotent"}

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    idempotency_key = f"attachment-idempotency-{uuid4()}"
    first = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="gmail-idempotent@test.com",
        subject="Attachment Subject",
        body="<p>Attachment Body</p>",
        html=True,
        surrogate_id=surrogate.id,
        attachment_ids=[attachment.id],
        idempotency_key=idempotency_key,
    )
    second = await gmail_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        user_id=str(test_user.id),
        to="gmail-idempotent@test.com",
        subject="Attachment Subject",
        body="<p>Attachment Body</p>",
        html=True,
        surrogate_id=surrogate.id,
        attachment_ids=[attachment.id],
        idempotency_key=idempotency_key,
    )

    assert first["success"] is True
    assert second["success"] is True
    assert first["email_log_id"] == second["email_log_id"]
    assert calls["count"] == 1

    email_log_id = UUID(str(first["email_log_id"]))
    links = (
        db.query(EmailLogAttachment).filter(EmailLogAttachment.email_log_id == email_log_id).all()
    )
    assert len(links) == 1
