"""Unexpected API failures remain readable without blocking the event loop."""

import asyncio
import threading

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import main


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ["http://localhost:3000", "https://untrusted.example"])
async def test_unhandled_error_has_safe_response_and_allowed_origin_headers(monkeypatch, origin):
    # Use the production middleware stack without adding a test route to the shared app.
    app = FastAPI()
    app.user_middleware = main.app.user_middleware.copy()
    monkeypatch.setattr(main, "report_exception", lambda *_args: None)
    monkeypatch.setattr(main, "_record_api_error_alert", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "_record_metrics", lambda *_args: None)

    @app.get("/synthetic-failure")
    def fail():
        raise RuntimeError("private exception detail")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="https://test"
    ) as client:
        response = await client.get("/synthetic-failure", headers={"Origin": origin})

    assert response.status_code == 500
    if origin == "http://localhost:3000":
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers
    assert response.text == "Internal Server Error"
    assert "private exception detail" not in response.text


@pytest.mark.asyncio
async def test_error_alert_wait_does_not_block_event_loop(monkeypatch):
    release = threading.Event()
    alert_finished = []
    monkeypatch.setattr(main, "report_exception", lambda *_args: None)

    def record_alert(*_args, **_kwargs):
        alert_finished.append(release.wait(timeout=0.2))

    async def release_alert():
        await asyncio.sleep(0.01)
        release.set()

    async def fail(_request):
        raise RuntimeError("synthetic failure")

    from starlette.requests import Request

    request = Request(
        {"type": "http", "method": "GET", "path": "/synthetic-failure", "headers": []}
    )
    monkeypatch.setattr(main, "_record_api_error_alert", record_alert)
    release_task = asyncio.create_task(release_alert())
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            await main.gcp_error_reporting_middleware(request, fail)
        assert alert_finished == [True]
    finally:
        await release_task
