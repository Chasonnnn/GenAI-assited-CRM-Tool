import httpx
import pytest
import base64


@pytest.mark.asyncio
async def test_send_email_logged_marks_failed_on_exception(db, test_org, monkeypatch):
    from app.db.enums import EmailStatus
    from app.db.models import EmailLog
    from app.services import platform_email_service

    async def boom(**_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(platform_email_service, "_send_resend_email", boom)

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
    assert result["email_log_id"] is not None

    log = db.query(EmailLog).filter(EmailLog.id == result["email_log_id"]).one()
    assert log.status == EmailStatus.FAILED.value
    assert log.error


@pytest.mark.asyncio
async def test_send_email_logged_generates_text_fallback(db, test_org, monkeypatch):
    from app.services import platform_email_service

    async def fake_send_resend_email(**kwargs):
        # We should always include text for deliverability, even if callers only provide HTML.
        assert kwargs["text"]
        assert "<" not in kwargs["text"]
        assert "Hello" in kwargs["text"]
        assert "world" in kwargs["text"]
        return {"success": True, "message_id": "msg_123"}

    monkeypatch.setattr(platform_email_service, "_send_resend_email", fake_send_resend_email)

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
    assert result["message_id"] == "msg_123"


@pytest.mark.asyncio
async def test_send_resend_email_treats_409_as_duplicate_success(monkeypatch):
    from app.services import platform_email_service

    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_RESEND_API_KEY", "re_test_key")

    async def fake_request_with_retries(_request_fn, **_kwargs):
        return httpx.Response(409, json={"message": "Idempotency key already used"})

    monkeypatch.setattr(platform_email_service, "request_with_retries", fake_request_with_retries)

    result = await platform_email_service._send_resend_email(
        to_email="to@example.com",
        subject="Hello",
        from_email="Invites <invites@surrogacyforce.com>",
        html="<p>Hello</p>",
        text="Hello",
        idempotency_key="dup-key",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_send_resend_email_includes_attachment_payload(monkeypatch):
    from app.services import platform_email_service

    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_RESEND_API_KEY", "re_test_key")

    captured: dict[str, object] = {}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, _url, headers=None, json=None):
            captured["headers"] = headers
            captured["payload"] = json
            return httpx.Response(200, json={"id": "msg_123"})

    async def fake_request_with_retries(request_fn, **_kwargs):
        return await request_fn()

    monkeypatch.setattr(
        platform_email_service.httpx, "AsyncClient", lambda **_kwargs: _FakeAsyncClient()
    )
    monkeypatch.setattr(platform_email_service, "request_with_retries", fake_request_with_retries)

    attachment_bytes = b"hello world"
    result = await platform_email_service._send_resend_email(
        to_email="to@example.com",
        subject="Hello",
        from_email="Invites <invites@surrogacyforce.com>",
        html="<p>Hello</p>",
        text="Hello",
        idempotency_key="attachments-idem",
        attachments=[
            {
                "filename": "greeting.txt",
                "content_type": "text/plain",
                "content_bytes": attachment_bytes,
            }
        ],
    )

    assert result["success"] is True
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "attachments" in payload
    assert payload["attachments"][0]["filename"] == "greeting.txt"
    assert payload["attachments"][0]["type"] == "text/plain"
    assert payload["attachments"][0]["content"] == base64.b64encode(attachment_bytes).decode(
        "ascii"
    )
