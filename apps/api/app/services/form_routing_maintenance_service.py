"""Organization-scoped repair for the module-routing deployment window."""

import copy
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType
from app.db.models import (
    AutomationWorkflow,
    Form,
    FormSubmission,
    Job,
    Organization,
    WorkflowExecution,
)
from app.services import (
    audit_service,
    form_routing_service,
    permission_policy_service,
    workflow_execution_authority,
)
from app.services.workflow_engine_core import FORM_SUBMISSION_ACTION_SNAPSHOT_KEY
from app.services.workflow_routing_retirement import (
    RETIRED_ROUTING_ACTIONS,
    strip_retired_routing_actions,
)

logger = logging.getLogger(__name__)


def repair_routing_window(
    db: Session, *, org_id: UUID, released_at: datetime, apply: bool = False
) -> dict[str, int]:
    if released_at.tzinfo is None or released_at.utcoffset() is None:
        raise ValueError("Release timestamp must include a timezone")
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
                ]
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
            FormSubmission.status == "pending_review",
            FormSubmission.match_status == "workflow_pending",
            FormSubmission.surrogate_id.is_(None),
            FormSubmission.donor_id.is_(None),
            FormSubmission.intake_lead_id.is_(None),
            ~completed,
        )
        .order_by(FormSubmission.id)
    )
    if not apply:
        return {"workflows": workflows.count(), "submissions": submissions.count()}

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
            logger.info(
                "Retired workflow routing: workflow_id=%s organization_id=%s", workflow.id, org_id
            )
        if changed:
            permission_policy_service.touch_configuration(db, org_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Each route owns its atomic domain/audit transaction and row lock. Committed
    # repairs survive an interrupted run; replay skips already-routed submissions.
    submission_ids = [row.id for row in submissions.all()]
    routed = 0
    for submission_id in submission_ids:
        # Recheck eligibility under the routing row lock, including completion of a
        # concurrent release job, before route_submission can write anything.
        form_routing_service.lock_submission(db, org_id, submission_id)
        if submissions.filter(FormSubmission.id == submission_id).first() is None:
            db.commit()
            continue
        form_routing_service.route_submission(db, org_id=org_id, submission_id=submission_id)
        routed += 1
    return {"workflows": changed, "submissions": routed}
