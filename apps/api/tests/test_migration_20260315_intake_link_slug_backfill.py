from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260315_1900_intake_link_readable_slugs.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260315_1900", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_slug_base_prefers_event_name_then_campaign_then_form_name():
    migration = _load_migration_module()

    assert (
        migration._build_slug_base(
            event_name="Austin Expo",
            campaign_name="Spring Event",
            form_name="Shared Intake Form",
        )
        == "austin-expo"
    )
    assert (
        migration._build_slug_base(
            event_name=None,
            campaign_name="Spring Event",
            form_name="Shared Intake Form",
        )
        == "spring-event"
    )
    assert (
        migration._build_slug_base(
            event_name=None,
            campaign_name=None,
            form_name="PR334 QA Form 20260315 211811",
        )
        == "pr334-qa-form-20260315-211811"
    )


def test_format_slug_candidate_adds_collision_suffix():
    migration = _load_migration_module()

    assert migration._format_slug_candidate("austin-expo", 1) == "austin-expo"
    assert migration._format_slug_candidate("austin-expo", 2) == "austin-expo-2"
