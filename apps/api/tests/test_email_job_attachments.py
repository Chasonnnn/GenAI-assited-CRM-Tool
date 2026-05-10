"""Tests for attachment pass-through in email job handlers."""

from __future__ import annotations

from io import BytesIO

import pytest

from app.db.enums import EmailStatus, SurrogateSource
from app.db.models import Attachment, EmailLog, EmailLogAttachment
from app.jobs.handlers import email as email_job_handler
from app.schemas.surrogate import SurrogateCreate
from app.services import attachment_service, surrogate_service


def _configure_org_resend(db, test_org, test_user) -> None:
    from app.services import resend_settings_service

    resend_settings_service.update_resend_settings(
        db,
        test_org.id,
        test_user.id,
        email_provider="resend",
        api_key="re_test_key",
        from_email="no-reply@example.com",
        from_name="Test Org",
        verified_domain="example.com",
    )


@pytest.mark.asyncio
async def test_send_email_async_passes_linked_attachments_to_resend(
    db, test_org, test_user, monkeypatch
):
    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Worker Attachment Surrogate",
            email="worker-attachment@test.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    file_bytes = b"%PDF-1.4 worker-attachment"
    attachment: Attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="worker.pdf",
        content_type="application/pdf",
        file=BytesIO(file_bytes),
        file_size=len(file_bytes),
        surrogate_id=surrogate.id,
    )
    attachment.scan_status = "clean"
    attachment.quarantined = False

    email_log = EmailLog(
        organization_id=test_org.id,
        template_id=None,
        surrogate_id=surrogate.id,
        recipient_email="worker-attachment@test.com",
        subject="Worker Subject",
        body="<p>Worker Body</p>",
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.flush()

    db.add(
        EmailLogAttachment(
            organization_id=test_org.id,
            email_log_id=email_log.id,
            attachment_id=attachment.id,
        )
    )
    db.commit()
    db.refresh(email_log)

    _configure_org_resend(db, test_org, test_user)

    captured: dict[str, object] = {}

    async def fake_send_email_direct(**kwargs):
        captured["api_key"] = kwargs.get("api_key")
        captured["from_email"] = kwargs.get("from_email")
        captured["attachments"] = kwargs.get("attachments") or []
        return True, None, "resend-msg-1"

    from app.services import resend_email_service

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    result = await email_job_handler.send_email_async(email_log, db=db)

    assert result == "sent"
    assert captured["api_key"] == "re_test_key"
    assert captured["from_email"] == "no-reply@example.com"
    sent_attachments = captured["attachments"]
    assert isinstance(sent_attachments, list)
    assert len(sent_attachments) == 1
    assert sent_attachments[0]["filename"] == "worker.pdf"
    assert sent_attachments[0]["content_type"] == "application/pdf"
    assert sent_attachments[0]["content_bytes"] == file_bytes


@pytest.mark.asyncio
async def test_send_email_async_requires_org_resend_for_direct_email(db, test_org):
    email_log = EmailLog(
        organization_id=test_org.id,
        template_id=None,
        surrogate_id=None,
        recipient_email="direct-missing-resend@test.com",
        subject="Direct Subject",
        body="<p>Direct Body</p>",
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.commit()
    db.refresh(email_log)

    with pytest.raises(Exception) as exc:
        await email_job_handler.send_email_async(email_log, db=db)

    assert str(exc.value) == "Org Resend is not configured for direct email sending."
