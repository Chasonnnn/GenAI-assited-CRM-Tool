import inspect

import pytest

from app.core import rate_limit


class DummyLimiter:
    def __init__(self, *, raise_exc: Exception | None = None):
        self._raise_exc = raise_exc

    def limit(self, *_args, **_kwargs):
        def decorator(func):
            if inspect.iscoroutinefunction(func):

                async def async_wrapped(*f_args, **f_kwargs):
                    if self._raise_exc:
                        raise self._raise_exc
                    return await func(*f_args, **f_kwargs)

                return async_wrapped

            def sync_wrapped(*f_args, **f_kwargs):
                if self._raise_exc:
                    raise self._raise_exc
                return func(*f_args, **f_kwargs)

            return sync_wrapped

        return decorator

    def exempt(self, func):
        return func


class FakeRedisError(Exception):
    pass


@pytest.mark.asyncio
async def test_rate_limit_fail_open_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(rate_limit, "FAIL_OPEN", True)
    monkeypatch.setattr(rate_limit, "FALLBACK_SECONDS", 0)
    monkeypatch.setattr(rate_limit, "REDIS_ERROR_TYPES", (FakeRedisError,))

    redis_limiter = DummyLimiter(raise_exc=FakeRedisError("boom"))
    memory_limiter = DummyLimiter()
    limiter = rate_limit.FailOpenLimiter(redis_limiter, memory_limiter)

    async def handler():
        return "ok"

    decorated = limiter.limit("1/minute")(handler)
    assert await decorated() == "ok"


@pytest.mark.asyncio
async def test_rate_limit_fail_closed_raises(monkeypatch):
    monkeypatch.setattr(rate_limit, "FAIL_OPEN", False)
    monkeypatch.setattr(rate_limit, "REDIS_ERROR_TYPES", (FakeRedisError,))

    redis_limiter = DummyLimiter(raise_exc=FakeRedisError("boom"))
    memory_limiter = DummyLimiter()
    limiter = rate_limit.FailOpenLimiter(redis_limiter, memory_limiter)

    async def handler():
        return "ok"

    decorated = limiter.limit("1/minute")(handler)
    with pytest.raises(FakeRedisError):
        await decorated()


def test_rate_limit_preserves_handler_signature(monkeypatch):
    monkeypatch.setattr(rate_limit, "FAIL_OPEN", True)
    monkeypatch.setattr(rate_limit, "REDIS_ERROR_TYPES", (FakeRedisError,))

    redis_limiter = DummyLimiter()
    memory_limiter = DummyLimiter()
    limiter = rate_limit.FailOpenLimiter(redis_limiter, memory_limiter)

    async def handler(request, user_id: str, *, include_archived: bool = False):
        return request, user_id, include_archived

    decorated = limiter.limit("1/minute")(handler)

    assert inspect.signature(decorated) == inspect.signature(handler)
