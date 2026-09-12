"""Verify model upgrades preserve non-Google settings and support rollback."""

import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace


def test_google_model_upgrade_and_downgrade(monkeypatch):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260907_1200_upgrade_gemini_38_flash.py"
    )
    spec = importlib.util.spec_from_file_location("gemini_38_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    defaults = []
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE ai_settings (provider TEXT, model TEXT)")
        rows = [
            ("gemini", "gemini-3.7-flash"),
            ("vertex_wif", None),
            ("vertex_api_key", "gemini-3-flash-preview"),
            ("other", "custom-model"),
        ]
        db.executemany("INSERT INTO ai_settings VALUES (?, ?)", rows)
        monkeypatch.setattr(
            migration,
            "op",
            SimpleNamespace(
                alter_column=lambda *args, **kwargs: defaults.append(
                    str(kwargs["server_default"])
                ),
                execute=db.execute,
            ),
        )
        migration.upgrade()
        assert db.execute("SELECT provider, model FROM ai_settings").fetchall() == [
            (provider, "gemini-3.8-flash") for provider, _ in rows[:3]
        ] + [rows[3]]
        migration.downgrade()
        assert db.execute("SELECT provider, model FROM ai_settings").fetchall() == [
            (provider, "gemini-3.7-flash") for provider, _ in rows[:3]
        ] + [rows[3]]
        assert defaults == ["'gemini-3.8-flash'", "'gemini-3.7-flash'"]
