import pytest


@pytest.mark.asyncio
async def test_send_email_logged_queues_platform_message_without_inline_network(
    db,
    test_org,
    monkeypatch,
):
    from app.db.enums import EmailDeliveryStatus, EmailProviderScope, EmailStatus
    from app.db.models import EmailDelivery, EmailLog
    from app.services import platform_email_service

    monkeypatch.setattr(
        platform_email_service.settings,
        "PLATFORM_RESEND_API_KEY",
        "re_test_key",
    )

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        to_email="to@example.com",
        subject="Hello",
        from_email="Invites <invites@surrogacyforce.com>",
        html="<p>Hello <strong>world</strong></p>",
        text=None,
        idempotency_key="platform-queued-message",
    )

    assert result["success"] is True
    assert result["queued"] is True
    assert result["message_id"] is None

    email_log = db.get(EmailLog, result["email_log_id"])
    assert email_log.status == EmailStatus.PENDING.value
    assert email_log.provider_scope == EmailProviderScope.PLATFORM.value
    assert email_log.text_body == "Hello world"
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == email_log.id,
        )
        .one()
    )
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.provider_account_id == "platform:default"


@pytest.mark.asyncio
async def test_send_email_logged_does_not_enqueue_when_platform_sender_is_unconfigured(
    db,
    test_org,
    monkeypatch,
):
    from app.db.models import EmailLog
    from app.services import platform_email_service

    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_RESEND_API_KEY", "")

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        to_email="to@example.com",
        subject="Hello",
        from_email="Invites <invites@surrogacyforce.com>",
        html="<p>Hello</p>",
        text=None,
        idempotency_key="test-idem-exception",
    )

    assert result["success"] is False
    assert result["queued"] is False
    assert "not configured" in result["error"]
    assert db.query(EmailLog).filter(EmailLog.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_send_email_logged_generates_text_fallback(db, test_org, monkeypatch):
    from app.db.models import EmailLog
    from app.services import platform_email_service

    monkeypatch.setattr(
        platform_email_service.settings,
        "PLATFORM_RESEND_API_KEY",
        "re_test_key",
    )

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=test_org.id,
        to_email="to@example.com",
        subject="Hello",
        from_email="Invites <invites@surrogacyforce.com>",
        html="<p>Hello <strong>world</strong></p>",
        text=None,
        idempotency_key="test-idem-text",
    )

    assert result["success"] is True
    assert result["queued"] is True
    assert result["message_id"] is None
    email_log = db.get(EmailLog, result["email_log_id"])
    assert email_log.text_body
    assert "<" not in email_log.text_body
    assert "Hello" in email_log.text_body
    assert "world" in email_log.text_body
    assert email_log.safe_tags == [
        {"name": "message_kind", "value": "platform_transactional"},
        {"name": "organization_id", "value": str(test_org.id)},
        {"name": "email_log_id", "value": str(email_log.id)},
    ]
