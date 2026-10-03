"""Organization-scoped repair for the module-routing deployment window."""

import copy
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, and_, cast, or_
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType
from app.db.models import (
    AutomationWorkflow,
    Form,
    FormSubmission,
    Job,
    Organization,
    Task,
    WorkflowExecution,
)
from app.services import (
    audit_service,
    form_routing_service,
    permission_policy_service,
    workflow_execution_authority,
)
from app.services.workflow_engine_core import (
    FORM_SUBMISSION_ACTION_SNAPSHOT_KEY,
    complete_paused_executions,
)
from app.services.workflow_routing_retirement import (
    GENERATED_ROUTING_PREFIX,
    RETIRED_ROUTING_ACTIONS,
    cancel_paused_routing_execution,
    strip_retired_routing_actions,
)

logger = logging.getLogger(__name__)


def repair_routing_window(
    db: Session, *, org_id: UUID, window_start: datetime, released_at: datetime, apply: bool = False
) -> dict[str, int | list[str]]:
    for timestamp in (window_start, released_at):
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Window timestamps must include a timezone")
    if window_start > released_at:
        raise ValueError("Window start must not be after release timestamp")
    if db.query(Organization.id).filter(Organization.id == org_id).first() is None:
        raise ValueError("Organization not found")

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            or_(
                *[
                    AutomationWorkflow.actions.contains([{"action_type": action}])
                    for action in sorted(RETIRED_ROUTING_ACTIONS)
                ],
                and_(
                    AutomationWorkflow.system_key.startswith(
                        GENERATED_ROUTING_PREFIX, autoescape=True
                    ),
                    AutomationWorkflow.actions != [],
                ),
            ),
        )
        .order_by(AutomationWorkflow.id)
    )
    completed = (
        db.query(Job.id)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == "form_submission_workflow",
            Job.status == "completed",
            Job.completed_at >= released_at,
            Job.payload["submission_id"].astext == cast(FormSubmission.id, String),
        )
        .exists()
    )
    submissions = (
        db.query(FormSubmission.id)
        .join(
            Form,
            (Form.id == FormSubmission.form_id)
            & (Form.organization_id == FormSubmission.organization_id),
        )
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.source_mode == "shared",
            FormSubmission.submitted_at >= window_start,
            FormSubmission.submitted_at <= released_at,
            FormSubmission.status == "pending_review",
            FormSubmission.match_status == "workflow_pending",
            FormSubmission.surrogate_id.is_(None),
            FormSubmission.donor_id.is_(None),
            FormSubmission.intake_lead_id.is_(None),
            ~completed,
        )
        .order_by(FormSubmission.id)
    )
    paused = (
        db.query(WorkflowExecution, AutomationWorkflow, Task)
        .join(
            AutomationWorkflow,
            (AutomationWorkflow.id == WorkflowExecution.workflow_id)
            & (AutomationWorkflow.organization_id == WorkflowExecution.organization_id),
        )
        .outerjoin(
            Task,
            (Task.id == WorkflowExecution.paused_task_id)
            & (Task.workflow_execution_id == WorkflowExecution.id)
            & (Task.organization_id == WorkflowExecution.organization_id)
            & (Task.task_type == "workflow_approval"),
        )
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.status == "paused",
            WorkflowExecution.executed_at >= window_start,
            WorkflowExecution.executed_at <= released_at,
        )
        .order_by(WorkflowExecution.id)
    )
    result = {"workflow_ids": [], "submission_ids": [], "execution_ids": []}
    if not apply:
        result["workflow_ids"] = [str(w.id) for w in workflows.all()]
        result["submission_ids"] = [str(s.id) for s in submissions.all()]
        result["execution_ids"] = [
            str(e.id) for e, w, t in paused.all() if _paused_on_retired_action(e, w, t)
        ]
        return _counts(result)

    permission_policy_service.lock_configuration(db, org_id)
    changed = 0
    try:
        for workflow in workflows.with_for_update().populate_existing().all():
            original = copy.deepcopy(workflow.actions)
            current_grant = workflow_execution_authority.grant_is_current(workflow)
            # Preserve action indices for pending approvals. Never rewrite terminal history.
            executions = (
                db.query(WorkflowExecution)
                .filter(
                    WorkflowExecution.organization_id == org_id,
                    WorkflowExecution.workflow_id == workflow.id,
                    WorkflowExecution.status.in_(["running", "paused"]),
                )
                .order_by(WorkflowExecution.id)
                .with_for_update()
                .all()
            )
            for execution in executions:
                event = execution.trigger_event or {}
                if FORM_SUBMISSION_ACTION_SNAPSHOT_KEY not in event:
                    execution.trigger_event = {
                        **event,
                        FORM_SUBMISSION_ACTION_SNAPSHOT_KEY: original,
                    }
            workflow.actions = strip_retired_routing_actions(original)
            workflow.is_enabled = workflow.is_enabled and bool(workflow.actions)
            if workflow.actions and (workflow.system_key or "").startswith(
                GENERATED_ROUTING_PREFIX
            ):
                workflow.system_key = None
                workflow.is_system_workflow = False
            if current_grant:
                workflow.execution_authority = {
                    **workflow.execution_authority,
                    "configuration_digest": workflow_execution_authority.configuration_digest(
                        workflow
                    ),
                }
            audit_service.log_event(
                db,
                org_id,
                AuditEventType.WORKFLOW_CONFIG_CHANGED,
                target_type="workflow",
                target_id=workflow.id,
                details={"operation": "retire_routing", "scope": workflow.scope},
            )
            # Sessions disable autoflush; the next audit entry must see this hash.
            db.flush()
            changed += 1
            result["workflow_ids"].append(str(workflow.id))
            logger.info(
                "Retired workflow routing: workflow_id=%s organization_id=%s", workflow.id, org_id
            )
        if changed:
            permission_policy_service.touch_configuration(db, org_id)
        completions = []
        for execution, workflow, task in (
            paused.with_for_update(of=WorkflowExecution).populate_existing().all()
        ):
            if _paused_on_retired_action(execution, workflow, task):
                completions.append((execution, workflow, execution.paused_at_action_index))
                cancel_paused_routing_execution(db, execution)
                result["execution_ids"].append(str(execution.id))
        result["submission_ids"].extend(
            str(submission_id) for submission_id in complete_paused_executions(db, completions)
        )
    except Exception:
        db.rollback()
        raise

    # Each route owns its atomic domain/audit transaction and row lock. Committed
    # repairs survive an interrupted run; replay skips already-routed submissions.
    submission_ids = [row.id for row in submissions.all()]
    for submission_id in submission_ids:
        # Recheck eligibility under the routing row lock, including completion of a
        # concurrent release job, before route_submission can write anything.
        form_routing_service.lock_submission(db, org_id, submission_id)
        if submissions.filter(FormSubmission.id == submission_id).first() is None:
            db.commit()
            continue
        form_routing_service.route_submission(db, org_id=org_id, submission_id=submission_id)
        result["submission_ids"].append(str(submission_id))
    return _counts(result)


def _counts(result: dict[str, list[str]]) -> dict[str, int | list[str]]:
    return {
        **result,
        "workflows": len(result["workflow_ids"]),
        "submissions": len(result["submission_ids"]),
        "executions": len(result["execution_ids"]),
    }


def _paused_on_retired_action(
    execution: WorkflowExecution, workflow: AutomationWorkflow, task: Task | None
) -> bool:
    if task is not None:
        action = task.workflow_action_payload or {}
        if isinstance(action, dict) and action.get("action_type"):
            return action["action_type"] in RETIRED_ROUTING_ACTIONS
        if task.workflow_action_type:
            return task.workflow_action_type in RETIRED_ROUTING_ACTIONS
    snapshot = (execution.trigger_event or {}).get(FORM_SUBMISSION_ACTION_SNAPSHOT_KEY)
    actions = snapshot if isinstance(snapshot, list) else workflow.actions
    index = execution.paused_at_action_index
    return bool(
        isinstance(index, int)
        and 0 <= index < len(actions or [])
        and isinstance(actions[index], dict)
        and actions[index].get("action_type") in RETIRED_ROUTING_ACTIONS
    )
