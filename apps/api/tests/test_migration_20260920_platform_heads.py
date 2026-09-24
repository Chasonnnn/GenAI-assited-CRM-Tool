"""Both main and reviewed-platform schemas can reach the joined head."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command


@pytest.mark.parametrize(
    "previous", ["20260919_0100_platform_heads", "20260919_0300_ops_cli_login"]
)
def test_platform_join_preserves_existing_organization_and_includes_ops_schema(db_engine, previous):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, previous)
            org_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Existing organization", "slug": f"join-{org_id}"},
            )
            command.upgrade(config, "head")
            command.upgrade(config, "head")

            assert (
                connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1
            )
            assert (
                connection.execute(
                    text("SELECT name FROM organizations WHERE id = :id"), {"id": org_id}
                ).scalar_one()
                == "Existing organization"
            )
            schema = inspect(connection)
            assert {"ops_cli_tokens", "ops_cli_logins"} <= set(schema.get_table_names())
            for table in (
                "platform_email_templates",
                "platform_form_templates",
                "workflow_templates",
            ):
                assert "external_key" in {column["name"] for column in schema.get_columns(table)}
            assert "current_version" in {
                column["name"] for column in schema.get_columns("workflow_templates")
            }
        finally:
            transaction.rollback()
