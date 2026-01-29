"""Rate limiting configuration for the Surrogacy Force API."""

import logging
import os
import inspect
import time

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
FALLBACK_SECONDS = int(os.getenv("RATE_LIMIT_REDIS_FALLBACK_SECONDS", "30"))

try:  # Optional for tests without redis installed
    from redis.exceptions import RedisError as _RedisError
    from redis.exceptions import ConnectionError as _RedisConnectionError

    REDIS_ERROR_TYPES = (_RedisError, _RedisConnectionError)
except Exception:  # pragma: no cover - redis not installed in some envs
    REDIS_ERROR_TYPES = (Exception,)


class FailOpenLimiter:
    """Limiter wrapper that falls back to in-memory on Redis errors."""

    def __init__(self, redis_limiter: Limiter, memory_limiter: Limiter):
        self._redis = redis_limiter
        self._memory = memory_limiter
        self._fallback_until = 0.0

    def _fallback_active(self) -> bool:
        return FAIL_OPEN and self._fallback_until > time.monotonic()

    def _activate_fallback(self) -> None:
        if FALLBACK_SECONDS <= 0:
            self._fallback_until = time.monotonic()
        else:
            self._fallback_until = time.monotonic() + FALLBACK_SECONDS

    def limit(self, *args, **kwargs):  # type: ignore[override]
        redis_decorator = self._redis.limit(*args, **kwargs)
        memory_decorator = self._memory.limit(*args, **kwargs)

        def decorator(func):
            redis_wrapped = redis_decorator(func)
            memory_wrapped = memory_decorator(func)

            if inspect.iscoroutinefunction(func):

                async def async_wrapped(*f_args, **f_kwargs):
                    if self._fallback_active():
                        return await memory_wrapped(*f_args, **f_kwargs)
                    try:
                        return await redis_wrapped(*f_args, **f_kwargs)
                    except REDIS_ERROR_TYPES as exc:
                        if not FAIL_OPEN:
                            raise
                        logging.warning("Redis rate limit failed, falling back to memory: %s", exc)
                        self._activate_fallback()
                        return await memory_wrapped(*f_args, **f_kwargs)

                return async_wrapped

            def sync_wrapped(*f_args, **f_kwargs):
                if self._fallback_active():
                    return memory_wrapped(*f_args, **f_kwargs)
                try:
                    return redis_wrapped(*f_args, **f_kwargs)
                except REDIS_ERROR_TYPES as exc:
                    if not FAIL_OPEN:
                        raise
                    logging.warning("Redis rate limit failed, falling back to memory: %s", exc)
                    self._activate_fallback()
                    return memory_wrapped(*f_args, **f_kwargs)

            return sync_wrapped

        return decorator

    def exempt(self, *args, **kwargs):  # type: ignore[override]
        return self._redis.exempt(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._redis, name)


memory_limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=DEFAULT_LIMITS,
)

if IS_TESTING:
    limiter = memory_limiter
elif not REDIS_URL:
    if FAIL_OPEN:
        limiter = memory_limiter
    else:
        raise RuntimeError("REDIS_URL must be set when RATE_LIMIT_FAIL_OPEN is false")
else:
    try:
        client = get_sync_redis_client()
        if client is None:
            raise RuntimeError("Redis client unavailable")
        client.ping()
        redis_limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL,
            default_limits=DEFAULT_LIMITS,
        )
        limiter = FailOpenLimiter(redis_limiter, memory_limiter) if FAIL_OPEN else redis_limiter
    except Exception as exc:
        if FAIL_OPEN:
            logging.warning("Redis unavailable for rate limiting, using in-memory: %s", exc)
            limiter = memory_limiter
        else:
            raise RuntimeError("Redis is required for rate limiting") from exc
