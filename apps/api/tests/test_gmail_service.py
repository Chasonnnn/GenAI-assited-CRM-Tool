"""Tests for Gmail service logging/idempotency."""

import pytest

from app.db.enums import EmailStatus
from app.db.models import EmailLog, EmailSuppression
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
