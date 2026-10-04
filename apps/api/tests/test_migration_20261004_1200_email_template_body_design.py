"""Upgrade rehearsal for the email template ``body_design`` columns (ADR 0006)."""

import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20261004_1000_drop_flat_medical_columns"
DESIGN_REVISION = "20261004_1200_email_template_body_design"

ORG_ID = uuid.UUID("10000000-0000-0000-0000-000000000031")
TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000031")
LEGACY_BODY = '<table role="presentation"><tr><td>Hi {{first_name}} — 保留</td></tr></table>\r\n'

DESIGN_TABLES = (
    ("email_templates", "body_design"),
    ("email_template_drafts", "body_design"),
    ("platform_email_templates", "body_design"),
    ("platform_email_templates", "published_body_design"),
    ("platform_system_email_templates", "body_design"),
)


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _column_count(connection, table: str, column: str) -> int:
    return connection.scalar(
        text(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    )


def test_body_design_upgrade_keeps_bodies_and_rejects_non_objects(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, DESIGN_REVISION)
            command.downgrade(config, PREVIOUS_REVISION)
            for table, column in DESIGN_TABLES:
                assert _column_count(connection, table, column) == 0

            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": ORG_ID, "name": "Body design rehearsal", "slug": "body-design-rehearsal"},
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

            command.upgrade(config, DESIGN_REVISION)

            for table, column in DESIGN_TABLES:
                assert _column_count(connection, table, column) == 1
            row = connection.execute(
                text("SELECT body, body_design FROM email_templates WHERE id = :id"),
                {"id": TEMPLATE_ID},
            ).one()
            assert row.body == LEGACY_BODY
            assert row.body_design is None

            for value in ("'[]'::jsonb", "'null'::jsonb", "'\"doc\"'::jsonb"):
                savepoint = connection.begin_nested()
                with pytest.raises(IntegrityError):
                    connection.execute(
                        text(f"UPDATE email_templates SET body_design = {value} WHERE id = :id"),
                        {"id": TEMPLATE_ID},
                    )
                savepoint.rollback()

            connection.execute(
                text(
                    """
                    UPDATE email_templates SET body_design = '{"type": "doc"}'::jsonb
                    WHERE id = :id
                    """
                ),
                {"id": TEMPLATE_ID},
            )

            command.downgrade(config, PREVIOUS_REVISION)
            assert _column_count(connection, "email_templates", "body_design") == 0
            assert (
                connection.scalar(
                    text("SELECT body FROM email_templates WHERE id = :id"), {"id": TEMPLATE_ID}
                )
                == LEGACY_BODY
            )
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
