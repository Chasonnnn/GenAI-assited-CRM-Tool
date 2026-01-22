"""Rate limiting configuration for the Surrogacy Force API."""

import logging
import os
import inspect

from slowapi import Limiter
from slowapi.util import get_remote_address
import slowapi.extension as slowapi_extension

from app.core.config import settings
from app.core.redis_client import get_redis_url, get_sync_redis_client

# Patch slowapi for Python 3.14+ where asyncio.iscoroutinefunction is deprecated.
slowapi_extension.asyncio.iscoroutinefunction = inspect.iscoroutinefunction

# Configure rate limiter with Redis for multi-worker support.
# Falls back to in-memory storage if Redis is unavailable.
REDIS_URL = get_redis_url()
IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")
FAIL_OPEN = settings.RATE_LIMIT_FAIL_OPEN
DEFAULT_LIMITS = (
    [] if IS_TESTING or settings.RATE_LIMIT_API <= 0 else [f"{settings.RATE_LIMIT_API}/minute"]
)

if IS_TESTING:
    # Use in-memory storage for tests (no Redis dependency)
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=DEFAULT_LIMITS,
    )
elif not REDIS_URL:
    if FAIL_OPEN:
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
            default_limits=DEFAULT_LIMITS,
        )
    else:
        raise RuntimeError("REDIS_URL must be set when RATE_LIMIT_FAIL_OPEN is false")
else:
    try:
        client = get_sync_redis_client()
        if client is None:
            raise RuntimeError("Redis client unavailable")
        client.ping()
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL,
            default_limits=DEFAULT_LIMITS,
        )
    except Exception as exc:
        if FAIL_OPEN:
            logging.warning("Redis unavailable for rate limiting, using in-memory: %s", exc)
            limiter = Limiter(
                key_func=get_remote_address,
                storage_uri="memory://",
                default_limits=DEFAULT_LIMITS,
            )
        else:
            raise RuntimeError("Redis is required for rate limiting") from exc
