"""The seeded system workflow repair changes only rows on the original seed config."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20261001_1200_notification_email_preferences"
REVISION = "20261003_1200_repair_seeded_system_workflows"
SEEDED_AT = datetime(2026, 1, 1, tzinfo=UTC)
OLD_NURTURE_CONFIG = {"interval": "weekly", "day_of_week": 1}
OLD_REMINDER_CONFIG = {"hours_before": 24, "entity_type": "appointment"}


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _insert_org(connection, *, with_cold_leads: bool) -> tuple[UUID, UUID | None]:
    org_id = uuid4()
    connection.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": org_id, "name": "Seed Repair Org", "slug": f"seed-{org_id.hex[:8]}"},
    )
    if not with_cold_leads:
        return org_id, None
    pipeline_id = uuid4()
    stage_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO pipelines (id, organization_id, entity_type, name, is_default, "
            "current_version) VALUES (:id, :org_id, 'surrogate', 'Default', TRUE, 1)"
        ),
        {"id": pipeline_id, "org_id": org_id},
    )
    connection.execute(
        text(
            "INSERT INTO pipeline_stages (id, pipeline_id, stage_key, slug, stage_type, label, "
            "color, \"order\", is_active) VALUES (:id, :pipeline_id, 'cold_leads', "
            "'cold_leads', 'terminal', 'Cold Leads', '#64748B', 1, TRUE)"
        ),
        {"id": stage_id, "pipeline_id": pipeline_id},
    )
    return org_id, stage_id


def _insert_workflow(
    connection,
    *,
    org_id: UUID,
    system_key: str,
    trigger_type: str,
    trigger_config: dict,
    actions: list,
    description: str | None = None,
    enabled: bool = False,
) -> UUID:
    workflow_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO automation_workflows (
                id, organization_id, name, description, icon, schema_version, subject_type,
                trigger_type, trigger_config, conditions, condition_logic, actions,
                is_enabled, is_system_workflow, system_key, run_count, updated_at
            ) VALUES (
                :id, :org_id, :name, :description, 'workflow', 1, :subject_type,
                :trigger_type, CAST(:trigger_config AS jsonb), '[]'::jsonb, 'AND',
                CAST(:actions AS jsonb), :enabled, TRUE, :system_key, 0, :seeded_at
            )
            """
        ),
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": f"{system_key} {workflow_id.hex[:6]}",
            "description": description,
            "subject_type": {"appointment_scheduled": "appointment", "match_proposed": "match"}.get(
                trigger_type, "surrogate"
            ),
            "trigger_type": trigger_type,
            "trigger_config": json.dumps(trigger_config),
            "actions": json.dumps(actions),
            "enabled": enabled,
            "system_key": system_key,
            "seeded_at": SEEDED_AT,
        },
    )
    return workflow_id


def test_upgrade_repairs_only_original_seed_rows(db_engine) -> None:
    notify = {"action_type": "send_notification", "title": "Notice", "recipients": "owner"}
    send_email = {"action_type": "send_email", "template_id": str(uuid4())}
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            org_id, cold_stage_id = _insert_org(connection, with_cold_leads=True)
            stageless_org_id, _ = _insert_org(connection, with_cold_leads=False)
            ids = {
                "nurture": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="weekly_nurture",
                    trigger_type="scheduled",
                    trigger_config=OLD_NURTURE_CONFIG,
                    actions=[notify],
                    description="Sends weekly promotional content to inactive leads",
                    enabled=True,
                ),
                "nurture_edited": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="weekly_nurture",
                    trigger_type="scheduled",
                    trigger_config={"cron": "0 8 * * 2", "timezone": "UTC"},
                    actions=[notify],
                ),
                "nurture_no_stage": _insert_workflow(
                    connection,
                    org_id=stageless_org_id,
                    system_key="weekly_nurture",
                    trigger_type="scheduled",
                    trigger_config=OLD_NURTURE_CONFIG,
                    actions=[notify],
                ),
                "reminder": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="appointment_reminder",
                    trigger_type="scheduled",
                    trigger_config=OLD_REMINDER_CONFIG,
                    actions=[notify],
                ),
                "reminder_edited": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="appointment_reminder",
                    trigger_type="scheduled",
                    trigger_config={"cron": "0 9 * * *", "timezone": "UTC"},
                    actions=[notify],
                ),
                "notice": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="appointment_scheduled_notice",
                    trigger_type="appointment_scheduled",
                    trigger_config={},
                    actions=[notify, send_email],
                ),
                "match": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="match_notification",
                    trigger_type="match_proposed",
                    trigger_config={},
                    actions=[send_email, notify],
                    description=(
                        "Notifies case manager and sends intro email when a match is proposed"
                    ),
                ),
                "other_email": _insert_workflow(
                    connection,
                    org_id=org_id,
                    system_key="approved_booking_invite",
                    trigger_type="status_changed",
                    trigger_config={},
                    actions=[send_email, notify],
                ),
            }

            command.upgrade(config, REVISION)

            rows = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, description, trigger_config, conditions, actions, "
                        "is_enabled, updated_at FROM automation_workflows WHERE id = ANY(:ids)"
                    ),
                    {"ids": list(ids.values())},
                )
            }

            nurture = rows[ids["nurture"]]
            assert nurture.trigger_config == {
                "cron": "0 9 * * 1",
                "timezone": "America/Los_Angeles",
            }
            assert nurture.conditions == [
                {"field": "stage_id", "operator": "in", "value": [str(cold_stage_id)]}
            ]
            assert nurture.actions == [
                {
                    "action_type": "send_notification",
                    "title": "Follow up with a cold lead",
                    "recipients": "owner",
                }
            ]
            assert nurture.description == "Reminds owners every Monday to follow up with cold leads"
            assert nurture.is_enabled is False
            assert nurture.updated_at > SEEDED_AT

            for key in ("nurture_edited", "nurture_no_stage"):
                assert rows[ids[key]].updated_at == SEEDED_AT, key

            assert ids["reminder"] not in rows
            assert ids["reminder_edited"] in rows

            assert rows[ids["notice"]].actions == [notify]
            match = rows[ids["match"]]
            assert match.actions == [notify]
            assert match.description == "Notifies the surrogate's owner when a match is proposed"
            assert rows[ids["other_email"]].actions == [send_email, notify]
            assert rows[ids["other_email"]].updated_at == SEEDED_AT
        finally:
            transaction.rollback()
