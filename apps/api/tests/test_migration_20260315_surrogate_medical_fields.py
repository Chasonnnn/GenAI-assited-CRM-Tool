from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260315_1200_add_fax_pcp_lab_clinic_fields.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260315_1200", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_only_drops_existing_columns(monkeypatch):
    migration = _load_migration_module()
    dropped_columns: list[str] = []
    existing_columns = {"lab_clinic_email", "pcp_name", "insurance_fax"}

    monkeypatch.setattr(
        migration,
        "_column_exists",
        lambda _table_name, column_name: column_name in existing_columns,
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda _table_name, column_name: dropped_columns.append(column_name),
    )

    migration.downgrade()

    assert dropped_columns == ["lab_clinic_email", "pcp_name", "insurance_fax"]
