from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260406_1700_canonicalize_surrogate_height_precision.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260406_1700", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_widens_height_precision_and_backfills_canonical_inches(monkeypatch):
    migration = _load_migration_module()
    alter_calls: list[dict[str, object]] = []
    execute_calls: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table_name, column_name, **kwargs: alter_calls.append(
            {
                "table_name": table_name,
                "column_name": column_name,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr(migration.op, "execute", lambda sql: execute_calls.append(str(sql)))

    migration.upgrade()

    assert len(alter_calls) == 1
    alter_call = alter_calls[0]
    assert alter_call["table_name"] == "surrogates"
    assert alter_call["column_name"] == "height_ft"
    assert alter_call["existing_nullable"] is True
    assert alter_call["existing_type"].precision == 3
    assert alter_call["existing_type"].scale == 1
    assert alter_call["type_"].precision == 4
    assert alter_call["type_"].scale == 2
    assert execute_calls == [
        """
        UPDATE surrogates
        SET height_ft = ROUND(ROUND(height_ft * 12)::numeric / 12.0, 2)
        WHERE height_ft IS NOT NULL
        """
    ]


def test_downgrade_rounds_back_to_single_decimal_before_shrinking_column(monkeypatch):
    migration = _load_migration_module()
    alter_calls: list[dict[str, object]] = []
    execute_calls: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table_name, column_name, **kwargs: alter_calls.append(
            {
                "table_name": table_name,
                "column_name": column_name,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr(migration.op, "execute", lambda sql: execute_calls.append(str(sql)))

    migration.downgrade()

    assert execute_calls == [
        """
        UPDATE surrogates
        SET height_ft = ROUND(height_ft::numeric, 1)
        WHERE height_ft IS NOT NULL
        """
    ]
    assert len(alter_calls) == 1
    alter_call = alter_calls[0]
    assert alter_call["table_name"] == "surrogates"
    assert alter_call["column_name"] == "height_ft"
    assert alter_call["existing_nullable"] is True
    assert alter_call["existing_type"].precision == 4
    assert alter_call["existing_type"].scale == 2
    assert alter_call["type_"].precision == 3
    assert alter_call["type_"].scale == 1
