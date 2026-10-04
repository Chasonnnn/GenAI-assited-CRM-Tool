"""Repair system workflows seeded with configurations that could never run.

- weekly_nurture rows still on the complete original configuration get the Monday 9:00 cron, the Cold Leads stage condition, and an
  owner notification. Rows stay disabled. Orgs without a cold_leads stage are skipped.
- appointment_reminder rows still on the original config are deleted: no appointment-relative trigger existed for
  them and scheduling sends its own reminder.
- appointment_scheduled_notice and match_notification lose their send_email actions.
  These actions failed on every run. Scheduling owns appointment confirmations, and
  match workflows cannot send email.

Downgrade is a no-op: the previous configurations were invalid and never executed.

Revision ID: 20261003_1200_repair_seeded_system_workflows
Revises: 20261001_1200_notification_email_preferences
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "20261003_1200_repair_seeded_system_workflows"
down_revision = "20261001_1200_notification_email_preferences"
branch_labels = None
depends_on = None

# Literal historical configuration; edits to any of these fields opt out of repair.
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


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()
    rows = (
        connection.execute(
            sa.text("""
        SELECT * FROM automation_workflows
        WHERE system_key IN ('weekly_nurture', 'appointment_reminder',
                             'appointment_scheduled_notice', 'match_notification')
        FOR UPDATE
    """)
        )
        .mappings()
        .all()
    )
    templates = {
        (row.organization_id, row.system_key): str(row.id)
        for row in connection.execute(
            sa.text("""
            SELECT id, organization_id, system_key FROM email_templates
            WHERE system_key IN ('appointment_reminder_24h', 'appointment_confirmed', 'match_proposal_intro')
        """)
        )
    }
    for row in rows:
        expected = json.loads(json.dumps(ORIGINAL_SEEDS[row["system_key"]]))
        for action in expected["actions"]:
            template_key = action.pop("template_key", None)
            if template_key:
                template_id = templates.get((row["organization_id"], template_key))
                if template_id:
                    action["template_id"] = template_id
        if any(row[key] != value for key, value in expected.items()):
            continue
        params = {"id": row["id"], "org": row["organization_id"]}
        if row["system_key"] == "weekly_nurture":
            connection.execute(
                sa.text("""
                UPDATE automation_workflows AS w
                SET trigger_config = '{"cron":"0 9 * * 1","timezone":"America/Los_Angeles"}'::jsonb,
                    conditions = jsonb_build_array(jsonb_build_object(
                        'field', 'stage_id', 'operator', 'in',
                        'value', jsonb_build_array(CAST(s.id AS text))
                    )),
                    actions = '[{"action_type":"send_notification","title":"Follow up with a cold lead","recipients":"owner"}]'::jsonb,
                    description = 'Reminds owners every Monday to follow up with cold leads',
                    is_enabled = FALSE, updated_at = now()
                FROM pipelines AS p
                JOIN pipeline_stages AS s ON s.pipeline_id = p.id
                WHERE w.id = :id AND w.organization_id = :org
                  AND p.organization_id = w.organization_id
                  AND p.entity_type = 'surrogate' AND p.is_default = TRUE
                  AND s.stage_key = 'cold_leads' AND s.is_active = TRUE
            """),
                params,
            )
        elif row["system_key"] == "appointment_reminder":
            connection.execute(
                sa.text(
                    "DELETE FROM automation_workflows WHERE id = :id AND organization_id = :org"
                ),
                params,
            )
        else:
            actions = [action for action in row["actions"] if action["action_type"] != "send_email"]
            description = (
                "Notifies the surrogate's owner when a match is proposed"
                if row["system_key"] == "match_notification"
                else row["description"]
            )
            connection.execute(
                sa.text("""
                UPDATE automation_workflows
                SET actions = CAST(:actions AS jsonb), description = :description, updated_at = now()
                WHERE id = :id AND organization_id = :org
            """),
                {**params, "actions": json.dumps(actions), "description": description},
            )


def downgrade() -> None:
    pass
