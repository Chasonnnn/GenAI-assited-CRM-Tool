"""Redis client helpers with connection pooling."""

from __future__ import annotations

import os

REDIS_DISABLED_URL = "memory://"
DEFAULT_REDIS_MAX_CONNECTIONS = 20
DEFAULT_REDIS_CONNECT_TIMEOUT_SECONDS = 2.0
DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS = 2.0
DEFAULT_REDIS_HEALTH_CHECK_SECONDS = 30

_sync_client = None
_async_client = None


def get_redis_url() -> str | None:
    url = os.getenv("REDIS_URL")
    if not url or url.strip().lower() == REDIS_DISABLED_URL:
        return None
    return url.strip()


def _redis_max_connections() -> int:
    value = os.getenv("REDIS_MAX_CONNECTIONS", "").strip()
    if value.isdigit():
        parsed = int(value)
        if parsed > 0:
            return parsed
    return DEFAULT_REDIS_MAX_CONNECTIONS


def get_sync_redis_client():
    url = get_redis_url()
    if not url:
        return None

    global _sync_client
    if _sync_client is None:
        import redis

        pool = redis.ConnectionPool.from_url(
            url,
            max_connections=_redis_max_connections(),
            socket_connect_timeout=DEFAULT_REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=DEFAULT_REDIS_HEALTH_CHECK_SECONDS,
            retry_on_timeout=True,
        )
        _sync_client = redis.Redis(connection_pool=pool)
    return _sync_client


def get_async_redis_client():
    url = get_redis_url()
    if not url:
        return None

    global _async_client
    if _async_client is None:
        import redis.asyncio as redis

        pool = redis.ConnectionPool.from_url(
            url,
            max_connections=_redis_max_connections(),
            socket_connect_timeout=DEFAULT_REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=DEFAULT_REDIS_HEALTH_CHECK_SECONDS,
            retry_on_timeout=True,
        )
        _async_client = redis.Redis(connection_pool=pool)
    return _async_client
