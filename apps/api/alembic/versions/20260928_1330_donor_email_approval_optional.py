"""Make approval optional again on stored donor workflow emails.

Save-time validation forced ``requires_approval: true`` on every send_email action
in a donor-context workflow or template. Approval is now optional, but the stored
forced values still hold donor emails for review. Every stored donor-context
send_email approval was forced by validation, so all of them are set to
``requires_approval: false``. Surrogate-context actions, other action types,
executions, and pending approval tasks are unchanged.

Donor context uses frozen copies of the resolvers at this revision:
workflows follow ``resolve_effective_workflow_subject_type`` (the trigger form is
looked up in the workflow organization), templates and template drafts follow
``resolve_effective_template_subject_type`` (an organization template binds its
form, then the unbound resolver applies).

An organization workflow whose stored v2 ``execution_authority`` digest matched
the configuration before this change gets the recomputed digest, so it stays
authorized. A missing or already mismatched grant is left alone.

Downgrade is a no-op: the forced values carried no user choice.

Revision ID: 20260928_1330_donor_email_approval_optional
Revises: 20260928_1320_donor_workflow_source_canonical
"""

import json
from hashlib import sha256
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "20260928_1330_donor_email_approval_optional"
down_revision = "20260928_1320_donor_workflow_source_canonical"
branch_labels = None
depends_on = None

# Frozen copies of workflow_service and template_service constants.
DONOR_SUBJECT_TYPES = frozenset({"egg_donor", "sperm_donor"})
DONOR_PERMISSION_CONTEXT = "donor"
INTAKE_CONTEXT_KEYS = {"form_submitted": "lead_kind", "intake_lead_created": "lead_type"}
LEGACY_TRIGGER_SUBJECT_TYPES = {
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_declined": "match",
    "match_cancelled": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
}
DONOR_ONLY_TRIGGER_TYPES = frozenset(
    {"donor_created", "donor_stage_changed", "donor_assigned", "donor_updated"}
)
DIGEST_KEYS = (
    "organization_id",
    "scope",
    "owner_user_id",
    "subject_type",
    "trigger_type",
    "trigger_config",
    "conditions",
    "condition_logic",
    "actions",
)
FORCED_APPROVAL_FILTER = (
    """@> '[{"action_type": "send_email", "requires_approval": true}]'::jsonb"""
)


def _parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except TypeError, ValueError:
        return None


def _workflow_is_donor_context(
    subject_type: str | None,
    trigger_type: str,
    trigger_config: object,
    form_kind: str | None,
) -> bool:
    """Frozen resolve_effective_workflow_subject_type, reduced to donor context."""
    if subject_type in DONOR_SUBJECT_TYPES:
        return True
    context_key = INTAKE_CONTEXT_KEYS.get(trigger_type)
    if context_key is None:
        return False
    config = trigger_config if isinstance(trigger_config, dict) else {}
    configured_kind = config.get(context_key)
    form_id = config.get("form_id")
    if configured_kind in DONOR_SUBJECT_TYPES or form_kind in DONOR_SUBJECT_TYPES:
        return True
    if configured_kind == "surrogate" or form_kind == "surrogate":
        return False
    if form_id and form_kind is None and configured_kind is None:
        return True
    return not form_id and configured_kind is None


def _unbound_is_donor_context(
    subject_type: str | None, trigger_type: str, trigger_config: dict
) -> bool:
    """Frozen resolve_unbound_workflow_subject_type, reduced to donor context."""
    if subject_type is None:
        subject_type = LEGACY_TRIGGER_SUBJECT_TYPES.get(trigger_type, "surrogate")
    if subject_type in DONOR_SUBJECT_TYPES:
        return True
    context_key = INTAKE_CONTEXT_KEYS.get(trigger_type)
    if context_key is None:
        return False
    configured_kind = trigger_config.get(context_key)
    if configured_kind in DONOR_SUBJECT_TYPES:
        return True
    if trigger_config.get("form_id") or trigger_config.get("form_name"):
        return True
    return configured_kind != "surrogate"


def _template_is_donor_context(
    subject_type: str | None,
    trigger_type: str,
    trigger_config: object,
    form_kind: str | None,
) -> bool:
    """Frozen resolve_effective_template_subject_type, reduced to donor context."""
    config = dict(trigger_config) if isinstance(trigger_config, dict) else {}
    context_key = INTAKE_CONTEXT_KEYS.get(trigger_type)
    if context_key and config.get("form_id"):
        configured_kind = config.pop(context_key, None)
        config.pop("form_id", None)
        if form_kind in DONOR_SUBJECT_TYPES:
            config[context_key] = form_kind
        elif configured_kind in DONOR_SUBJECT_TYPES:
            config[context_key] = configured_kind
        elif form_kind == "surrogate":
            config[context_key] = form_kind
    if subject_type is None and trigger_type in DONOR_ONLY_TRIGGER_TYPES:
        return True
    return _unbound_is_donor_context(subject_type, trigger_type, config)


def _form_id(trigger_type: str, trigger_config: object) -> UUID | None:
    if trigger_type not in INTAKE_CONTEXT_KEYS or not isinstance(trigger_config, dict):
        return None
    form_id = trigger_config.get("form_id")
    return _parse_uuid(form_id) if form_id else None


