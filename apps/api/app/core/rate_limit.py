"""Rate limiting configuration for the CRM API."""

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Configure rate limiter with Redis for multi-worker support
# Falls back to in-memory if Redis is not available (dev/test mode)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")

if IS_TESTING:
    # Use in-memory storage for tests (no Redis dependency)
    limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
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
        )
    except Exception as e:
        logging.warning(f"Redis unavailable for rate limiting, using in-memory: {e}")
        limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
