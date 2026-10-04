"""Notification email preference migration adds an opt-in column that is off for existing rows."""

from uuid import uuid4

from sqlalchemy import inspect, text

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import _alembic_config

REVISION = "20261001_1200_notification_email_preferences"
PREVIOUS = "20260928_1340_zapier_event_effective_at"


def _settings_columns(connection):
    return {
        column["name"]: column
        for column in inspect(connection).get_columns("user_notification_settings")
    }


def test_upgrade_adds_email_toggle_off_for_existing_rows(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            assert "email_workflow_notifications" not in _settings_columns(connection)
            org_id = uuid4()
            user_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Notify Org", "slug": f"notify-{org_id.hex[:8]}"},
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name, token_version) "
                    "VALUES (:id, :email, 'Notify User', 1)"
                ),
                {"id": user_id, "email": f"notify-{user_id.hex[:8]}@test.com"},
            )
            connection.execute(
                text(
                    "INSERT INTO user_notification_settings (user_id, organization_id, "
                    "task_assigned) VALUES (:user_id, :org_id, false)"
                ),
                {"user_id": user_id, "org_id": org_id},
            )

            command.upgrade(config, REVISION)

            column = _settings_columns(connection)["email_workflow_notifications"]
            assert column["nullable"] is False
            email_enabled, task_assigned = connection.execute(
                text(
                    "SELECT email_workflow_notifications, task_assigned "
                    "FROM user_notification_settings WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            ).one()
            assert (email_enabled, task_assigned) == (False, False)

            command.downgrade(config, PREVIOUS)
            assert "email_workflow_notifications" not in _settings_columns(connection)
            command.upgrade(config, REVISION)
        finally:
            transaction.rollback()
