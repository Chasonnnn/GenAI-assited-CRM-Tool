"""Repair system workflows seeded with configurations that could never run.

- weekly_nurture rows still on the original schedule get the Monday 9:00 cron, the Cold Leads stage condition, and an
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

OLD_NURTURE_TRIGGER_CONFIG = {"interval": "weekly", "day_of_week": 1}
OLD_NURTURE_DESCRIPTION = "Sends weekly promotional content to inactive leads"
NURTURE_TRIGGER_CONFIG = {"cron": "0 9 * * 1", "timezone": "America/Los_Angeles"}
NURTURE_DESCRIPTION = "Reminds owners every Monday to follow up with cold leads"
NURTURE_ACTIONS = [
    {
        "action_type": "send_notification",
        "title": "Follow up with a cold lead",
        "recipients": "owner",
    }
]
OLD_REMINDER_TRIGGER_CONFIG = {"hours_before": 24, "entity_type": "appointment"}
OLD_MATCH_DESCRIPTION = "Notifies case manager and sends intro email when a match is proposed"
MATCH_DESCRIPTION = "Notifies the surrogate's owner when a match is proposed"


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute(
        sa.text(
            """
            UPDATE automation_workflows AS w
            SET trigger_config = CAST(:trigger_config AS jsonb),
                conditions = jsonb_build_array(jsonb_build_object(
                    'field', 'stage_id', 'operator', 'in',
                    'value', jsonb_build_array(CAST(s.id AS text))
                )),
                actions = CAST(:actions AS jsonb),
                description = CASE WHEN w.description = :old_description
                    THEN :description ELSE w.description END,
                is_enabled = FALSE,
                updated_at = now()
            FROM pipelines AS p
            JOIN pipeline_stages AS s ON s.pipeline_id = p.id
            WHERE w.system_key = 'weekly_nurture'
              AND w.trigger_config = CAST(:old_trigger_config AS jsonb)
              AND p.organization_id = w.organization_id
              AND p.entity_type = 'surrogate'
              AND p.is_default = TRUE
              AND s.stage_key = 'cold_leads'
              AND s.is_active = TRUE
            """
        ).bindparams(
            trigger_config=json.dumps(NURTURE_TRIGGER_CONFIG),
            actions=json.dumps(NURTURE_ACTIONS),
            old_description=OLD_NURTURE_DESCRIPTION,
            description=NURTURE_DESCRIPTION,
            old_trigger_config=json.dumps(OLD_NURTURE_TRIGGER_CONFIG),
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM automation_workflows "
            "WHERE system_key = 'appointment_reminder' "
            "AND trigger_config = CAST(:old_trigger_config AS jsonb)"
        ).bindparams(old_trigger_config=json.dumps(OLD_REMINDER_TRIGGER_CONFIG))
    )
    op.execute(
        sa.text(
            """
            UPDATE automation_workflows
            SET actions = (
                    SELECT COALESCE(jsonb_agg(action ORDER BY position), '[]'::jsonb)
                    FROM jsonb_array_elements(actions) WITH ORDINALITY AS a(action, position)
                    WHERE action->>'action_type' IS DISTINCT FROM 'send_email'
                ),
                description = CASE WHEN description = :old_match_description
                    THEN :match_description ELSE description END,
                updated_at = now()
            WHERE system_key IN ('appointment_scheduled_notice', 'match_notification')
              AND jsonb_typeof(actions) = 'array'
              AND jsonb_path_exists(actions, '$[*] ? (@.action_type == "send_email")')
            """
        ).bindparams(
            old_match_description=OLD_MATCH_DESCRIPTION,
            match_description=MATCH_DESCRIPTION,
        )
    )


def downgrade() -> None:
    pass
