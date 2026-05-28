"""Tests for Gmail service logging/idempotency."""

import logging
from io import BytesIO
from uuid import UUID, uuid4

import pytest

from app.db.enums import EmailStatus, SurrogateSource
from app.db.models import EmailLog, EmailLogAttachment, EmailSuppression
from app.schemas.surrogate import SurrogateCreate
from app.services import gmail_service


def _ops_records(caplog, message: str):
    return [record for record in caplog.records if record.name == "app.ops" and record.message == message]


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
async def test_send_email_logged_emits_safe_attempt_and_success_logs(
    db,
    test_org,
    test_user,
    monkeypatch,
    caplog,
):
    async def fake_send_email(*_args, **_kwargs):
        return {
            "success": True,
            "message_id": "gmail-msg-safe-log",
            "thread_id": "thread-safe-log",
            "provider_status_code": 200,
        }

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    with caplog.at_level(logging.INFO, logger="app.ops"):
        result = await gmail_service.send_email_logged(
            db=db,
            org_id=test_org.id,
            user_id=str(test_user.id),
            to="niki.gmail@example.com",
            subject="Secret Subject",
            body="<p>Secret body with {{token}}</p>",
            html=True,
            attachments=[{"filename": "safe.pdf", "content_bytes": b"secret"}],
        )

    assert result["success"] is True
    attempt = _ops_records(caplog, "email_send_attempt")[-1]
    success = _ops_records(caplog, "email_send_success")[-1]

    assert attempt.email_log_id == str(result["email_log_id"])
    assert attempt.provider == "gmail"
    assert attempt.org_id == str(test_org.id)
    assert attempt.user_id == str(test_user.id)
    assert attempt.attachment_count == 1
    assert attempt.recipient_email_hash
    assert success.email_log_id == str(result["email_log_id"])
    assert success.provider_status_code == 200

    rendered_records = " ".join(str(record.__dict__) for record in (attempt, success))
    assert "niki.gmail@example.com" not in rendered_records
    assert "Secret Subject" not in rendered_records
    assert "Secret body" not in rendered_records
    assert "{{token}}" not in rendered_records


@pytest.mark.asyncio
async def test_send_email_logged_emits_safe_failure_log(
    db,
    test_org,
    test_user,
    monkeypatch,
    caplog,
):
    async def fake_send_email(*_args, **_kwargs):
        return {
            "success": False,
            "error": "Gmail API error: 403 (insufficientPermissions)",
            "provider_status_code": 403,
            "provider_error_reason": "insufficientPermissions",
        }

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    with caplog.at_level(logging.INFO, logger="app.ops"):
        result = await gmail_service.send_email_logged(
            db=db,
            org_id=test_org.id,
            user_id=str(test_user.id),
            to="niki.failure@example.com",
            subject="Failure Subject",
            body="Failure body",
            html=False,
        )

    assert result["success"] is False
    failure = _ops_records(caplog, "email_send_failure")[-1]
    assert failure.email_log_id == str(result["email_log_id"])
    assert failure.provider == "gmail"
    assert failure.provider_status_code == 403
    assert failure.provider_error_reason == "insufficientPermissions"
    assert failure.recipient_email_hash

    rendered_record = str(failure.__dict__)
    assert "niki.failure@example.com" not in rendered_record
    assert "Failure Subject" not in rendered_record
    assert "Failure body" not in rendered_record


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
    assert links[0].attachment_id == attachment.id
