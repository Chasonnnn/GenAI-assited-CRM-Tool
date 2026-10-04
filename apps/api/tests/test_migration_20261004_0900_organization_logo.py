"""Square branding is nullable and leaves existing signature logos unchanged."""

from uuid import uuid4

from sqlalchemy import inspect, text

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import _alembic_config

REVISION = "20261004_0900_organization_logo"
PREVIOUS = "20261003_1800_timezone_aware_form_timestamps"


def test_organization_logo_upgrade_and_downgrade(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            org_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, signature_logo_url) VALUES (:id, 'Logo Org', :slug, 'logos/signature.png')"
                ),
                {"id": org_id, "slug": f"logo-{org_id.hex}"},
            )
            command.upgrade(config, REVISION)
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("organizations")
            }
            assert columns["logo_url"]["nullable"] is True
            assert columns["logo_url"]["type"].length == 500
            assert connection.execute(
                text("SELECT logo_url, signature_logo_url FROM organizations WHERE id = :id"),
                {"id": org_id},
            ).one() == (None, "logos/signature.png")
            connection.execute(
                text("UPDATE organizations SET logo_url = :url WHERE id = :id"),
                {"id": org_id, "url": "x" * 500},
            )
            command.downgrade(config, PREVIOUS)
            assert "logo_url" not in {
                column["name"] for column in inspect(connection).get_columns("organizations")
            }
            assert (
                connection.execute(
                    text("SELECT signature_logo_url FROM organizations WHERE id = :id"),
                    {"id": org_id},
                ).scalar_one()
                == "logos/signature.png"
            )
            command.upgrade(config, REVISION)
        finally:
            transaction.rollback()
