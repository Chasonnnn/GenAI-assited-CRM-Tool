"""Form, intake, and pipeline stage timestamps convert to timestamptz as UTC."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command

PREVIOUS = "20261003_2030_email_template_body_design"
REVISION = "20261004_0215_forms_timestamptz"
NAIVE_COLUMNS = text(
    "SELECT table_name, column_name FROM information_schema.columns "
    "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'"
)


def test_upgrade_reads_stored_values_as_utc_and_downgrade_restores_them(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            # A non-UTC session must not shift the stored wall-clock values.
            connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
            command.downgrade(config, PREVIOUS)
            assert ("forms", "updated_at") in {
                tuple(row) for row in connection.execute(NAIVE_COLUMNS)
            }
            org_id, form_id = uuid4(), uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Clock', :slug)"),
                {"id": org_id, "slug": org_id.hex},
            )
            connection.execute(
                text(
                    "INSERT INTO forms (id, organization_id, name, created_at, updated_at) "
                    "VALUES (:id, :org, 'Clock', '2026-10-04 01:56:00', '2026-10-04 02:00:00')"
                ),
                {"id": form_id, "org": org_id},
            )

            command.upgrade(config, REVISION)

            assert connection.execute(NAIVE_COLUMNS).all() == []
            created_at, updated_at = connection.execute(
                text("SELECT created_at, updated_at FROM forms WHERE id = :id"),
                {"id": form_id},
            ).one()
            assert created_at == datetime(2026, 10, 4, 1, 56, tzinfo=UTC)
            assert updated_at == datetime(2026, 10, 4, 2, 0, tzinfo=UTC)

            command.downgrade(config, PREVIOUS)

            assert connection.execute(
                text("SELECT updated_at FROM forms WHERE id = :id"), {"id": form_id}
            ).scalar_one() == datetime(2026, 10, 4, 2, 0)
        finally:
            transaction.rollback()
