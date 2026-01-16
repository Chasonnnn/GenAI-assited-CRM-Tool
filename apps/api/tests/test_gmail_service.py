"""Tests for Gmail service logging/idempotency."""

import pytest

from app.db.enums import EmailStatus
from app.db.models import EmailLog
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
