from __future__ import annotations

import asyncio
from typing import Coroutine, TypeVar

import anyio

T = TypeVar("T")


def run_async(coro: Coroutine[object, object, T], *, timeout: float | None = None) -> T:
    """
    Run an async coroutine from sync code without asyncio.run in request threads.

    - In FastAPI sync endpoints, uses anyio.from_thread.run to execute on the main loop.
    - Falls back to anyio.run when no AnyIO worker thread is available (e.g., CLI/tests).
    - Raises if called from an async context in the same thread (use await instead).
    """

    async def _runner() -> T:
        if timeout is not None:
            with anyio.fail_after(timeout):
                return await coro
        return await coro

    try:
        return anyio.from_thread.run(_runner)
    except RuntimeError:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return anyio.run(_runner)
        raise RuntimeError("run_async called from async context; use await instead")
