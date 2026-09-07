"""An ordinary release cannot accidentally cross the match expansion boundary."""

from unittest.mock import Mock

import pytest
from sqlalchemy import inspect, text

from app.db import release_migration


@pytest.mark.parametrize(
    "revision", ["20260830_0100", "20260905_1400_match_cases", "20260905_1500_match_work"]
)
def test_pending_expansion_requires_explicit_cutover(revision, monkeypatch):
    monkeypatch.setattr(release_migration, "_current_heads", lambda _: (revision,))
    with pytest.raises(RuntimeError, match="explicit match expansion rollout"):
        release_migration.preflight(Mock(), allow_match_expansion=False)


def test_expanded_schema_allows_normal_release(monkeypatch):
    monkeypatch.setattr(
        release_migration, "_current_heads", lambda _: ("20260905_1600_record_integrations",)
    )
    assert release_migration.preflight(Mock(), allow_match_expansion=False) is False


def test_expansion_conflicts_are_reported_before_migration(monkeypatch):
    monkeypatch.setattr(release_migration, "_current_heads", lambda _: ("20260830_0100",))
    connection = Mock()
    connection.execute.return_value.scalar_one.return_value = 2
    with pytest.raises(RuntimeError, match="2 conflicting surrogate commitments"):
        release_migration.preflight(connection, allow_match_expansion=True)


def test_unknown_or_older_baseline_requires_review(monkeypatch):
    monkeypatch.setattr(release_migration, "_current_heads", lambda _: ("20260829_0100",))
    with pytest.raises(RuntimeError, match="baseline"):
        release_migration.preflight(Mock(), allow_match_expansion=True)


def test_release_migration_cannot_overlap_another_migration(db_engine):
    with db_engine.connect() as connection:
        connection.execute(
            text("SELECT pg_advisory_lock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
        )
        try:
            with pytest.raises(RuntimeError, match="Another migration is running"):
                release_migration.run_migration(
                    db_engine, check_only=False, allow_match_expansion=False
                )
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
            )


def test_failed_preflight_releases_migration_lock(db_engine, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Preflight failed")

    monkeypatch.setattr(release_migration, "preflight", fail)
    with pytest.raises(RuntimeError, match="Preflight failed"):
        release_migration.run_migration(db_engine, check_only=False, allow_match_expansion=False)
    with db_engine.connect() as connection:
        assert connection.execute(
            text("SELECT pg_try_advisory_lock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
        ).scalar_one()
        connection.execute(
            text("SELECT pg_advisory_unlock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
        )


def test_failed_release_ddl_rolls_back_before_releasing_lock(db_engine, monkeypatch):
    def fail_after_ddl(config, target):
        assert target == "head"
        config.attributes["connection"].execute(
            text("CREATE TABLE release_rollback_fixture (id integer)")
        )
        raise RuntimeError("Simulated DDL failure")

    monkeypatch.setattr(release_migration.command, "upgrade", fail_after_ddl)
    with pytest.raises(RuntimeError, match="Simulated DDL failure"):
        release_migration.run_migration(db_engine, check_only=False, allow_match_expansion=False)
    with db_engine.connect() as connection:
        assert not inspect(connection).has_table("release_rollback_fixture")
        assert connection.execute(
            text("SELECT pg_try_advisory_lock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
        ).scalar_one()
        connection.execute(
            text("SELECT pg_advisory_unlock(:id)"), {"id": release_migration.MIGRATION_LOCK_ID}
        )