def _clear_forced_approval(actions: object) -> list | None:
    """Return the actions with send_email approval cleared, or None when nothing changes."""
    if not isinstance(actions, list):
        return None
    changed = False
    result = []
    for action in actions:
        if (
            isinstance(action, dict)
            and action.get("action_type") == "send_email"
            and action.get("requires_approval") is True
        ):
            action = {**action, "requires_approval": False}
            changed = True
        result.append(action)
    return result if changed else None


def _configuration_digest(config: dict) -> str:
    """Frozen workflow_execution_authority.configuration_digest."""
    return sha256(
        json.dumps(
            {key: config[key] for key in DIGEST_KEYS},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()


def _form_kinds(connection, references: set[tuple[UUID, UUID]]) -> dict[tuple[UUID, UUID], str]:
    if not references:
        return {}
    rows = connection.execute(
        sa.text("SELECT organization_id, id, lead_kind FROM forms WHERE id = ANY(:ids)"),
        {"ids": sorted({form_id for _, form_id in references})},
    ).all()
    return {(org_id, form_id): lead_kind for org_id, form_id, lead_kind in rows}


def _upgrade_workflows(connection) -> None:
    rows = (
        connection.execute(
            sa.text(
                "SELECT id, organization_id, scope, owner_user_id, subject_type, trigger_type, "
                "trigger_config, conditions, condition_logic, actions, execution_authority "
                f"FROM automation_workflows WHERE actions {FORCED_APPROVAL_FILTER}"
            )
        )
        .mappings()
        .all()
    )
    references = {
        (row["organization_id"], form_id)
        for row in rows
        if (form_id := _form_id(row["trigger_type"], row["trigger_config"])) is not None
    }
    form_kinds = _form_kinds(connection, references)
    for row in rows:
        form_id = _form_id(row["trigger_type"], row["trigger_config"])
        form_kind = form_kinds.get((row["organization_id"], form_id)) if form_id else None
        if not _workflow_is_donor_context(
            row["subject_type"], row["trigger_type"], row["trigger_config"], form_kind
        ):
            continue
        actions = _clear_forced_approval(row["actions"])
        if actions is None:
            continue
        authority = row["execution_authority"]
        sealed = isinstance(authority, dict) and (
            authority.get("configuration_digest") == _configuration_digest(dict(row))
        )
        if sealed:
            authority = {
                **authority,
                "configuration_digest": _configuration_digest({**row, "actions": actions}),
            }
        connection.execute(
            sa.text(
                "UPDATE automation_workflows SET actions = CAST(:actions AS jsonb), "
                "execution_authority = CAST(:authority AS jsonb), updated_at = now() "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "actions": json.dumps(actions),
                "authority": None if authority is None else json.dumps(authority),
            },
        )


def _upgrade_templates(connection) -> None:
    rows = (
        connection.execute(
            sa.text(
                "SELECT id, organization_id, subject_type, trigger_type, trigger_config, "
                "actions, draft_config FROM workflow_templates "
                f"WHERE actions {FORCED_APPROVAL_FILTER} "
                f"OR draft_config->'actions' {FORCED_APPROVAL_FILTER}"
            )
        )
        .mappings()
        .all()
    )
    references = set()
    for row in rows:
        form_id = _form_id(row["trigger_type"], row["trigger_config"])
        if form_id is not None and row["organization_id"] is not None:
            references.add((row["organization_id"], form_id))
    form_kinds = _form_kinds(connection, references)
    for row in rows:
        form_id = _form_id(row["trigger_type"], row["trigger_config"])
        form_kind = (
            form_kinds.get((row["organization_id"], form_id))
            if form_id and row["organization_id"] is not None
            else None
        )
        if _template_is_donor_context(
            row["subject_type"], row["trigger_type"], row["trigger_config"], form_kind
        ):
            actions = _clear_forced_approval(row["actions"])
            if actions is not None:
                connection.execute(
                    sa.text(
                        "UPDATE workflow_templates SET actions = CAST(:actions AS jsonb) "
                        "WHERE id = :id"
                    ),
                    {"id": row["id"], "actions": json.dumps(actions)},
                )

        draft = row["draft_config"]
        if not isinstance(draft, dict):
            continue
        # Draft publishing validates without a tenant form lookup.
        draft_trigger = draft.get("trigger_type") or row["trigger_type"]
        draft_config = draft.get("trigger_config")
        if not _template_is_donor_context(
            draft.get("subject_type", row["subject_type"]),
            draft_trigger,
            draft_config if isinstance(draft_config, dict) else {},
            None,
        ):
            continue
        draft_actions = _clear_forced_approval(draft.get("actions"))
        if draft_actions is not None:
            connection.execute(
                sa.text(
                    "UPDATE workflow_templates SET draft_config = jsonb_set(draft_config, "
                    "'{actions}', CAST(:actions AS jsonb)) WHERE id = :id"
                ),
                {"id": row["id"], "actions": json.dumps(draft_actions)},
            )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()
    _upgrade_workflows(connection)
    _upgrade_templates(connection)


def downgrade() -> None:
    pass
