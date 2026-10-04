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


# Frozen pre-repair seed fixtures, including the per-organization template binding.
ORIGINAL_SEEDS = {
    "appointment_reminder": {
        "system_key": "appointment_reminder",
        "name": "Appointment Reminder",
        "description": "Sends a reminder email 24 hours before an appointment",
        "icon": "calendar",
        "trigger_type": "scheduled",
        "trigger_config": {"hours_before": 24, "entity_type": "appointment"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_email", "template_key": "appointment_reminder_24h"},
            {"action_type": "send_notification", "title": "Appointment Reminder Sent"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
        "schema_version": 1,
        "scope": "org",
        "owner_user_id": None,
        "is_system_workflow": True,
        "recurrence_stop_on_status": None,
        "rate_limit_per_hour": None,
        "rate_limit_per_entity_per_day": None,
        "reviewed_at": None,
        "reviewed_by_user_id": None,
        "recurrence_interval_hours": None,
        "subject_type": "surrogate",
    },
    "match_notification": {
        "system_key": "match_notification",
        "name": "Match Notification",
        "description": "Notifies case manager and sends intro email when a match is proposed",
        "icon": "heart",
        "trigger_type": "match_proposed",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_notification", "title": "New Match Proposed"},
            {"action_type": "send_email", "template_key": "match_proposal_intro"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
        "schema_version": 1,
        "scope": "org",
        "owner_user_id": None,
        "is_system_workflow": True,
        "recurrence_stop_on_status": None,
        "rate_limit_per_hour": None,
        "rate_limit_per_entity_per_day": None,
        "reviewed_at": None,
        "reviewed_by_user_id": None,
        "recurrence_interval_hours": None,
        "subject_type": "match",
    },
    "weekly_nurture": {
        "system_key": "weekly_nurture",
        "name": "Weekly Nurture Campaign",
        "description": "Sends weekly promotional content to inactive leads",
        "icon": "repeat",
        "trigger_type": "scheduled",
        "trigger_config": {"interval": "weekly", "day_of_week": 1},
        "conditions": [{"field": "status", "operator": "not_in", "value": ["matched", "closed"]}],
        "condition_logic": "AND",
        "actions": [{"action_type": "send_notification", "title": "Weekly nurture email sent"}],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "recurring",
        "recurrence_interval_hours": 168,
        "schema_version": 1,
        "scope": "org",
        "owner_user_id": None,
        "is_system_workflow": True,
        "recurrence_stop_on_status": None,
        "rate_limit_per_hour": None,
        "rate_limit_per_entity_per_day": None,
        "reviewed_at": None,
        "reviewed_by_user_id": None,
        "subject_type": "surrogate",
    },
    "appointment_scheduled_notice": {
        "system_key": "appointment_scheduled_notice",
        "name": "Appointment Scheduled Notice",
        "description": "Notifies the owner when an appointment is scheduled",
        "icon": "calendar",
        "trigger_type": "appointment_scheduled",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "send_notification",
                "title": "Appointment booked",
                "body": "A new appointment was scheduled.",
                "recipients": "owner",
            },
            {"action_type": "send_email", "template_key": "appointment_confirmed"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
        "schema_version": 1,
        "scope": "org",
        "owner_user_id": None,
        "is_system_workflow": True,
        "recurrence_stop_on_status": None,
        "rate_limit_per_hour": None,
        "rate_limit_per_entity_per_day": None,
        "reviewed_at": None,
        "reviewed_by_user_id": None,
        "recurrence_interval_hours": None,
        "subject_type": "appointment",
    },
}


def _insert_workflow(connection, seed, *, with_cold_leads=True):
    org_id, stage_id = _insert_org(connection, with_cold_leads=with_cold_leads)
    config = json.loads(json.dumps(seed))
    for action in config["actions"]:
        template_key = action.pop("template_key", None)
        if template_key:
            template_id = uuid4()
            connection.execute(
                text("""
                INSERT INTO email_templates
                    (id, organization_id, name, subject, body, system_key, is_system_template,
                     is_active, current_version)
                VALUES (:id, :org, :name, 'Subject', 'Body', :name, TRUE, TRUE, 1)
            """),
                {"id": template_id, "org": org_id, "name": template_key},
            )
            action["template_id"] = str(template_id)
    workflow_id = uuid4()
    columns = list(config)
    json_columns = {"trigger_config", "conditions", "actions"}
    values = [f"CAST(:{key} AS jsonb)" if key in json_columns else f":{key}" for key in columns]
    connection.execute(
        text(
            "INSERT INTO automation_workflows (id, organization_id, updated_at, run_count, "
            + ", ".join(columns)
            + ") VALUES (:id, :org, :seeded_at, 0, "
            + ", ".join(values)
            + ")"
        ),
        {
            "id": workflow_id,
            "org": org_id,
            "seeded_at": SEEDED_AT,
            **{
                key: json.dumps(value) if key in json_columns else value
                for key, value in config.items()
            },
        },
    )
    return workflow_id, stage_id


def _row(connection, workflow_id):
    return connection.execute(
        text("SELECT to_jsonb(w) FROM automation_workflows w WHERE id = :id"), {"id": workflow_id}
    ).scalar_one_or_none()


def test_upgrade_repairs_only_original_seed_rows(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            originals = {
                key: _insert_workflow(connection, seed) for key, seed in ORIGINAL_SEEDS.items()
            }
            unchanged = {}
            mutations = {
                "trigger_type": "surrogate_created",
                "trigger_config": {"cron": "0 8 * * 2", "timezone": "UTC"},
                "conditions": [{"field": "is_priority", "operator": "equals", "value": True}],
                "condition_logic": "OR",
                "actions": [
                    {"action_type": "send_notification", "title": "Custom notification"},
                    {"action_type": "send_email", "template_id": str(uuid4())},
                ],
                "description": "Customized description",
                "is_enabled": True,
                "name": "Customized name",
                "icon": "bell",
                "requires_review": False,
                "recurrence_interval_hours": 48,
                "rate_limit_per_hour": 10,
                "is_system_workflow": False,
                "subject_type": "donor",
            }
            for seed in ORIGINAL_SEEDS.values():
                for field, value in mutations.items():
                    workflow_id, _ = _insert_workflow(connection, {**seed, field: value})
                    unchanged[workflow_id] = _row(connection, workflow_id)
            no_stage, _ = _insert_workflow(
                connection, ORIGINAL_SEEDS["weekly_nurture"], with_cold_leads=False
            )
            unchanged[no_stage] = _row(connection, no_stage)
            # A foreign template must not be mistaken for this organization's seeded action.
            foreign_id, _ = _insert_workflow(connection, ORIGINAL_SEEDS["match_notification"])
            foreign_actions = _row(connection, originals["match_notification"][0])["actions"]
            connection.execute(
                text(
                    "UPDATE automation_workflows SET actions = CAST(:actions AS jsonb) WHERE id = :id"
                ),
                {"id": foreign_id, "actions": json.dumps(foreign_actions)},
            )
            unchanged[foreign_id] = _row(connection, foreign_id)

            command.upgrade(config, REVISION)

            for workflow_id, before in unchanged.items():
                assert _row(connection, workflow_id) == before
            nurture_id, cold_stage_id = originals["weekly_nurture"]
            nurture = _row(connection, nurture_id)
            assert nurture["trigger_config"] == {
                "cron": "0 9 * * 1",
                "timezone": "America/Los_Angeles",
            }
            assert nurture["conditions"] == [
                {"field": "stage_id", "operator": "in", "value": [str(cold_stage_id)]}
            ]
            assert nurture["actions"] == [
                {
                    "action_type": "send_notification",
                    "title": "Follow up with a cold lead",
                    "recipients": "owner",
                }
            ]
            assert (
                nurture["description"] == "Reminds owners every Monday to follow up with cold leads"
            )
            assert nurture["is_enabled"] is False
            assert _row(connection, originals["appointment_reminder"][0]) is None
            for key in ("appointment_scheduled_notice", "match_notification"):
                row = _row(connection, originals[key][0])
                assert row["actions"] == [ORIGINAL_SEEDS[key]["actions"][0]]
                assert datetime.fromisoformat(row["updated_at"]) > SEEDED_AT
            assert (
                _row(connection, originals["match_notification"][0])["description"]
                == "Notifies the surrogate's owner when a match is proposed"
            )
        finally:
            transaction.rollback()
