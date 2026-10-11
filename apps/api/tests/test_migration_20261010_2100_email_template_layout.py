"""Upgrade rehearsal for the email template ``layout`` columns."""

import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20261007_2000_messaging_test_phones"
LAYOUT_REVISION = "20261010_2100_email_template_layout"

ORG_ID = uuid.UUID("10000000-0000-0000-0000-000000000041")
TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000041")
LEGACY_BODY = "<p>Hi {{first_name}}</p>"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _column_count(connection, table: str) -> int:
    return connection.scalar(
        text(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'layout'
            """
        ),
        {"table": table},
    )


def test_layout_upgrade_keeps_rows_null_and_rejects_non_objects(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            for table in ("email_templates", "email_template_drafts"):
                assert _column_count(connection, table) == 0

            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": ORG_ID, "name": "Layout rehearsal", "slug": "layout-rehearsal"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO email_templates
                        (id, organization_id, name, subject, body, scope, current_version)
                    VALUES (:id, :org_id, 'Legacy', 'Subject', :body, 'org', 1)
                    """
                ),
                {"id": TEMPLATE_ID, "org_id": ORG_ID, "body": LEGACY_BODY},
            )

            command.upgrade(config, LAYOUT_REVISION)

            for table in ("email_templates", "email_template_drafts"):
                assert _column_count(connection, table) == 1
            row = connection.execute(
                text("SELECT body, layout FROM email_templates WHERE id = :id"),
                {"id": TEMPLATE_ID},
            ).one()
            assert row.body == LEGACY_BODY
            assert row.layout is None

            for value in ("'[]'::jsonb", "'null'::jsonb", "'\"card\"'::jsonb"):
                savepoint = connection.begin_nested()
                with pytest.raises(IntegrityError):
                    connection.execute(
                        text(f"UPDATE email_templates SET layout = {value} WHERE id = :id"),
                        {"id": TEMPLATE_ID},
                    )
                savepoint.rollback()

            connection.execute(
                text(
                    """UPDATE email_templates SET layout = '{"kind": "card"}'::jsonb
                    WHERE id = :id"""
                ),
                {"id": TEMPLATE_ID},
            )

            command.downgrade(config, PREVIOUS_REVISION)
            assert _column_count(connection, "email_templates") == 0
            assert (
                connection.scalar(
                    text("SELECT body FROM email_templates WHERE id = :id"), {"id": TEMPLATE_ID}
                )
                == LEGACY_BODY
            )
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
