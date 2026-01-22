import importlib


def _reload_redis_client(monkeypatch, *, redis_url=None, max_connections=None):
    if redis_url is None:
        monkeypatch.delenv("REDIS_URL", raising=False)
    else:
        monkeypatch.setenv("REDIS_URL", redis_url)

    if max_connections is None:
        monkeypatch.delenv("REDIS_MAX_CONNECTIONS", raising=False)
    else:
        monkeypatch.setenv("REDIS_MAX_CONNECTIONS", str(max_connections))

    import app.core.redis_client as redis_client

    return importlib.reload(redis_client)


def test_get_redis_url_disabled(monkeypatch):
    redis_client = _reload_redis_client(monkeypatch, redis_url=None)
    assert redis_client.get_redis_url() is None

    redis_client = _reload_redis_client(monkeypatch, redis_url="memory://")
    assert redis_client.get_redis_url() is None


def test_get_sync_client_uses_pool_limit(monkeypatch):
    redis_client = _reload_redis_client(
        monkeypatch,
        redis_url="redis://localhost:6379/0",
        max_connections=7,
    )
    client = redis_client.get_sync_redis_client()
    assert client is not None
    assert client.connection_pool.max_connections == 7


def test_get_sync_client_none_when_unset(monkeypatch):
    redis_client = _reload_redis_client(monkeypatch, redis_url=None)
    client = redis_client.get_sync_redis_client()
    assert client is None
