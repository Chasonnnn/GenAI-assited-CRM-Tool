"""Upgrade and downgrade of the per-appointment-type client message migration."""

from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20261003_1200_repair_seeded_system_workflows"
REVISION = "20261003_1300_appointment_type_client_messages"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_upgrade_turns_zero_hour_reminders_into_a_disabled_reminder(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            org_id = uuid4()
            user_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Org', :slug)"),
                {"id": org_id, "slug": f"org-{org_id.hex[:8]}"},
            )
            connection.execute(
                text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Host')"),
                {"id": user_id, "email": f"host-{user_id.hex[:8]}@test.com"},
            )
            type_ids = {}
            for slug, hours in (("off", 0), ("on", 12)):
                type_ids[slug] = uuid4()
                connection.execute(
                    text(
                        "INSERT INTO appointment_types (id, organization_id, user_id, name, "
                        "slug, duration_minutes, buffer_before_minutes, buffer_after_minutes, "
                        "reminder_hours_before) VALUES (:id, :org_id, :user_id, :name, :slug, "
                        "30, 0, 5, :hours)"
                    ),
                    {
                        "id": type_ids[slug],
                        "org_id": org_id,
                        "user_id": user_id,
                        "name": slug,
                        "slug": slug,
                        "hours": hours,
                    },
                )

            command.upgrade(config, REVISION)

            rows = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, reminder_hours_before, client_messages FROM appointment_types "
                        "WHERE id = ANY(:ids)"
                    ),
                    {"ids": list(type_ids.values())},
                )
            }
            assert rows[type_ids["off"]].reminder_hours_before == 24
            assert rows[type_ids["off"]].client_messages == {
                "reminder": {"enabled": False, "template_id": None}
            }
            assert rows[type_ids["on"]].reminder_hours_before == 12
            assert rows[type_ids["on"]].client_messages == {}

            command.downgrade(config, PREVIOUS_REVISION)
            assert (
                connection.execute(
                    text("SELECT reminder_hours_before FROM appointment_types WHERE id = :id"),
                    {"id": type_ids["off"]},
                ).scalar_one()
                == 0
            )
        finally:
            transaction.rollback()
