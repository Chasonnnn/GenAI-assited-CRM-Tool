"""Zapier event effective time migration adds a nullable column and keeps existing rows."""

from uuid import uuid4

from sqlalchemy import inspect, text

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import (
    SEEDED_AT,
    _alembic_config,
)

REVISION = "20260928_1340_zapier_event_effective_at"
PREVIOUS = "20260928_1330_donor_email_approval_optional"


def _event_columns(connection):
    return {
        column["name"]: column
        for column in inspect(connection).get_columns("zapier_outbound_events")
    }


def test_upgrade_adds_nullable_effective_at_and_keeps_existing_events(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            assert "effective_at" not in _event_columns(connection)
            org_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Zapier Org", "slug": f"zapier-{org_id.hex[:8]}"},
            )
            event_id = uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO zapier_outbound_events (
                        id, organization_id, source, status, reason, stage_key,
                        created_at, updated_at
                    ) VALUES (
                        :id, :org_id, 'automatic', 'skipped', 'outbound_disabled',
                        'pre_qualified', :seeded_at, :seeded_at
                    )
                    """
                ),
                {"id": event_id, "org_id": org_id, "seeded_at": SEEDED_AT},
            )

            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)

            column = _event_columns(connection)["effective_at"]
            assert column["nullable"] is True
            assert getattr(column["type"], "timezone", False) is True
            status, reason, effective_at, updated_at = connection.execute(
                text(
                    "SELECT status, reason, effective_at, updated_at "
                    "FROM zapier_outbound_events WHERE id = :id"
                ),
                {"id": event_id},
            ).one()
            assert (status, reason, effective_at) == ("skipped", "outbound_disabled", None)
            assert updated_at == SEEDED_AT

            command.downgrade(config, PREVIOUS)
            assert "effective_at" not in _event_columns(connection)
            command.upgrade(config, REVISION)
        finally:
            transaction.rollback()
