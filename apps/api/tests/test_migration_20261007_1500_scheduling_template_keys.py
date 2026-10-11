"""Scheduling's legacy-named templates gain system keys and readable names, and roll back."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, defer
from sqlalchemy.orm.attributes import set_committed_value

from alembic import command
from app.db.models import EmailTemplate
from app.services import email_service, version_service
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


def _insert_snapshot(connection, org_id, template_id, name):
    payload = {
        "name": name,
        "subject": "Subject",
        "from_email": None,
        "body": "<p>Body</p>",
        "is_active": True,
    }
    _insert_version(
        connection,
        org_id,
        template_id,
        version_service.encrypt_payload(payload),
        version_service.compute_checksum(payload),
    )


def _insert_version(connection, org_id, template_id, payload_encrypted, checksum):
    connection.execute(
        text(
            "INSERT INTO entity_versions (organization_id, entity_type, entity_id, version, "
            "schema_version, payload_encrypted, checksum) "
            "VALUES (:org, 'email_template', :id, 1, 1, :payload, :checksum)"
        ),
        {"org": org_id, "id": template_id, "payload": payload_encrypted, "checksum": checksum},
    )


def _assert_history_matches(connection, template_id, version):
    with Session(bind=connection) as session:
        # Columns added after this revision do not exist yet; they read as their NULL default.
        template = session.get(EmailTemplate, template_id, options=[defer(EmailTemplate.layout)])
        set_committed_value(template, "layout", None)
        assert template.current_version == version
        # Raises when the live content does not match the current version snapshot.
        email_service.ensure_template_current_version_snapshot(session, template)


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
            # A template with version history records the rename as its next version.
            versioned = _insert_template(connection, org, "appointment_rescheduled")
            _insert_snapshot(connection, org, versioned, "appointment_rescheduled")
            # A snapshot that cannot be decrypted keeps its template's name.
            unreadable = _insert_template(connection, org, "appointment_request_received")
            _insert_version(connection, org, unreadable, b"not-a-token", "0" * 64)
            # An org that already uses the readable name keeps both templates' names.
            crowded = _insert_template(connection, crowded_org, "appointment_cancelled")
            own = _insert_template(connection, crowded_org, "Booking Cancelled")

            command.upgrade(config, REVISION)

            assert _row(connection, confirmed) == ("Booking Confirmed", "scheduling_confirmed")
            assert _row(connection, reminder) == ("Booking Reminder", "scheduling_reminder")
            assert _row(connection, seeded) == ("Appointment Confirmed", "appointment_confirmed")
            assert _row(connection, versioned) == ("Booking Rescheduled", "scheduling_rescheduled")
            _assert_history_matches(connection, versioned, 2)
            assert _row(connection, unreadable) == (
                "appointment_request_received",
                "scheduling_request_received",
            )
            assert _row(connection, crowded) == ("appointment_cancelled", "scheduling_cancelled")
            assert _row(connection, own) == ("Booking Cancelled", None)

            command.downgrade(config, PREVIOUS)
            assert _row(connection, confirmed) == ("appointment_confirmed", None)
            assert _row(connection, versioned) == ("appointment_rescheduled", None)
            _assert_history_matches(connection, versioned, 3)
            assert _row(connection, unreadable) == ("appointment_request_received", None)
            assert _row(connection, crowded) == ("appointment_cancelled", None)
            assert _row(connection, seeded) == ("Appointment Confirmed", "appointment_confirmed")

            command.upgrade(config, REVISION)
            # A new template that takes a legacy name blocks the downgrade instead of colliding.
            _insert_template(connection, org, "appointment_confirmed")
            with pytest.raises(RuntimeError, match="rename it before downgrade"):
                command.downgrade(config, PREVIOUS)
        finally:
            transaction.rollback()
