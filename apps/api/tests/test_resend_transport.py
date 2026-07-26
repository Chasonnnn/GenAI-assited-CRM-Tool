"""Contract tests for the shared Resend HTTP transport."""

from __future__ import annotations

import httpx
import pytest


class _FakeAsyncClient:
    def __init__(self, responses: list[httpx.Response | httpx.RequestError]):
        self._responses = iter(responses)
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
        self.requests.append({"url": url, "headers": headers, "json": json})
        result = next(self._responses)
        if isinstance(result, httpx.RequestError):
            raise result
        return result


@pytest.mark.asyncio
async def test_invalid_idempotent_request_is_a_failure_without_retry(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                409,
                json={
                    "name": "invalid_idempotent_request",
                    "message": "Same idempotency key used with a different request payload.",
                },
            )
        ]
    )
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/123",
    )

    assert result.success is False
    assert result.error_type == "invalid_idempotent_request"
    assert "different request payload" in (result.error or "")
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_concurrent_idempotent_request_is_deferred_to_durable_scheduler(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                409,
                json={
                    "name": "concurrent_idempotent_requests",
                    "message": "Original request is still in progress.",
                },
            ),
        ]
    )

    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/123",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.error_type == "concurrent_idempotent_requests"
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_rate_limit_defers_retry_after_to_durable_scheduler(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                429,
                headers={"retry-after": "2.5", "ratelimit-reset": "1"},
                json={"name": "rate_limit_exceeded", "message": "Too many requests."},
            ),
        ]
    )

    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/456",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.retry_after_seconds == 2.5
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_long_retry_after_is_deferred_to_durable_outbox_without_sleeping(
    monkeypatch,
):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                429,
                headers={"retry-after": "75"},
                json={"name": "rate_limit_exceeded", "message": "Too many requests."},
            ),
            httpx.Response(200, json={"id": "must-not-send-in-this-lease"}),
        ]
    )
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/defer-long-rate-limit",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.retry_after_seconds == 75
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_rate_limit_uses_first_response_without_inline_retries(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                429,
                headers={"retry-after": "1"},
                json={"name": "rate_limit_exceeded", "message": "Too many requests."},
            ),
        ]
    )

    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/rate-limit-exhausted",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.status_code == 429
    assert result.retry_after_seconds == 1
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    "error_type",
    [
        "daily_quota_exceeded",
        "monthly_quota_exceeded",
    ],
)
@pytest.mark.asyncio
async def test_quota_exhaustion_requires_account_action_instead_of_retry(
    monkeypatch,
    error_type,
):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                429,
                headers={"retry-after": "60"},
                json={"name": error_type, "message": "Email quota reached."},
            ),
        ]
    )
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key=f"email-log/{error_type}",
    )

    assert result.success is False
    assert result.error_type == error_type
    assert result.retryable is False
    assert result.retry_after_seconds is None
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_server_error_defers_rate_limit_reset_to_durable_scheduler(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                503,
                headers={"ratelimit-reset": "1.25"},
                json={"name": "application_error", "message": "Temporarily unavailable."},
            ),
        ]
    )

    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/789-server-retry",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.retry_after_seconds == 1.25
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_request_error_is_deferred_to_durable_scheduler(monkeypatch):
    from app.services import resend_transport

    request = httpx.Request("POST", resend_transport.RESEND_SEND_URL)
    client = _FakeAsyncClient(
        [
            httpx.ConnectError("connection reset", request=request),
        ]
    )

    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/789-network-retry",
    )

    assert result.success is False
    assert result.retryable is True
    assert result.error_type == "network_error"
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_request_error_without_idempotency_key_is_not_retried(monkeypatch):
    from app.services import resend_transport

    request = httpx.Request("POST", resend_transport.RESEND_SEND_URL)
    client = _FakeAsyncClient(
        [
            httpx.ReadTimeout("response timeout after request write", request=request),
            httpx.Response(200, json={"id": "duplicate_if_retried"}),
        ]
    )
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
    )

    assert result.success is False
    assert result.error_type == "timeout"
    assert result.retryable is False
    assert result.ambiguous is True
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_server_error_without_idempotency_key_is_not_retried(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient(
        [
            httpx.Response(
                503,
                json={"name": "application_error", "message": "Temporarily unavailable."},
            ),
            httpx.Response(200, json={"id": "duplicate_if_retried"}),
        ]
    )
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
    )

    assert result.success is False
    assert result.status_code == 503
    assert result.retryable is False
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_success_without_message_id_is_rejected(monkeypatch):
    from app.services import resend_transport

    client = _FakeAsyncClient([httpx.Response(200, json={})])
    monkeypatch.setattr(resend_transport.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await resend_transport.send_email(
        api_key="re_test",
        payload={
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "html": "<p>Hello</p>",
        },
        idempotency_key="email-log/789",
    )

    assert result.success is False
    assert result.error_type == "invalid_success_response"
    assert result.ambiguous is True
