"""Move workflow-owned intake routing into per-form settings.

Revision ID: 20261003_1400_migrate_form_routing
Revises: 20261003_1300_form_module_routing

Literal definitions deliberately survive removal of the former workflow actions.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20261003_1400_migrate_form_routing"
down_revision = "20261003_1300_form_module_routing"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")
ROUTING_ACTIONS = {"auto_match_submission", "create_intake_lead"}


def _settings(actions: list[dict], *, donor: bool, enabled: bool) -> dict:
    match = next((a for a in actions if a.get("action_type") == "auto_match_submission"), None)
    create = next((a for a in actions if a.get("action_type") == "create_intake_lead"), None)
    source = create.get("source") if create else None
    return {
        "routing_exact_match": "review"
        if not enabled or match is None or match.get("requires_approval")
        else "auto",
        "routing_no_match": "off"
        if not enabled or create is None
        else "review"
        if create.get("requires_approval")
        else "auto",
        "routing_lead_source": source
        if isinstance(source, str) and source in {"website", "form_embed"}
        else None,
        "routing_auto_create_donor": donor and bool(create and create.get("auto_promote") is True),
    }


# Only the columns used here are declared; migration code never imports application models.
workflows = sa.table(
    "automation_workflows",
    sa.column("id", sa.Uuid()),
    sa.column("organization_id", sa.Uuid()),
    sa.column("actions", JSONB),
    sa.column("is_enabled", sa.Boolean()),
    sa.column("is_system_workflow", sa.Boolean()),
    sa.column("system_key", sa.String()),
    sa.column("execution_authority", JSONB),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
forms = sa.table(
    "forms",
    sa.column("id", sa.Uuid()),
    sa.column("organization_id", sa.Uuid()),
    sa.column("routing_exact_match", sa.String()),
    sa.column("routing_no_match", sa.String()),
    sa.column("routing_lead_source", sa.String()),
    sa.column("routing_auto_create_donor", sa.Boolean()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def _digest(workflow: dict) -> str:
    config = {
        key: workflow[key]
        for key in (
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
    }
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _merge(settings: list[dict]) -> dict:
    # A paused/reviewed route must not become automatic because another route conflicts.
    result = dict(settings[0])
    result["routing_exact_match"] = (
        "review" if any(s["routing_exact_match"] == "review" for s in settings) else "auto"
    )
    result["routing_no_match"] = max(
        (s["routing_no_match"] for s in settings), key={"auto": 0, "review": 1, "off": 2}.get
    )
    sources = {s["routing_lead_source"] for s in settings}
    result["routing_lead_source"] = sources.pop() if len(sources) == 1 else None
    result["routing_auto_create_donor"] = all(s["routing_auto_create_donor"] for s in settings)
    return result


def _migrate_paused(connection) -> None:
    rows = (
        connection.execute(
            sa.text("""
        SELECT e.*, w.actions AS current_actions, f.name AS form_name,
               f.updated_by_user_id AS form_editor, f.created_by_user_id AS form_creator,
               s.id AS submission_id, s.surrogate_id, s.donor_id, s.intake_lead_id
        FROM workflow_executions e
        JOIN automation_workflows w ON w.id = e.workflow_id AND w.organization_id = e.organization_id
        JOIN form_submissions s ON s.id = e.entity_id AND s.organization_id = e.organization_id
        JOIN forms f ON f.id = s.form_id AND f.organization_id = s.organization_id
        WHERE e.status = 'paused' AND e.entity_type = 'form_submission'
        ORDER BY e.executed_at, e.id
        FOR UPDATE OF e, s, w, f
    """)
        )
        .mappings()
        .all()
    )
    for row in rows:
        task = (
            connection.execute(
                sa.text("""
            SELECT * FROM tasks WHERE organization_id = :org AND workflow_execution_id = :execution
              AND id = :task AND task_type = 'workflow_approval' FOR UPDATE
        """),
                {
                    "org": row["organization_id"],
                    "execution": row["id"],
                    "task": row["paused_task_id"],
                },
            )
            .mappings()
            .first()
        )
        snapshot = (row["trigger_event"] or {}).get("_form_submission_workflow_actions")
        actions = snapshot if isinstance(snapshot, list) else (row["current_actions"] or [])
        index = row["paused_at_action_index"]
        action = (task["workflow_action_payload"] or {}) if task else {}
        if not action and isinstance(index, int) and 0 <= index < len(actions):
            action = actions[index]
        action_type = action.get("action_type")
        if action_type not in ROUTING_ACTIONS:
            continue
        # An invalid cross-tenant record link must never be copied to a review task.
        for table, key in (
            ("surrogates", "surrogate_id"),
            ("donors", "donor_id"),
            ("intake_leads", "intake_lead_id"),
        ):
            if (
                row[key]
                and not connection.execute(
                    sa.text(f"SELECT 1 FROM {table} WHERE id = :id AND organization_id = :org"),
                    {"id": row[key], "org": row["organization_id"]},
                ).first()
            ):
                logger.warning(
                    "Cross-organization submission link skipped: submission_id=%s organization_id=%s",
                    row["submission_id"],
                    row["organization_id"],
                )
        params = {
            "org": row["organization_id"],
            "execution": row["id"],
            "submission": row["submission_id"],
        }
        connection.execute(
            sa.text("""
            UPDATE tasks t SET status = 'completed', is_completed = TRUE, completed_at = now(), updated_at = now(),
                completed_by_user_id = '00000000-0000-0000-0000-000000000001'::uuid
            WHERE t.organization_id = :org AND t.workflow_execution_id = :execution
              AND t.task_type = 'workflow_approval' AND t.status IN ('pending', 'in_progress')
              AND EXISTS (SELECT 1 FROM workflow_executions e WHERE e.id = t.workflow_execution_id
                AND e.organization_id = t.organization_id AND e.status = 'paused')
        """),
            params,
        )
        connection.execute(
            sa.text("""
            UPDATE workflow_executions SET status = 'canceled', paused_at_action_index = NULL,
                paused_task_id = NULL, error_message = 'Workflow routing retired'
            WHERE organization_id = :org AND id = :execution AND status = 'paused'
        """),
            params,
        )
        logger.info("Workflow %s: canceled routing execution %s", row["workflow_id"], row["id"])
        step = "match" if action_type == "auto_match_submission" else "create_lead"
        # The old resume path ignored resolved/rejected submissions and candidate-bearing
        # create requests. Preserve those decisions rather than reopening their review.
        review = connection.execute(
            sa.text("""
            UPDATE form_submissions s SET match_status = 'routing_review', routing_review_step = :step
            WHERE s.id = :submission AND s.organization_id = :org
              AND s.status = 'pending_review' AND s.surrogate_id IS NULL
              AND s.donor_id IS NULL AND s.intake_lead_id IS NULL
              AND s.match_status IN ('workflow_pending', 'ambiguous_review')
              AND (:step = 'match' OR NOT EXISTS (
                SELECT 1 FROM form_submission_match_candidates c
                WHERE c.submission_id = s.id AND c.organization_id = s.organization_id))
            RETURNING s.id
        """),
            {**params, "step": step},
        ).first()
        if review is None:
            continue
        members = (
            connection.execute(
                sa.text("""
            SELECT u.id, m.role FROM memberships m JOIN users u ON u.id = m.user_id
            WHERE m.organization_id = :org AND m.is_active AND u.is_active ORDER BY u.created_at, u.id
            FOR SHARE OF m, u
        """),
                {"org": row["organization_id"]},
            )
            .mappings()
            .all()
        )
        member_ids = {m["id"] for m in members}
        candidates = [
            task["owner_id"] if task and task["owner_type"] == "user" else None,
            row["form_editor"],
            row["form_creator"],
        ]
        owner = next((candidate for candidate in candidates if candidate in member_ids), None)
        owner = owner or next(
            (m["id"] for m in members if m["role"] in {"admin", "developer"}), None
        )
        if owner is None:
            logger.warning(
                "Routing reviewer unavailable: submission_id=%s organization_id=%s",
                row["submission_id"],
                row["organization_id"],
            )
        # Preserve the original approval deadline, including its business-hours calculation.
        connection.execute(
            sa.text("""
            INSERT INTO tasks (id, organization_id, form_submission_id, surrogate_id, donor_id,
                task_type, title, owner_type, owner_id, status, created_by_user_id, due_at, due_date, due_time)
            SELECT :id, :org, :submission, :surrogate, :donor, 'review', :title, 'user', :owner,
                'pending', '00000000-0000-0000-0000-000000000001', :due,
                (CAST(:due AS timestamptz) AT TIME ZONE 'UTC')::date,
                (CAST(:due AS timestamptz) AT TIME ZONE 'UTC')::time
            WHERE CAST(:owner AS uuid) IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM tasks WHERE organization_id = :org
                AND form_submission_id = :submission AND task_type = 'review'
                AND status IN ('pending', 'in_progress'))
        """),
            {
                **params,
                "id": uuid4(),
                "surrogate": row["surrogate_id"],
                "donor": row["donor_id"],
                "title": f"Review submission: {row['form_name']}"[:255],
                "owner": owner,
                "due": task["due_at"] if task else None,
            },
        )
        logger.info(
            "Workflow %s: canceled routing execution %s; submission %s awaits %s review",
            row["workflow_id"],
            row["id"],
            row["submission_id"],
            step,
        )


def _preserve_snapshots(connection, workflow):
    # Terminal history is immutable. Active executions need the original action order
    # if an older worker did not checkpoint it. Retired actions fail closed on resume.
    connection.execute(
        sa.text("""
        UPDATE workflow_executions e
        SET trigger_event = COALESCE(e.trigger_event, '{}'::jsonb) ||
            jsonb_build_object('_form_submission_workflow_actions', CAST(:actions AS jsonb))
        FROM automation_workflows w
        WHERE w.id = e.workflow_id AND w.organization_id = e.organization_id
          AND w.id = :workflow AND w.organization_id = :org
          AND e.status IN ('running', 'paused')
          AND NOT (COALESCE(e.trigger_event, '{}'::jsonb) ? '_form_submission_workflow_actions')
    """),
        {
            "workflow": workflow["id"],
            "org": workflow["organization_id"],
            "actions": json.dumps(workflow["actions"] or []),
        },
    )


def _retire_template_actions(connection):
    # Platform-global library templates are explicit; tenant templates stay scoped by org.
    rows = (
        connection.execute(
            sa.text(
                "SELECT id, organization_id, actions, draft_config FROM workflow_templates ORDER BY id FOR UPDATE"
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        actions = [a for a in row["actions"] or [] if a.get("action_type") not in ROUTING_ACTIONS]
        draft = row["draft_config"]
        changed = actions != (row["actions"] or [])
        if isinstance(draft, dict) and isinstance(draft.get("actions"), list):
            remaining = [a for a in draft["actions"] if a.get("action_type") not in ROUTING_ACTIONS]
            if remaining != draft["actions"]:
                draft = {**draft, "actions": remaining}
                changed = True
        if not changed:
            continue
        connection.execute(
            sa.text("""
            UPDATE workflow_templates SET actions = CAST(:actions AS jsonb), draft_config = CAST(:draft AS jsonb),
                status = CASE WHEN :empty THEN 'draft' ELSE status END,
                published_version = CASE WHEN :empty THEN 0 ELSE published_version END,
                is_published_globally = CASE WHEN :empty THEN FALSE ELSE is_published_globally END,
                updated_at = now()
            WHERE id = :id AND organization_id IS NOT DISTINCT FROM :org
        """),
            {
                "id": row["id"],
                "org": row["organization_id"],
                "actions": json.dumps(actions),
                "draft": json.dumps(draft) if draft is not None else None,
                "empty": not actions,
            },
        )
        logger.info(
            "Workflow template %s: removed routing actions%s",
            row["id"],
            "; unpublished empty template" if not actions else "",
        )


def _grant_is_current(connection, workflow) -> bool:
    # Match the retired generated-routing authorization without importing live models.
    return bool(
        connection.execute(
            sa.text("""
                SELECT 1 FROM automation_workflows w
                WHERE w.id = :id AND w.organization_id = :org
                  AND w.execution_authority->>'organization_id' = CAST(w.organization_id AS text)
                  AND w.execution_authority->>'configuration_digest' = :digest
            """),
            {
                "id": workflow["id"],
                "org": workflow["organization_id"],
                "digest": _digest(workflow),
            },
        ).first()
    )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()
    # Match runtime configuration locking so policy activation cannot change the
    # authority version while its workflows are being mapped (including v1 orgs
    # that do not yet have a permission-policy row).
    connection.execute(sa.text("SELECT id FROM organizations ORDER BY id FOR NO KEY UPDATE")).all()
    rows = (
        connection.execute(
            sa.text("""
        SELECT w.*, COALESCE(p.version, 1) AS permission_policy_version
        FROM automation_workflows w
        LEFT JOIN organization_permission_policies p ON p.organization_id = w.organization_id
        ORDER BY w.organization_id, w.created_at, w.id
        FOR UPDATE OF w
    """)
        )
        .mappings()
        .all()
    )
    _migrate_paused(connection)
    mapped = {}
    for row in rows:
        workflow = dict(row)
        actions = workflow["actions"] or []
        if not any(a.get("action_type") in ROUTING_ACTIONS for a in actions):
            continue
        config = workflow["trigger_config"] or {}
        target = config.get("form_id")
        if not target and str(workflow["system_key"] or "").startswith("shared_intake_routing:"):
            target = workflow["system_key"].split(":", 1)[1]
        valid_binding = (
            workflow["scope"] == "org"
            and workflow["subject_type"] == "form_submission"
            and workflow["trigger_type"]
            in {"form_submitted", "form_submission_approved", "form_submission_rejected"}
        )
        try:
            target = UUID(str(target)) if target else None
        except ValueError:
            valid_binding = False
            target = None
            logger.warning(
                "Workflow %s: invalid form binding; routing actions stripped", workflow["id"]
            )
        affected = (
            (
                connection.execute(
                    sa.text("""
            SELECT f.* FROM forms f JOIN automation_workflows w ON w.organization_id = f.organization_id
            WHERE w.id = :workflow AND w.organization_id = :org
              AND (CAST(:form AS uuid) IS NULL OR f.id = :form)
              AND (CAST(:kind AS text) IS NULL OR f.lead_kind = :kind)
            FOR UPDATE OF f
        """),
                    {
                        "workflow": workflow["id"],
                        "org": workflow["organization_id"],
                        "form": target,
                        "kind": config.get("lead_kind"),
                    },
                )
                .mappings()
                .all()
            )
            if valid_binding
            else []
        )
        if not affected:
            logger.warning(
                "Workflow %s: no matching same-organization form binding; routing actions stripped",
                workflow["id"],
            )
        paused_authority = workflow["permission_policy_version"] >= 2 and not _grant_is_current(
            connection, workflow
        )
        for form in affected:
            settings = _settings(
                actions,
                donor=form["lead_kind"] in {"egg_donor", "sperm_donor"},
                enabled=workflow["is_enabled"],
            )
            if paused_authority:
                settings = {**settings, "routing_exact_match": "review", "routing_no_match": "off"}
            mapped.setdefault((form["organization_id"], form["id"]), []).append(settings)
        remaining = [a for a in actions if a.get("action_type") not in ROUTING_ACTIONS]
        condition = (workflows.c.id == workflow["id"]) & (
            workflows.c.organization_id == workflow["organization_id"]
        )
        gated_match = next(
            (
                i
                for i, a in enumerate(actions)
                if a.get("action_type") == "auto_match_submission" and a.get("requires_approval")
            ),
            None,
        )
        if gated_match is not None and any(
            a.get("action_type") not in ROUTING_ACTIONS | {"send_email", "send_notification"}
            for a in actions[gated_match + 1 :]
        ):
            logger.warning(
                "Approval-gated record actions require review: workflow_id=%s", workflow["id"]
            )
        _preserve_snapshots(connection, workflow)
        # Never cascade execution history, including corrupt foreign-org references.
        # Only read their existence; all mutations remain scoped to this workflow's org.
        history = connection.execute(
            sa.text("""
            SELECT 1 FROM workflow_executions e
            JOIN automation_workflows w ON w.id = e.workflow_id
            WHERE w.id = :workflow AND w.organization_id = :org LIMIT 1
        """),
            {"workflow": workflow["id"], "org": workflow["organization_id"]},
        ).first()
        if affected and target and not workflow["conditions"] and not remaining and not history:
            connection.execute(workflows.delete().where(condition))
            change = "mapped routing settings; deleted routing-only workflow"
        else:
            grant = workflow["execution_authority"]
            # Removing actions narrows authority. Preserve only a grant valid for the old config.
            if _grant_is_current(connection, workflow):
                grant = {
                    **grant,
                    "configuration_digest": _digest({**workflow, "actions": remaining}),
                }
            connection.execute(
                workflows.update()
                .where(condition)
                .values(
                    actions=remaining,
                    is_enabled=bool(remaining) and workflow["is_enabled"],
                    execution_authority=grant,
                    updated_at=datetime.now(UTC),
                )
            )
            change = "mapped routing settings; stripped routing actions" + (
                "; disabled empty workflow" if not remaining else ""
            )
        logger.info("Workflow %s: %s", workflow["id"], change)
    for (org_id, form_id), settings in mapped.items():
        connection.execute(
            forms.update()
            .where(forms.c.organization_id == org_id, forms.c.id == form_id)
            .values(**_merge(settings), updated_at=datetime.now(UTC))
        )
    # A published form without an applicable old route must remain paused, including
    # forms whose generated route was deleted or still names an earlier lead kind.
    published = (
        connection.execute(
            sa.text(
                "SELECT id, organization_id FROM forms WHERE status = 'published' ORDER BY organization_id, id FOR UPDATE"
            )
        )
        .mappings()
        .all()
    )
    for form in published:
        if (form["organization_id"], form["id"]) not in mapped:
            connection.execute(
                forms.update()
                .where(forms.c.organization_id == form["organization_id"], forms.c.id == form["id"])
                .values(
                    routing_exact_match="review",
                    routing_no_match="off",
                    updated_at=datetime.now(UTC),
                )
            )
    _retire_template_actions(connection)


def downgrade() -> None:
    # Irreversible data rewrite, matching other data-only migrations: removed workflow
    # definitions cannot be reconstructed, and downgrading must not re-enable automation.
    pass
