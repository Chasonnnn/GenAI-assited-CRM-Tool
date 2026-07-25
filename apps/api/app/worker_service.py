"""Cloud Run service entrypoint for the background worker."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.worker import _ensure_attachment_scanner_available, _sync_clamav_signatures, worker_loop

_worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _worker_task
    _sync_clamav_signatures()
    _ensure_attachment_scanner_available()
    stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(worker_loop(stop_event))
    try:
        yield
    finally:
        if _worker_task:
            stop_event.set()
            await _worker_task
            _worker_task = None


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    # Cloud Run requires binding to all interfaces.
    host = os.getenv("HOST", "0.0.0.0")  # nosec
    uvicorn.run("app.worker_service:app", host=host, port=port)


if __name__ == "__main__":
    main()
