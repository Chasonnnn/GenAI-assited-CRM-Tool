from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260209_1200_add_surrogate_full_application_form_template.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260209_1200", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeConnection:
    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return _FakeResult(self._row)


def test_fetch_base_snapshot_uses_fallback_when_base_template_missing(monkeypatch):
    migration = _load_migration_module()

    fallback_schema = {"pages": [{"title": "Fallback", "fields": [{"key": "name"}]}]}
    fallback_settings = {"privacy_notice": "Fallback notice"}

    monkeypatch.setattr(
        migration,
        "_load_fallback_base_snapshot",
        lambda: (fallback_schema, fallback_settings),
    )

    schema, settings = migration._fetch_base_snapshot(
        _FakeConnection(None),
        migration._template_table(),
    )

    assert schema == fallback_schema
    assert settings == fallback_settings
