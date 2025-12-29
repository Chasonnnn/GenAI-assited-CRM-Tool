"""Rate limiting configuration for the CRM API."""

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Configure rate limiter with Redis for multi-worker support
# Falls back to in-memory if Redis is not available (dev/test mode)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")
DEFAULT_LIMITS = (
    []
    if IS_TESTING or settings.RATE_LIMIT_API <= 0
    else [f"{settings.RATE_LIMIT_API}/minute"]
)

if IS_TESTING:
    # Use in-memory storage for tests (no Redis dependency)
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=DEFAULT_LIMITS,
    )
else:
    # Try Redis, fall back to memory if connection fails
    try:
        import redis

        # Test connection upfront
        r = redis.from_url(REDIS_URL, socket_connect_timeout=1)
        r.ping()
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL,
            default_limits=DEFAULT_LIMITS,
        )
    except Exception as e:
        logging.warning(f"Redis unavailable for rate limiting, using in-memory: {e}")
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
            default_limits=DEFAULT_LIMITS,
        )
