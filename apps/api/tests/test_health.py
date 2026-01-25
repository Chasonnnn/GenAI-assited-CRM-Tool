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

    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
    assert "version" in data
    assert data["db_migrations"]["status"] == "ok"

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
