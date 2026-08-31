"""Deployment rehearsal for shared Intended Parent and Donor activity."""

from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PRE_ACTIVITY_REVISION = "20260829_0100"
ACTIVITY_REVISION = "20260830_0100"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_entity_activity_migration_backfills_history_and_downgrades(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PRE_ACTIVITY_REVISION)

            org_id = uuid4()
            pipeline_id = uuid4()
            first_stage_id = uuid4()
            second_stage_id = uuid4()
            ip_id = uuid4()
            transition_id = uuid4()
            archive_id = uuid4()

            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Activity Migration", "slug": f"activity-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pipelines (
                        id, organization_id, entity_type, name, is_default,
                        current_version, feature_config
                    ) VALUES (
                        :id, :org_id, 'intended_parent', 'Intended Parents', TRUE, 1, '{}'::jsonb
                    )
                    """
                ),
                {"id": pipeline_id, "org_id": org_id},
            )
            for stage_id, stage_key, label, stage_order in (
                (first_stage_id, "new", "New Lead", 1),
                (second_stage_id, "matched", "Matched", 2),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO pipeline_stages (
                            id, pipeline_id, stage_key, slug, stage_type,
                            label, color, "order", semantics
                        ) VALUES (
                            :id, :pipeline_id, :stage_key, :stage_key, 'intake',
                            :label, '#2563EB', :stage_order, '{}'::jsonb
                        )
                        """
                    ),
                    {
                        "id": stage_id,
                        "pipeline_id": pipeline_id,
                        "stage_key": stage_key,
                        "label": label,
                        "stage_order": stage_order,
                    },
                )
            connection.execute(
                text(
                    """
                    INSERT INTO intended_parents (
                        id, organization_id, intended_parent_number, full_name,
                        email, email_hash, stage_id, status
                    ) VALUES (
                        :id, :org_id, 'I19999', 'Migration Parent',
                        'encrypted-email', :email_hash, :stage_id, 'matched'
                    )
                    """
                ),
                {
                    "id": ip_id,
                    "org_id": org_id,
                    "email_hash": uuid4().hex + uuid4().hex,
                    "stage_id": second_stage_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO intended_parent_status_history (
                        id, intended_parent_id, old_stage_id, new_stage_id,
                        old_status, new_status
                    ) VALUES
                        (:transition_id, :ip_id, :first_stage_id, :second_stage_id, 'new', 'matched'),
                        (:archive_id, :ip_id, :second_stage_id, :second_stage_id, 'matched', 'archived')
                    """
                ),
                {
                    "transition_id": transition_id,
                    "archive_id": archive_id,
                    "ip_id": ip_id,
                    "first_stage_id": first_stage_id,
                    "second_stage_id": second_stage_id,
                },
            )

            command.upgrade(config, ACTIVITY_REVISION)

            history = (
                connection.execute(
                    text(
                        """
                    SELECT id, organization_id, old_label_snapshot, new_label_snapshot
                    FROM intended_parent_status_history
                    WHERE id IN (:transition_id, :archive_id)
                    ORDER BY id
                    """
                    ),
                    {"transition_id": transition_id, "archive_id": archive_id},
                )
                .mappings()
                .all()
            )
            by_id = {row["id"]: row for row in history}
            assert by_id[transition_id]["organization_id"] == org_id
            assert by_id[transition_id]["old_label_snapshot"] == "New Lead"
            assert by_id[transition_id]["new_label_snapshot"] == "Matched"
            assert by_id[archive_id]["organization_id"] == org_id
            assert by_id[archive_id]["old_label_snapshot"] == "Matched"
            assert by_id[archive_id]["new_label_snapshot"] == "Archived"

            schema = inspect(connection)
            assert "entity_activity_logs" in schema.get_table_names()
            assert {index["name"] for index in schema.get_indexes("entity_activity_logs")} >= {
                "idx_entity_activity_ip_time",
                "idx_entity_activity_donor_time",
            }
            assert {
                constraint["name"]
                for constraint in schema.get_check_constraints("entity_activity_logs")
            } >= {"ck_entity_activity_exactly_one_subject"}

            command.downgrade(config, PRE_ACTIVITY_REVISION)
            schema = inspect(connection)
            assert "entity_activity_logs" not in schema.get_table_names()
            history_columns = {
                column["name"] for column in schema.get_columns("intended_parent_status_history")
            }
            assert history_columns.isdisjoint(
                {"organization_id", "old_label_snapshot", "new_label_snapshot"}
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM intended_parent_status_history WHERE id = :id"),
                    {"id": transition_id},
                )
                == 1
            )
        finally:
            transaction.rollback()
