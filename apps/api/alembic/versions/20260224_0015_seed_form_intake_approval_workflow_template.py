"""seed form intake auto-routing workflow platform template

Revision ID: 20260224_0015
Revises: 20260223_2358
Create Date: 2026-02-24 00:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260224_0015"
down_revision: str | Sequence[str] | None = "20260223_2358"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEMPLATE_NAME = "Application Intake: Auto-Match then Create Lead (Approval)"
TEMPLATE_DESCRIPTION = (
    "When a form submission is received, queue approval for auto-match first, "
    "then queue approval for intake lead creation as fallback."
)


def _insert_workflow_template(conn: sa.Connection) -> None:
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM workflow_templates WHERE is_global IS TRUE AND name = :name LIMIT 1"
        ),
        {"name": TEMPLATE_NAME},
    ).first()
    if exists:
        return

    draft_config = {
        "name": TEMPLATE_NAME,
        "description": TEMPLATE_DESCRIPTION,
        "icon": "workflow",
        "category": "intake",
        "trigger_type": "form_submitted",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "auto_match_submission",
                "requires_approval": True,
            },
            {
                "action_type": "create_intake_lead",
                "requires_approval": True,
            },
        ],
    }

    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_templates
            (id, name, description, icon, category, trigger_type, trigger_config, conditions, condition_logic, actions,
             draft_config, is_global, organization_id, status, published_version, is_published_globally, usage_count)
            VALUES
            (gen_random_uuid(), :name, :description, :icon, :category, :trigger_type, CAST(:trigger_config AS jsonb),
             CAST(:conditions AS jsonb), :condition_logic, CAST(:actions AS jsonb), CAST(:draft_config AS jsonb), true,
             NULL, 'draft', 0, false, 0)
            """
        ),
        {
            "name": draft_config["name"],
            "description": draft_config["description"],
            "icon": draft_config["icon"],
            "category": draft_config["category"],
            "trigger_type": draft_config["trigger_type"],
            "trigger_config": json.dumps(draft_config["trigger_config"]),
            "conditions": json.dumps(draft_config["conditions"]),
            "condition_logic": draft_config["condition_logic"],
            "actions": json.dumps(draft_config["actions"]),
            "draft_config": json.dumps(draft_config),
        },
    )


def upgrade() -> None:
    conn = op.get_bind()
    _insert_workflow_template(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM workflow_templates WHERE is_global IS TRUE AND name = :name"
        ),
        {"name": TEMPLATE_NAME},
    )
