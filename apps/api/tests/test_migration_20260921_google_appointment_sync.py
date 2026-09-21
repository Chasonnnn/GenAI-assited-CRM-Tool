"""Google appointment links start unbound and enforce valid sync state."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text


def test_google_appointment_sync_migration_round_trip(db):
    path = Path(__file__).parents[1] / "alembic/versions/20260921_0100_google_appointment_sync.py"
    spec = importlib.util.spec_from_file_location("google_appointment_sync_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    connection = db.connection()

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert "google_sync_revision" not in {
            column["name"] for column in inspect(connection).get_columns("appointments")
        }
        migration.upgrade()

    columns = {column["name"] for column in inspect(connection).get_columns("appointments")}
    assert {
        "google_calendar_id",
        "google_integration_id",
        "google_event_etag",
        "google_sync_state",
    } <= columns
    defaults = connection.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'appointments' AND column_name = 'google_sync_revision'"
        )
    ).scalar_one()
    assert defaults == "0"
    constraints = {
        constraint["name"]
        for constraint in inspect(connection).get_check_constraints("appointments")
    }
    assert {
        "ck_appointments_google_sync_revision_nonnegative",
        "ck_appointments_google_sync_state",
    } <= constraints
