"""seed dual intake workflow templates for full app and pre-screening

Revision ID: 20260224_0105
Revises: 20260224_0015
Create Date: 2026-02-24 01:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260224_0105"
down_revision: str | Sequence[str] | None = "20260224_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_TEMPLATE_NAME = "Application Intake: Auto-Match then Create Lead (Approval)"

FULL_APP_TEMPLATE_NAME = "Full Application: Auto-Match then Create Lead (Approval)"
FULL_APP_FORM_NAME = "Surrogate Full Application Form"
FULL_APP_DESCRIPTION = (
    "Approval-gated intake routing for the Surrogate Full Application Form. "
    "Step 1 auto-matches submission to an existing surrogate; step 2 creates "
    "an intake lead when no deterministic match exists."
)

PRE_SCREEN_TEMPLATE_NAME = "Pre-Screening: Auto-Match then Create Lead (Approval)"
PRE_SCREEN_FORM_NAME = "Surrogate Pre-Screening Questionnaire"
PRE_SCREEN_DESCRIPTION = (
    "Approval-gated intake routing for the Surrogate Pre-Screening Questionnaire. "
    "Step 1 auto-matches submission to an existing surrogate; step 2 creates "
    "an intake lead when no deterministic match exists."
)


def _insert_workflow_template(
    conn: sa.Connection,
    *,
    name: str,
    description: str,
    form_name: str,
) -> None:
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM workflow_templates WHERE is_global IS TRUE AND name = :name LIMIT 1"
        ),
        {"name": name},
    ).first()
    if exists:
        return

    draft_config = {
        "name": name,
        "description": description,
        "icon": "workflow",
        "category": "intake",
        "trigger_type": "form_submitted",
        "trigger_config": {"form_name": form_name},
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
    conn.execute(
        sa.text("DELETE FROM workflow_templates WHERE is_global IS TRUE AND name = :name"),
        {"name": OLD_TEMPLATE_NAME},
    )
    _insert_workflow_template(
        conn,
        name=FULL_APP_TEMPLATE_NAME,
        description=FULL_APP_DESCRIPTION,
        form_name=FULL_APP_FORM_NAME,
    )
    _insert_workflow_template(
        conn,
        name=PRE_SCREEN_TEMPLATE_NAME,
        description=PRE_SCREEN_DESCRIPTION,
        form_name=PRE_SCREEN_FORM_NAME,
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM workflow_templates
            WHERE is_global IS TRUE AND name IN :names
            """
        ).bindparams(sa.bindparam("names", expanding=True)),
        {"names": [FULL_APP_TEMPLATE_NAME, PRE_SCREEN_TEMPLATE_NAME]},
    )
