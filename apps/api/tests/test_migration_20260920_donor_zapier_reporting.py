"""Donor Zapier reporting migration keeps delivery disabled by default."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text


def test_donor_zapier_reporting_migration_round_trip(db, test_org):
    path = Path(__file__).parents[1] / "alembic/versions/20260920_0200_donor_zapier_reporting.py"
    spec = importlib.util.spec_from_file_location("donor_zapier_reporting_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    connection = db.connection()
    connection.execute(
        text("INSERT INTO zapier_webhook_settings (organization_id) VALUES (:organization_id)"),
        {"organization_id": test_org.id},
    )

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        settings_columns = {
            column["name"] for column in inspect(connection).get_columns("zapier_webhook_settings")
        }
        event_columns = {
            column["name"] for column in inspect(connection).get_columns("zapier_outbound_events")
        }
        assert "donor_outbound_enabled" not in settings_columns
        assert "donor_status_history_id" not in event_columns
        migration.upgrade()

    assert (
        connection.execute(
            text(
                "SELECT donor_outbound_enabled FROM zapier_webhook_settings "
                "WHERE organization_id = :organization_id"
            ),
            {"organization_id": test_org.id},
        ).scalar_one()
        is False
    )
    indexes = {index["name"] for index in inspect(connection).get_indexes("zapier_outbound_events")}
    assert "uq_zapier_outbound_events_donor_history" in indexes
