"""HTTP helpers with retry/backoff for integrations."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

DEFAULT_RETRY_STATUSES = {429, 500, 502, 503, 504}


async def request_with_retries(
    request_fn: Callable[[], Awaitable[httpx.Response]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    retry_statuses: set[int] | None = None,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff retries."""
    statuses = retry_statuses or DEFAULT_RETRY_STATUSES

    for attempt in range(max_attempts):
        try:
            response = await request_fn()
        except httpx.RequestError as exc:
            if attempt >= max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            if delay:
                delay = delay + random.uniform(0, delay / 2)
            logger.warning("HTTP request failed, retrying", exc_info=exc)
            if delay:
                await asyncio.sleep(delay)
            continue

        if response.status_code in statuses and attempt < max_attempts - 1:
            delay = min(max_delay, base_delay * (2**attempt))
            if delay:
                delay = delay + random.uniform(0, delay / 2)
            logger.warning(
                "HTTP request returned %s, retrying", response.status_code
            )
            if delay:
                await asyncio.sleep(delay)
            continue

        return response

    return response
