from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260701_1025_add_intelligent_summary_indexes.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260701_1025", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _MigrationContext:
    def __init__(self) -> None:
        self.autocommit_entries = 0

    @contextmanager
    def autocommit_block(self):
        self.autocommit_entries += 1
        yield


def test_upgrade_creates_all_indexes_concurrently_and_idempotently(monkeypatch) -> None:
    migration = _load_migration_module()
    context = _MigrationContext()
    create_calls: list[dict[str, object]] = []

    monkeypatch.setattr(migration.op, "get_context", lambda: context)
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table_name, columns, **kwargs: create_calls.append(
            {
                "name": name,
                "table_name": table_name,
                "columns": columns,
                **kwargs,
            }
        ),
    )

    migration.upgrade()

    assert context.autocommit_entries == 1
    assert [call["name"] for call in create_calls] == [
        "idx_surrogate_activity_org_surrogate_time",
        "idx_surrogate_activity_org_type_surrogate_time",
        "idx_appointments_org_status_surrogate",
    ]
    assert all(call["postgresql_concurrently"] is True for call in create_calls)
    assert all(call["if_not_exists"] is True for call in create_calls)


def test_downgrade_drops_all_indexes_concurrently_and_idempotently(monkeypatch) -> None:
    migration = _load_migration_module()
    context = _MigrationContext()
    drop_calls: list[dict[str, object]] = []

    monkeypatch.setattr(migration.op, "get_context", lambda: context)
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, **kwargs: drop_calls.append({"name": name, **kwargs}),
    )

    migration.downgrade()

    assert context.autocommit_entries == 1
    assert [call["name"] for call in drop_calls] == [
        "idx_appointments_org_status_surrogate",
        "idx_surrogate_activity_org_type_surrogate_time",
        "idx_surrogate_activity_org_surrogate_time",
    ]
    assert all(call["postgresql_concurrently"] is True for call in drop_calls)
    assert all(call["if_exists"] is True for call in drop_calls)
