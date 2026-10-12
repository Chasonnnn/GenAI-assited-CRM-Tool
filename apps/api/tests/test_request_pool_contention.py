"""Waiting HTTP requests must leave worker threads available to connection owners."""

import asyncio
from typing import Annotated

import pytest
from anyio import to_thread
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import deps


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", [False, True])
async def test_request_burst_completes_without_pool_starvation(db_engine, monkeypatch, denied):
    request_engine = create_engine(db_engine.url, pool_size=2, max_overflow=0, pool_timeout=0.3)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=request_engine))
    monkeypatch.setattr(deps.settings, "DB_POOL_SIZE", 2)
    monkeypatch.setattr(deps.settings, "DB_MAX_OVERFLOW", 0)
    monkeypatch.setattr(to_thread.current_default_thread_limiter(), "total_tokens", 4)
    app = FastAPI()

    def authenticate(db: Annotated[Session, Depends(deps.get_db)]):
        assert db.scalar(text("SELECT 1")) == 1

    async def after_authentication(_auth: Annotated[None, Depends(authenticate)]):
        # Another dependency awaits while the authenticated request owns a connection.
        await asyncio.sleep(0.03)

    @app.get("/work", dependencies=[Depends(after_authentication)])
    def work(db: Annotated[Session, Depends(deps.get_db)], reject: bool = False) -> dict:
        if reject:
            raise HTTPException(403, "Denied")
        return {"value": db.scalar(text("SELECT 1"))}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *(client.get("/work", params={"reject": denied}) for _ in range(12))
            )
            assert [response.status_code for response in responses] == [403 if denied else 200] * 12
            assert (await client.get("/work")).json() == {"value": 1}
        assert request_engine.pool.checkedout() == 0
    finally:
        request_engine.dispose()


@pytest.mark.asyncio
async def test_admission_timeout_and_cancelled_requests_release_capacity(db_engine, monkeypatch):
    request_engine = create_engine(db_engine.url, pool_size=1, max_overflow=0, pool_timeout=0.3)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=request_engine))
    monkeypatch.setattr(deps.settings, "DB_POOL_SIZE", 1)
    monkeypatch.setattr(deps.settings, "DB_MAX_OVERFLOW", 0)
    monkeypatch.setattr(deps.settings, "DB_POOL_TIMEOUT", 1)
    app = FastAPI()
    entered = asyncio.Event()
    release = asyncio.Event()

    @app.get("/hold")
    async def hold(db: Annotated[Session, Depends(deps.get_db)]) -> dict:
        assert db.scalar(text("SELECT 1")) == 1
        entered.set()
        await release.wait()
        return {}

    @app.get("/work")
    def work(db: Annotated[Session, Depends(deps.get_db)]) -> dict:
        return {"value": db.scalar(text("SELECT 1"))}

    owner = waiting = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner = asyncio.create_task(client.get("/hold"))
            await asyncio.wait_for(entered.wait(), timeout=2)
            waiting = asyncio.create_task(client.get("/work"))
            await asyncio.sleep(0.02)
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
            busy = await client.get("/work")
            assert busy.status_code == 503
            assert request_engine.pool.checkedout() == 1
            owner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert (await client.get("/work")).json() == {"value": 1}
            assert request_engine.pool.checkedout() == 0
    finally:
        release.set()
        for task in (owner, waiting):
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        request_engine.dispose()
