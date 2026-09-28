import asyncio
import inspect

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


@pytest.mark.anyio
@pytest.mark.parametrize("error_type", [RuntimeError, anyio.NoEventLoopError])
async def test_run_async_preserves_coroutine_failure_without_replaying(error_type) -> None:
    calls = 0
    failure = error_type("provider operation failed")

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await anyio.to_thread.run_sync(lambda: run_async(fail()))

    assert caught.value is failure
    assert calls == 1


@pytest.mark.anyio
async def test_run_async_closes_rejected_coroutine_in_async_context() -> None:
    coroutine = _sample()
    try:
        with pytest.raises(RuntimeError, match="use await instead"):
            run_async(coroutine)
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
    finally:
        coroutine.close()


def test_run_async_supports_plain_synchronous_callers() -> None:
    assert run_async(_sample()) == "ok"
