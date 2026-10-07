"""Scheduling's legacy-named templates gain system keys and readable names, and roll back."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import _alembic_config

REVISION = "20261007_1500_scheduling_template_keys"
PREVIOUS = "20261005_0100_under_review_scope"


def _insert_template(connection, org_id, name, scope="org", system_key=None):
    template_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO email_templates (id, organization_id, name, subject, body, scope, "
            "system_key, current_version) "
            "VALUES (:id, :org, :name, 'Subject', '<p>Body</p>', :scope, :system_key, 1)"
        ),
        {
            "id": template_id,
            "org": org_id,
            "name": name,
            "scope": scope,
            "system_key": system_key,
        },
    )
    return template_id


def _row(connection, template_id):
    return connection.execute(
        text("SELECT name, system_key FROM email_templates WHERE id = :id"), {"id": template_id}
    ).one()


def test_scheduling_templates_gain_keys_and_names_and_roll_back(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            org, crowded_org = uuid4(), uuid4()
            for org_id in (org, crowded_org):
                connection.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Org', :slug)"),
                    {"id": org_id, "slug": f"tmpl-{org_id}"},
                )
            confirmed = _insert_template(connection, org, "appointment_confirmed")
            reminder = _insert_template(connection, org, "appointment_reminder")
            # The seeded workflow template keeps its own key and name.
            seeded = _insert_template(
                connection, org, "Appointment Confirmed", system_key="appointment_confirmed"
            )
            # An org that already uses the readable name keeps both templates' names.
            crowded = _insert_template(connection, crowded_org, "appointment_cancelled")
            own = _insert_template(connection, crowded_org, "Booking Cancelled")

            command.upgrade(config, REVISION)

            assert _row(connection, confirmed) == ("Booking Confirmed", "scheduling_confirmed")
            assert _row(connection, reminder) == ("Booking Reminder", "scheduling_reminder")
            assert _row(connection, seeded) == ("Appointment Confirmed", "appointment_confirmed")
            assert _row(connection, crowded) == ("appointment_cancelled", "scheduling_cancelled")
            assert _row(connection, own) == ("Booking Cancelled", None)

            command.downgrade(config, PREVIOUS)
            assert _row(connection, confirmed) == ("appointment_confirmed", None)
            assert _row(connection, crowded) == ("appointment_cancelled", None)
            assert _row(connection, seeded) == ("Appointment Confirmed", "appointment_confirmed")

            command.upgrade(config, REVISION)
            # A new template that takes a legacy name blocks the downgrade instead of colliding.
            _insert_template(connection, org, "appointment_confirmed")
            with pytest.raises(RuntimeError, match="rename it before downgrade"):
                command.downgrade(config, PREVIOUS)
        finally:
            transaction.rollback()
