"""Tests for Health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient, monkeypatch):
    """
    Test health and readiness endpoints.
    """
    from app.core import migrations as db_migrations
    from app.core import config
    from app.core.migrations import MigrationStatus

    monkeypatch.setattr(config.settings, "DB_MIGRATION_CHECK", True)
    monkeypatch.setattr(
        db_migrations,
        "get_migration_status",
        lambda *_args, **_kwargs: MigrationStatus(
            current_heads=("head",),
            head_revisions=("head",),
            is_up_to_date=True,
        ),
    )

    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
    assert "version" in data
    assert data["db_migrations"]["status"] == "ok"
    assert data["redis"]["status"] in {"ok", "disabled", "degraded"}

    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
    assert "version" in data
    assert data["db_migrations"]["status"] == "ok"
    assert data["redis"]["status"] in {"ok", "disabled", "degraded"}

    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
    assert "version" in data
    assert data["db_migrations"]["status"] == "ok"
    assert data["redis"]["status"] in {"ok", "disabled", "degraded"}


@pytest.mark.asyncio
async def test_readyz_fails_when_migrations_pending(client: AsyncClient, monkeypatch):
    from app.core import migrations as db_migrations
    from app.core import config
    from app.core.migrations import MigrationStatus

    monkeypatch.setattr(config.settings, "DB_MIGRATION_CHECK", True)
    monkeypatch.setattr(
        db_migrations,
        "get_migration_status",
        lambda *_args, **_kwargs: MigrationStatus(
            current_heads=("old",),
            head_revisions=("new",),
            is_up_to_date=False,
        ),
    )

    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database migrations pending"


@pytest.mark.asyncio
async def test_readyz_degrades_when_redis_down_and_fail_open(client: AsyncClient, monkeypatch):
    from app.core import config
    import app.main as main

    monkeypatch.setattr(config.settings, "DB_MIGRATION_CHECK", False)
    monkeypatch.setattr(config.settings, "RATE_LIMIT_FAIL_OPEN", True)
    monkeypatch.setattr(config.settings, "REDIS_REQUIRED", False)
    monkeypatch.setattr(main, "get_redis_url", lambda: "redis://localhost:6379/0")

    def _raise_client():
        raise RuntimeError("Redis down")

    monkeypatch.setattr(main, "get_sync_redis_client", _raise_client)

    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["redis"]["status"] == "degraded"
    assert data["redis"]["fail_open"] is True


@pytest.mark.asyncio
async def test_readyz_fails_when_redis_required(client: AsyncClient, monkeypatch):
    from app.core import config
    import app.main as main

    monkeypatch.setattr(config.settings, "DB_MIGRATION_CHECK", False)
    monkeypatch.setattr(config.settings, "RATE_LIMIT_FAIL_OPEN", True)
    monkeypatch.setattr(config.settings, "REDIS_REQUIRED", True)
    monkeypatch.setattr(main, "get_redis_url", lambda: "redis://localhost:6379/0")

    def _raise_client():
        raise RuntimeError("Redis down")

    monkeypatch.setattr(main, "get_sync_redis_client", _raise_client)

    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"] == "Redis unavailable"
