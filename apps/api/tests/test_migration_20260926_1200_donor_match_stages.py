"""Donor stage protection upgrades preserve existing participant references."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic import command
from app.db.migration_steps import donor_pipelines
from tests.test_migration_20260829_donor_module import _alembic_config, _insert_donor_fixture

REVISION = "20260926_1200_donor_match_stages"
PREVIOUS = "20260925_1200_match_status_model"


@pytest.mark.parametrize("kind,handoff", [("egg", "ready_to_match"), ("sperm", "available")])
@pytest.mark.parametrize("stage_state", ["existing", "inactive", "deleted", "missing"])
def test_upgrade_restores_protected_stages_without_moving_donors(
    db_engine, monkeypatch, kind, handoff, stage_state
):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            fixture = _insert_donor_fixture(connection, label=f"stage-{uuid4().hex[:8]}")
            pipeline = fixture["pipeline_id"]
            connection.execute(
                text("UPDATE pipelines SET entity_type=:entity WHERE id=:id"),
                {"entity": f"{kind}_donor", "id": pipeline},
            )
            connection.execute(
                text("UPDATE donors SET donor_type=:kind WHERE id=:id"),
                {"kind": kind, "id": fixture["donor_id"]},
            )
            ids = []
            for index, key in enumerate([handoff, "matched"]):
                stage_id = uuid4()
                ids.append(stage_id)
                connection.execute(
                    text("""INSERT INTO pipeline_stages
                    (id, pipeline_id, stage_key, slug, label, color, "order", stage_type, is_intake_stage, semantics)
                    VALUES (:id, :pipeline, :key, :slug, 'Custom label', '#123456', :order, 'post_approval', FALSE, '{}'::jsonb)"""),
                    {
                        "id": stage_id,
                        "pipeline": pipeline,
                        "key": key,
                        "slug": f"custom-{key}",
                        "order": 10 + index,
                    },
                )
            if stage_state == "missing":
                connection.execute(
                    text("DELETE FROM pipeline_stages WHERE id IN (:a, :b)"),
                    {"a": ids[0], "b": ids[1]},
                )
            else:
                connection.execute(
                    text("UPDATE donors SET stage_id=:stage WHERE id=:id"),
                    {"stage": ids[1], "id": fixture["donor_id"]},
                )
                if stage_state != "existing":
                    deleted = ", deleted_at=now()" if stage_state == "deleted" else ""
                    connection.execute(
                        text(
                            f"UPDATE pipeline_stages SET is_active=FALSE{deleted} WHERE id IN (:a, :b)"
                        ),
                        {"a": ids[0], "b": ids[1]},
                    )
            before_donor = connection.execute(
                text("SELECT stage_id FROM donors WHERE id=:id"), {"id": fixture["donor_id"]}
            ).scalar_one()
            monkeypatch.setattr(
                donor_pipelines, "_stage_semantics", lambda *args: {"future_helper": True}
            )
            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)
            rows = connection.execute(
                text('''SELECT id, stage_key, slug, label, color, "order", is_active, deleted_at, semantics
                FROM pipeline_stages WHERE pipeline_id=:id AND stage_key IN (:a, 'matched') ORDER BY "order"'''),
                {"id": pipeline, "a": handoff},
            ).all()
            assert [row.stage_key for row in rows] == [handoff, "matched"]
            assert all(row.is_active and row.deleted_at is None for row in rows)
            if stage_state == "missing":
                for row in rows:
                    assert row.semantics == {
                        "capabilities": {
                            "counts_as_contacted": True,
                            "eligible_for_matching": row.stage_key == handoff,
                            "locks_match_state": row.stage_key == "matched",
                            "shows_pregnancy_tracking": False,
                            "requires_delivery_details": False,
                            "tracks_interview_outcome": False,
                        },
                        "pause_behavior": "none",
                        "terminal_outcome": "none",
                        "integration_bucket": "converted",
                        "analytics_bucket": row.stage_key,
                        "suggestion_profile_key": None,
                        "requires_reason_on_enter": False,
                    }
            else:
                assert [row.id for row in rows] == ids
                assert [
                    (row.slug, row.label, row.color, row.order, row.semantics) for row in rows
                ] == [
                    (f"custom-{key}", "Custom label", "#123456", 10 + i, {})
                    for i, key in enumerate([handoff, "matched"])
                ]
            assert (
                connection.execute(
                    text("SELECT stage_id FROM donors WHERE id=:id"), {"id": fixture["donor_id"]}
                ).scalar_one()
                == before_donor
            )
        finally:
            transaction.rollback()
