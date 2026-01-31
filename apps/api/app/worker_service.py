"""Cloud Run service entrypoint for the background worker."""

from __future__ import annotations

import asyncio
import contextlib
import os

from fastapi import FastAPI

from app.worker import _ensure_attachment_scanner_available, _sync_clamav_signatures, worker_loop

app = FastAPI()
_worker_task: asyncio.Task | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def _startup() -> None:
    _sync_clamav_signatures()
    _ensure_attachment_scanner_available()
    global _worker_task
    _worker_task = asyncio.create_task(worker_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _worker_task:
        _worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _worker_task


def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    # nosec B104 - Cloud Run requires binding to all interfaces.
    uvicorn.run("app.worker_service:app", host=host, port=port)


if __name__ == "__main__":
    main()
