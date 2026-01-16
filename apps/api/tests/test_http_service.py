"""Tests for HTTP retry helper."""

import httpx
import pytest

from app.services.http_service import request_with_retries


@pytest.mark.asyncio
async def test_request_with_retries_retries_on_status():
    req = httpx.Request("POST", "https://example.com")
    responses = [
        httpx.Response(500, request=req),
        httpx.Response(200, json={"ok": True}, request=req),
    ]
    calls = {"count": 0}

    async def request_fn():
        calls["count"] += 1
        return responses.pop(0)

    response = await request_with_retries(
        request_fn,
        max_attempts=2,
        base_delay=0,
        max_delay=0,
    )

    assert calls["count"] == 2
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_with_retries_retries_on_request_error():
    req = httpx.Request("POST", "https://example.com")
    calls = {"count": 0}

    async def request_fn():
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("boom", request=req)
        return httpx.Response(200, json={"ok": True}, request=req)

    response = await request_with_retries(
        request_fn,
        max_attempts=2,
        base_delay=0,
        max_delay=0,
    )

    assert calls["count"] == 2
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_with_retries_raises_after_max_attempts():
    req = httpx.Request("POST", "https://example.com")
    calls = {"count": 0}

    async def request_fn():
        calls["count"] += 1
        raise httpx.ConnectError("boom", request=req)

    with pytest.raises(httpx.RequestError):
        await request_with_retries(
            request_fn,
            max_attempts=2,
            base_delay=0,
            max_delay=0,
        )

    assert calls["count"] == 2
