import asyncio

import anyio
import pytest

from app.core.async_utils import run_async


async def _sample() -> str:
    await anyio.sleep(0)
    return "ok"


@pytest.mark.anyio
async def test_run_async_avoids_asyncio_run_in_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_run(*_args: object, **_kwargs: object) -> None:
        pytest.fail("asyncio.run should not be used in request threads")

    monkeypatch.setattr(asyncio, "run", _fail_run)

    def _call() -> str:
        return run_async(_sample())

    result = await anyio.to_thread.run_sync(_call)
    assert result == "ok"
