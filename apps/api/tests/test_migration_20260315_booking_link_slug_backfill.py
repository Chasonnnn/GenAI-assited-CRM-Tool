from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260315_1800_booking_link_user_slugs.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260315_1800", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_slug_base_preserves_word_boundaries():
    migration = _load_migration_module()

    assert migration._build_slug_base("Test Developer") == "test-developer"
    assert migration._build_slug_base("Test Case Manager") == "test-case-manager"
