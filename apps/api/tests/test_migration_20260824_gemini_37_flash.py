"""Regression tests for the Gemini 3.7 Flash settings migration."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    API_ROOT / "alembic" / "versions" / "20260824_1200_upgrade_gemini_37_flash.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("gemini_37_flash_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_sets_default_and_migrates_all_google_providers(monkeypatch):
    migration = _load_migration_module()
    calls: list[tuple[str, object]] = []
    fake_op = SimpleNamespace(
        alter_column=lambda *args, **kwargs: calls.append(("alter_column", (args, kwargs))),
        execute=lambda statement: calls.append(("execute", statement)),
    )
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    alter_kwargs = calls[0][1][1]
    assert str(alter_kwargs["server_default"]) == "'gemini-3.7-flash'"
    update_sql = str(calls[1][1])
    assert "SET model = 'gemini-3.7-flash'" in update_sql
    assert "'gemini', 'vertex_wif', 'vertex_api_key'" in update_sql
    location_sql = str(calls[2][1])
    assert "SET vertex_location = 'us'" in location_sql
    assert "'global', 'us', 'eu'" in location_sql


def test_downgrade_only_reverts_gemini_37_flash(monkeypatch):
    migration = _load_migration_module()
    statements: list[str] = []
    fake_op = SimpleNamespace(
        alter_column=lambda *_args, **_kwargs: None,
        execute=lambda statement: statements.append(str(statement)),
    )
    monkeypatch.setattr(migration, "op", fake_op)

    migration.downgrade()

    assert "SET model = 'gemini-3-flash-preview'" in statements[0]
    assert "AND model = 'gemini-3.7-flash'" in statements[0]
