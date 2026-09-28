"""Store canonical donor sources in workflow Update Field actions.

The builder saved the donor source for Update Field actions as free text. Donor
updates now accept only canonical sources, so a stored free-text value fails on
every run. Workflow and template actions (including template drafts) get the
same mapping as the donors backfill: canonical values in any case, website
aliases to ``website``, and other values to ``other``. Only donor records accept
a source update, so every stored source action belongs to a donor workflow.
Downgrade is a no-op: the original spellings are not kept.

Revision ID: 20260928_1320_donor_workflow_source_canonical
Revises: 20260928_1310_donor_source_canonical
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "20260928_1320_donor_workflow_source_canonical"
down_revision = "20260928_1310_donor_source_canonical"
branch_labels = None
depends_on = None

# Frozen copies of SurrogateSource values and app.schemas.donor website aliases,
# so later vocabulary edits cannot change this revision.
CANONICAL_SOURCES = frozenset(
    {
        "manual",
        "meta",
        "tiktok",
        "google",
        "website",
        "referral",
        "import",
        "agency",
        "other",
    }
)
WEBSITE_ALIASES = frozenset(
    {
        "shared_intake",
        "form_embed",
        "website_intake",
        "website_embed",
        "manual_review_resolution",
        "manual_retry_resolution",
    }
)
SOURCE_ACTION_FILTER = """@> '[{"action_type": "update_field", "field": "source"}]'::jsonb"""


def _canonical_source(value: str) -> str:
    key = value.strip().lower()
    if key in CANONICAL_SOURCES:
        return key
    if key in WEBSITE_ALIASES:
        return "website"
    return "other"


def _canonicalize_actions(actions: object) -> list | None:
    """Return the actions with canonical source values, or None when nothing changes."""
    if not isinstance(actions, list):
        return None
    changed = False
    result = []
    for action in actions:
        if (
            isinstance(action, dict)
            and action.get("action_type") == "update_field"
            and action.get("field") == "source"
            and isinstance(action.get("value"), str)
            and action["value"].strip()
        ):
            source = _canonical_source(action["value"])
            if source != action["value"]:
                action = {**action, "value": source}
                changed = True
        result.append(action)
    return result if changed else None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()

    workflows = connection.execute(
        sa.text(
            f"SELECT id, actions FROM automation_workflows WHERE actions {SOURCE_ACTION_FILTER}"
        )
    ).all()
    for workflow_id, actions in workflows:
        canonical = _canonicalize_actions(actions)
        if canonical is not None:
            connection.execute(
                sa.text(
                    "UPDATE automation_workflows "
                    "SET actions = CAST(:actions AS jsonb), updated_at = now() WHERE id = :id"
                ),
                {"id": workflow_id, "actions": json.dumps(canonical)},
            )

    templates = connection.execute(
        sa.text(
            "SELECT id, actions, draft_config FROM workflow_templates "
            f"WHERE actions {SOURCE_ACTION_FILTER} "
            f"OR draft_config->'actions' {SOURCE_ACTION_FILTER}"
        )
    ).all()
    for template_id, actions, draft_config in templates:
        canonical = _canonicalize_actions(actions)
        if canonical is not None:
            connection.execute(
                sa.text(
                    "UPDATE workflow_templates SET actions = CAST(:actions AS jsonb) WHERE id = :id"
                ),
                {"id": template_id, "actions": json.dumps(canonical)},
            )
        draft_actions = (
            _canonicalize_actions(draft_config.get("actions"))
            if isinstance(draft_config, dict)
            else None
        )
        if draft_actions is not None:
            connection.execute(
                sa.text(
                    "UPDATE workflow_templates "
                    "SET draft_config = jsonb_set(draft_config, '{actions}', "
                    "CAST(:actions AS jsonb)) WHERE id = :id"
                ),
                {"id": template_id, "actions": json.dumps(draft_actions)},
            )


def downgrade() -> None:
    pass
