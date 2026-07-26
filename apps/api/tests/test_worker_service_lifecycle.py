"""Graceful worker-service shutdown contracts."""

from __future__ import annotations

import asyncio

import pytest

from app import worker_service


@pytest.mark.asyncio
async def test_lifespan_signals_stop_and_drains_active_worker(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    captured: dict[str, object] = {"cancelled": False}

    async def _worker_loop(stop_event=None):
        captured["stop_event"] = stop_event
        started.set()
        try:
            await release.wait()
            finished.set()
        except asyncio.CancelledError:
            captured["cancelled"] = True
            raise

    monkeypatch.setattr(worker_service, "_worker_task", None)
    monkeypatch.setattr(worker_service, "_sync_clamav_signatures", lambda: None)
    monkeypatch.setattr(worker_service, "_ensure_attachment_scanner_available", lambda: None)
    monkeypatch.setattr(worker_service, "worker_loop", _worker_loop)

    lifespan = worker_service.lifespan(None)
    await lifespan.__aenter__()
    await asyncio.wait_for(started.wait(), timeout=1)
    shutdown = asyncio.create_task(lifespan.__aexit__(None, None, None))
    await asyncio.sleep(0)

    try:
        stop_event = captured["stop_event"]
        assert isinstance(stop_event, asyncio.Event)
        assert stop_event.is_set()
        assert shutdown.done() is False
    finally:
        release.set()
        await asyncio.wait_for(shutdown, timeout=1)

    assert finished.is_set()
    assert captured["cancelled"] is False


@pytest.mark.asyncio
async def test_worker_shutdown_stops_claiming_within_cloud_run_budget(monkeypatch):
    started = asyncio.Event()
    stop_observed = asyncio.Event()
    cancelled = asyncio.Event()

    async def _worker_loop(stop_event=None):
        started.set()
        assert isinstance(stop_event, asyncio.Event)
        await stop_event.wait()
        stop_observed.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(worker_service, "_worker_task", None)
    monkeypatch.setattr(worker_service, "WORKER_SHUTDOWN_DRAIN_SECONDS", 0.01)
    monkeypatch.setattr(worker_service, "_sync_clamav_signatures", lambda: None)
    monkeypatch.setattr(worker_service, "_ensure_attachment_scanner_available", lambda: None)
    monkeypatch.setattr(worker_service, "worker_loop", _worker_loop)

    lifespan = worker_service.lifespan(None)
    await lifespan.__aenter__()
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(lifespan.__aexit__(None, None, None), timeout=0.25)

    assert stop_observed.is_set()
    assert cancelled.is_set()
    assert worker_service._worker_task is None
