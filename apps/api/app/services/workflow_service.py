"""Workflow service - CRUD operations for automation workflows."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.db.models import (
    AutomationWorkflow,
    WorkflowExecution,
    UserWorkflowPreference,
    User,
    Queue,
    EmailTemplate,
)
from app.db.enums import WorkflowTriggerType, WorkflowExecutionStatus, OwnerType
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowRead,
    WorkflowStats,
    WorkflowOptions,
    ALLOWED_CONDITION_FIELDS,
    ALLOWED_UPDATE_FIELDS,
    ALLOWED_EMAIL_VARIABLES,
    StatusChangeTriggerConfig,
    ScheduledTriggerConfig,
    TaskDueTriggerConfig,
    InactivityTriggerConfig,
    SurrogateUpdatedTriggerConfig,
    FormStartedTriggerConfig,
    FormSubmittedTriggerConfig,
    IntakeLeadCreatedTriggerConfig,
    SendEmailActionConfig,
    CreateTaskActionConfig,
    AssignSurrogateActionConfig,
    SendNotificationActionConfig,
    UpdateFieldActionConfig,
    AddNoteActionConfig,
    PromoteIntakeLeadActionConfig,
    AutoMatchSubmissionActionConfig,
    CreateIntakeLeadActionConfig,
)
from app.services import user_service
from app.services.workflow_email_provider import validate_email_provider


# =============================================================================
# Constants
# =============================================================================


TRIGGER_ENTITY_TYPES = {
    "surrogate_created": "surrogate",
    "status_changed": "surrogate",
    "surrogate_assigned": "surrogate",
    "surrogate_updated": "surrogate",
    "form_started": "surrogate",
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "task_due": "task",
    "task_overdue": "task",
    "scheduled": "surrogate",
    "inactivity": "surrogate",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_rejected": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
    "note_added": "note",
    "document_uploaded": "document",
}


# =============================================================================
# CRUD Operations
# =============================================================================


def create_workflow(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: WorkflowCreate,
) -> AutomationWorkflow:
    """Create a new workflow with validation."""
    # Validate trigger config
    _validate_trigger_config(data.trigger_type, data.trigger_config)

    actions = _normalize_actions_for_trigger(data.trigger_type, data.actions)

    # Validate actions
    for action in actions:
        _validate_action_config(db, org_id, action, data.scope, user_id)

    # Determine owner_user_id based on scope
    owner_user_id = user_id if data.scope == "personal" else None

    # Validate email provider if there's a send_email action
    if _has_send_email_action(actions):
        is_valid, error = validate_email_provider(db, data.scope, org_id, owner_user_id)
        if not is_valid:
            raise ValueError(error)

    workflow = AutomationWorkflow(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        scope=data.scope,
        owner_user_id=owner_user_id,
        trigger_type=data.trigger_type.value,
        trigger_config=data.trigger_config,
        conditions=[c.model_dump() for c in data.conditions],
        condition_logic=data.condition_logic,
        actions=actions,
        is_enabled=data.is_enabled,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )

    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def _has_send_email_action(actions: list[dict]) -> bool:
    """Check if actions list contains a send_email action."""
    return any(action.get("action_type") == "send_email" for action in actions)


def update_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
    data: WorkflowUpdate,
) -> AutomationWorkflow:
    """Update an existing workflow with validation."""
    if data.trigger_type is not None or data.trigger_config is not None:
        trigger_type = data.trigger_type or WorkflowTriggerType(workflow.trigger_type)
        trigger_config = (
            data.trigger_config if data.trigger_config is not None else workflow.trigger_config
        )
        _validate_trigger_config(trigger_type, trigger_config)

    normalized_actions = data.actions
    effective_trigger_type = data.trigger_type or WorkflowTriggerType(workflow.trigger_type)
    if data.actions is not None:
        normalized_actions = _normalize_actions_for_trigger(effective_trigger_type, data.actions)
        for action in normalized_actions:
            _validate_action_config(
                db,
                workflow.organization_id,
                action,
                workflow.scope,
                workflow.owner_user_id,
            )
        if _has_send_email_action(normalized_actions):
            is_valid, error = validate_email_provider(
                db,
                workflow.scope,
                workflow.organization_id,
                workflow.owner_user_id,
            )
            if not is_valid:
                raise ValueError(error)

    # Update fields
    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    if data.icon is not None:
        workflow.icon = data.icon
    if data.trigger_type is not None:
        workflow.trigger_type = data.trigger_type.value
    if data.trigger_config is not None:
        workflow.trigger_config = data.trigger_config
    if data.conditions is not None:
        workflow.conditions = [c.model_dump() for c in data.conditions]
    if data.condition_logic is not None:
        workflow.condition_logic = data.condition_logic
    if normalized_actions is not None:
        workflow.actions = normalized_actions
    if data.is_enabled is not None:
        workflow.is_enabled = data.is_enabled

    workflow.updated_by_user_id = user_id
    workflow.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(workflow)
    return workflow


def delete_workflow(db: Session, workflow: AutomationWorkflow) -> None:
    """Delete a workflow and all related data."""
    db.delete(workflow)
    db.commit()


def get_workflow(
    db: Session,
    workflow_id: UUID,
    org_id: UUID,
) -> AutomationWorkflow | None:
    """Get a workflow by ID, scoped to org."""
    return (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.id == workflow_id,
            AutomationWorkflow.organization_id == org_id,
        )
        .first()
    )


def list_workflows(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
    has_manage_permission: bool = False,
    scope_filter: str | None = None,
    enabled_only: bool = False,
    trigger_type: WorkflowTriggerType | None = None,
) -> list[AutomationWorkflow]:
    """
    List workflows for an organization with scope-based filtering.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: Current user ID (for filtering personal workflows)
        has_manage_permission: If True, user can see all workflows
        scope_filter: Optional filter: 'org' or 'personal'
        enabled_only: Only return enabled workflows
        trigger_type: Filter by trigger type

    Returns:
        List of workflows the user can see
    """
    query = db.query(AutomationWorkflow).filter(AutomationWorkflow.organization_id == org_id)

    # Apply scope filter
    if scope_filter == "org":
        query = query.filter(AutomationWorkflow.scope == "org")
    elif scope_filter == "personal":
        # Personal scope: only show user's own personal workflows
        if user_id:
            query = query.filter(
                AutomationWorkflow.scope == "personal",
                AutomationWorkflow.owner_user_id == user_id,
            )
        else:
            # No user_id means no personal workflows visible
            query = query.filter(AutomationWorkflow.scope == "personal", False)
    else:
        # No scope filter: show based on permissions
        if has_manage_permission:
            # Admin sees all workflows (org + all personal)
            pass
        elif user_id:
            # Non-admin: org workflows + own personal workflows
            query = query.filter(
                or_(
                    AutomationWorkflow.scope == "org",
                    and_(
                        AutomationWorkflow.scope == "personal",
                        AutomationWorkflow.owner_user_id == user_id,
                    ),
                )
            )
        else:
            # No user_id: only org workflows
            query = query.filter(AutomationWorkflow.scope == "org")

    if enabled_only:
        query = query.filter(AutomationWorkflow.is_enabled.is_(True))

    if trigger_type:
        query = query.filter(AutomationWorkflow.trigger_type == trigger_type.value)

    return query.order_by(AutomationWorkflow.name).all()


def toggle_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
) -> AutomationWorkflow:
    """Toggle a workflow's enabled state."""
    workflow.is_enabled = not workflow.is_enabled
    workflow.updated_by_user_id = user_id
    workflow.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workflow)
    return workflow


def duplicate_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
    new_scope: str | None = None,
) -> AutomationWorkflow:
    """
    Duplicate an existing workflow.

    Args:
        db: Database session
        workflow: Workflow to duplicate
        user_id: User creating the duplicate
        new_scope: Scope for the new workflow. If None:
            - Org workflows stay org (requires permission check upstream)
            - Personal workflows become owned by the duplicating user
    """
    # Determine scope and owner for duplicate
    scope = new_scope or workflow.scope
    owner_user_id = user_id if scope == "personal" else None

    # Find unique name
    base_name = f"{workflow.name} (Copy)"
    name = base_name
    counter = 1
    while (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == workflow.organization_id,
            AutomationWorkflow.name == name,
        )
        .first()
    ):
        counter += 1
        name = f"{base_name} {counter}"

    new_workflow = AutomationWorkflow(
        organization_id=workflow.organization_id,
        name=name,
        description=workflow.description,
        icon=workflow.icon,
        scope=scope,
        owner_user_id=owner_user_id,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=False,  # Start disabled
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )

    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)
    return new_workflow


# =============================================================================
# Stats & Options
# =============================================================================


def get_workflow_stats(db: Session, org_id: UUID) -> WorkflowStats:
    """Get workflow statistics for dashboard."""
    from app.db.models import Task
    from app.db.enums import TaskType, TaskStatus

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    # Total and enabled counts
    total = (
        db.query(func.count(AutomationWorkflow.id))
        .filter(AutomationWorkflow.organization_id == org_id)
        .scalar()
        or 0
    )

    enabled = (
        db.query(func.count(AutomationWorkflow.id))
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .scalar()
        or 0
    )

    # Executions in last 24h
    executions_24h = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
        )
        .scalar()
        or 0
    )

    # Success rate
    if executions_24h > 0:
        successes = (
            db.query(func.count(WorkflowExecution.id))
            .filter(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.executed_at >= day_ago,
                WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value,
            )
            .scalar()
            or 0
        )
        success_rate = round(successes / executions_24h * 100, 1)
    else:
        success_rate = 0.0

    # By trigger type
    by_trigger = {}
    trigger_counts = (
        db.query(AutomationWorkflow.trigger_type, func.count(AutomationWorkflow.id))
        .filter(AutomationWorkflow.organization_id == org_id)
        .group_by(AutomationWorkflow.trigger_type)
        .all()
    )

    for trigger_type, count in trigger_counts:
        by_trigger[trigger_type] = count

    # By scope
    org_workflows = (
        db.query(func.count(AutomationWorkflow.id))
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.scope == "org",
        )
        .scalar()
        or 0
    )
    personal_workflows = (
        db.query(func.count(AutomationWorkflow.id))
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.scope == "personal",
        )
        .scalar()
        or 0
    )

    # ==========================================================================
    # Approval Metrics
    # ==========================================================================

    # Pending approvals count
    pending_approvals = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == org_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
        )
        .scalar()
        or 0
    )

    # Resolved approvals in last 24h (completed, denied, expired)
    resolved_statuses = [
        TaskStatus.COMPLETED.value,
        TaskStatus.DENIED.value,
        TaskStatus.EXPIRED.value,
    ]

    # Get counts by status for resolved approvals in 24h
    resolved_counts = (
        db.query(Task.status, func.count(Task.id))
        .filter(
            Task.organization_id == org_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_(resolved_statuses),
            Task.updated_at >= day_ago,
        )
        .group_by(Task.status)
        .all()
    )

    resolved_by_status = {status: count for status, count in resolved_counts}
    approved_24h = resolved_by_status.get(TaskStatus.COMPLETED.value, 0)
    denied_24h = resolved_by_status.get(TaskStatus.DENIED.value, 0)
    expired_24h = resolved_by_status.get(TaskStatus.EXPIRED.value, 0)
    total_resolved_24h = approved_24h + denied_24h + expired_24h

    # Calculate rates
    if total_resolved_24h > 0:
        approval_rate = round(approved_24h / total_resolved_24h * 100, 1)
        denial_rate = round(denied_24h / total_resolved_24h * 100, 1)
        expiry_rate = round(expired_24h / total_resolved_24h * 100, 1)
    else:
        approval_rate = 0.0
        denial_rate = 0.0
        expiry_rate = 0.0

    # Average approval latency (for approved tasks only, in hours)
    avg_latency = (
        db.query(func.avg(func.extract("epoch", Task.completed_at - Task.created_at) / 3600))
        .filter(
            Task.organization_id == org_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status == TaskStatus.COMPLETED.value,
            Task.completed_at.isnot(None),
            Task.updated_at >= day_ago,
        )
        .scalar()
    )

    return WorkflowStats(
        total_workflows=total,
        enabled_workflows=enabled,
        total_executions_24h=executions_24h,
        success_rate_24h=success_rate,
        by_trigger_type=by_trigger,
        org_workflows=org_workflows,
        personal_workflows=personal_workflows,
        # Approval metrics
        pending_approvals=pending_approvals,
        approvals_resolved_24h=total_resolved_24h,
        approval_rate_24h=approval_rate,
        denial_rate_24h=denial_rate,
        expiry_rate_24h=expiry_rate,
        avg_approval_latency_hours=round(avg_latency, 2) if avg_latency else None,
    )


def get_workflow_options(
    db: Session,
    org_id: UUID,
    workflow_scope: str | None = None,
    user_id: UUID | None = None,
) -> WorkflowOptions:
    """Get available options for workflow builder UI."""
    # Trigger types with descriptions
    trigger_types = [
        {
            "value": "surrogate_created",
            "label": "Surrogate Created",
            "description": "When a new case is created",
        },
        {
            "value": "status_changed",
            "label": "Status Changed",
            "description": "When case status changes",
        },
        {
            "value": "surrogate_assigned",
            "label": "Surrogate Assigned",
            "description": "When case is assigned",
        },
        {
            "value": "surrogate_updated",
            "label": "Surrogate Updated",
            "description": "When specific fields change",
        },
        {
            "value": "form_started",
            "label": "Form Started",
            "description": "When an applicant starts a form draft",
        },
        {
            "value": "form_submitted",
            "label": "Application Submitted",
            "description": "When an applicant submits a form",
        },
        {
            "value": "intake_lead_created",
            "label": "Intake Lead Created",
            "description": "When shared intake creates a provisional lead",
        },
        {
            "value": "task_due",
            "label": "Task Due",
            "description": "Before a task is due",
        },
        {
            "value": "task_overdue",
            "label": "Task Overdue",
            "description": "When a task becomes overdue",
        },
        {
            "value": "scheduled",
            "label": "Scheduled",
            "description": "On a recurring schedule",
        },
        {
            "value": "inactivity",
            "label": "Inactivity",
            "description": "When case has no activity",
        },
        {
            "value": "match_proposed",
            "label": "Match Proposed",
            "description": "When a match is proposed",
        },
        {
            "value": "match_accepted",
            "label": "Match Accepted",
            "description": "When a match is accepted",
        },
        {
            "value": "match_rejected",
            "label": "Match Rejected",
            "description": "When a match is rejected",
        },
        {
            "value": "appointment_scheduled",
            "label": "Appointment Scheduled",
            "description": "When an appointment is scheduled",
        },
        {
            "value": "appointment_completed",
            "label": "Appointment Completed",
            "description": "When an appointment is completed",
        },
        {
            "value": "note_added",
            "label": "Note Added",
            "description": "When a note is added to a case",
        },
        {
            "value": "document_uploaded",
            "label": "Document Uploaded",
            "description": "When a document is uploaded",
        },
    ]

    # Action types
    action_types = [
        {
            "value": "send_email",
            "label": "Send Email",
            "description": "Send email using template",
        },
        {
            "value": "create_task",
            "label": "Create Task",
            "description": "Create a task on the case",
        },
        {
            "value": "assign_surrogate",
            "label": "Assign Surrogate",
            "description": "Assign to user or queue",
        },
        {
            "value": "send_notification",
            "label": "Send Notification",
            "description": "Send in-app notification",
        },
        {
            "value": "update_field",
            "label": "Update Field",
            "description": "Update a case field",
        },
        {
            "value": "add_note",
            "label": "Add Note",
            "description": "Add a note to the case",
        },
        {
            "value": "promote_intake_lead",
            "label": "Promote Intake Lead",
            "description": "Create surrogate case from intake lead",
        },
        {
            "value": "auto_match_submission",
            "label": "Auto-Match Submission",
            "description": "Try deterministic match to an existing surrogate",
        },
        {
            "value": "create_intake_lead",
            "label": "Create Intake Lead",
            "description": "Create provisional intake lead for unmatched submission",
        },
    ]

    surrogate_action_values = [
        "send_email",
        "create_task",
        "assign_surrogate",
        "send_notification",
        "update_field",
        "add_note",
    ]
    form_submission_action_values = [
        "auto_match_submission",
        "create_intake_lead",
        *surrogate_action_values,
    ]
    action_types_by_trigger: dict[str, list[str]] = {}
    for trigger, entity_type in TRIGGER_ENTITY_TYPES.items():
        if entity_type in ("surrogate", "task"):
            action_types_by_trigger[trigger] = surrogate_action_values
        elif entity_type == "form_submission":
            action_types_by_trigger[trigger] = form_submission_action_values
        elif entity_type == "intake_lead":
            action_types_by_trigger[trigger] = ["send_notification", "promote_intake_lead"]
        else:
            action_types_by_trigger[trigger] = ["send_notification"]

    # Condition operators
    condition_operators = [
        {"value": "equals", "label": "Equals"},
        {"value": "not_equals", "label": "Does not equal"},
        {"value": "contains", "label": "Contains"},
        {"value": "not_contains", "label": "Does not contain"},
        {"value": "is_empty", "label": "Is empty"},
        {"value": "is_not_empty", "label": "Is not empty"},
        {"value": "in", "label": "Is one of"},
        {"value": "not_in", "label": "Is not one of"},
        {"value": "greater_than", "label": "Greater than"},
        {"value": "less_than", "label": "Less than"},
    ]

    # Email templates - scope-aware filtering
    # For org workflows: only org + system templates
    # For personal workflows: personal (user's own) + org + system templates
    from sqlalchemy import or_, and_
    from app.services import system_email_template_service

    template_query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.is_active.is_(True),
    )

    platform_system_keys = set(system_email_template_service.DEFAULT_SYSTEM_TEMPLATES.keys())
    if platform_system_keys:
        template_query = template_query.filter(
            or_(
                EmailTemplate.system_key.is_(None),
                EmailTemplate.system_key.notin_(platform_system_keys),
            )
        )

    if workflow_scope == "org":
        # Org workflows can only use org templates (including system templates)
        template_query = template_query.filter(EmailTemplate.scope == "org")
    elif workflow_scope == "personal" and user_id:
        # Personal workflows can use user's personal templates + org templates
        template_query = template_query.filter(
            or_(
                EmailTemplate.scope == "org",
                and_(
                    EmailTemplate.scope == "personal",
                    EmailTemplate.owner_user_id == user_id,
                ),
            )
        )
    else:
        # Default: show all org templates (for backward compatibility)
        template_query = template_query.filter(EmailTemplate.scope == "org")

    templates = template_query.order_by(EmailTemplate.scope.desc(), EmailTemplate.name).all()
    email_templates = [{"id": str(t.id), "name": t.name, "scope": t.scope} for t in templates]

    # Users in org
    from app.db.models import Membership

    user_rows = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .all()
    )
    users = [
        {"id": str(user_id), "display_name": display_name} for user_id, display_name in user_rows
    ]

    # Queues
    queues = db.query(Queue).filter(Queue.organization_id == org_id).all()
    queue_options = [{"id": str(q.id), "name": q.name} for q in queues]

    # Stages (status options)
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    statuses = [
        {"id": str(s.id), "value": s.slug, "label": s.label, "is_active": s.is_active}
        for s in stages
    ]

    # Forms (published)
    from app.db.models import Form
    from app.db.enums import FormStatus

    published_forms = (
        db.query(Form)
        .filter(
            Form.organization_id == org_id,
            Form.status == FormStatus.PUBLISHED.value,
        )
        .order_by(Form.name.asc())
        .all()
    )
    forms = [{"id": str(f.id), "name": f.name} for f in published_forms]

    return WorkflowOptions(
        trigger_types=trigger_types,
        action_types=action_types,
        action_types_by_trigger=action_types_by_trigger,
        trigger_entity_types=TRIGGER_ENTITY_TYPES,
        condition_operators=condition_operators,
        condition_fields=list(ALLOWED_CONDITION_FIELDS),
        update_fields=list(ALLOWED_UPDATE_FIELDS),
        email_variables=list(ALLOWED_EMAIL_VARIABLES),
        email_templates=email_templates,
        users=users,
        queues=queue_options,
        statuses=statuses,
        forms=forms,
    )


# =============================================================================
# Execution History
# =============================================================================


def list_executions(
    db: Session,
    workflow_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WorkflowExecution], int]:
    """List executions for a workflow with pagination."""
    query = db.query(WorkflowExecution).filter(WorkflowExecution.workflow_id == workflow_id)

    total = query.count()
    items = query.order_by(WorkflowExecution.executed_at.desc()).offset(offset).limit(limit).all()

    return items, total


def list_org_executions(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    workflow_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    List all workflow executions for an organization with filters.

    Returns executions with workflow name joined for display.
    """
    query = (
        db.query(WorkflowExecution, AutomationWorkflow.name)
        .join(AutomationWorkflow, WorkflowExecution.workflow_id == AutomationWorkflow.id)
        .filter(WorkflowExecution.organization_id == org_id)
    )

    if status:
        query = query.filter(WorkflowExecution.status == status)

    if workflow_id:
        query = query.filter(WorkflowExecution.workflow_id == workflow_id)

    total = query.count()
    items = query.order_by(WorkflowExecution.executed_at.desc()).offset(offset).limit(limit).all()

    # Build response with workflow name
    result = []
    for exec, workflow_name in items:
        result.append(
            {
                "id": exec.id,
                "workflow_id": exec.workflow_id,
                "workflow_name": workflow_name or "Unknown",
                "status": exec.status,
                "entity_type": exec.entity_type,
                "entity_id": exec.entity_id,
                "action_count": len(exec.actions_executed) if exec.actions_executed else 0,
                "duration_ms": exec.duration_ms or 0,
                "executed_at": exec.executed_at.isoformat(),
                "trigger_event": exec.trigger_event,
                "actions_executed": exec.actions_executed or [],
                "error_message": exec.error_message,
                "skip_reason": None if exec.matched_conditions else "Conditions not met",
            }
        )

    return result, total


def get_execution(db: Session, org_id: UUID, execution_id: UUID) -> WorkflowExecution | None:
    """Fetch a single execution scoped to an organization."""
    return (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.id == execution_id,
        )
        .first()
    )


def get_execution_stats(db: Session, org_id: UUID) -> dict:
    """Get execution statistics for the dashboard."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    # Total in last 24h
    total_24h = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
        )
        .scalar()
        or 0
    )

    # Failed in last 24h
    failed_24h = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
            WorkflowExecution.status == WorkflowExecutionStatus.FAILED.value,
        )
        .scalar()
        or 0
    )

    # Success rate
    if total_24h > 0:
        successes = (
            db.query(func.count(WorkflowExecution.id))
            .filter(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.executed_at >= day_ago,
                WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value,
            )
            .scalar()
            or 0
        )
        success_rate = round(successes / total_24h * 100, 1)
    else:
        success_rate = 0.0

    # Average duration
    avg_duration = (
        db.query(func.avg(WorkflowExecution.duration_ms))
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
            WorkflowExecution.duration_ms.isnot(None),
        )
        .scalar()
        or 0
    )

    return {
        "total_24h": total_24h,
        "failed_24h": failed_24h,
        "success_rate": success_rate,
        "avg_duration_ms": int(avg_duration),
    }


# =============================================================================
# User Preferences
# =============================================================================


def get_user_preferences(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> list[UserWorkflowPreference]:
    """Get user's workflow preferences."""
    return (
        db.query(UserWorkflowPreference)
        .join(AutomationWorkflow)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            AutomationWorkflow.organization_id == org_id,
        )
        .all()
    )


def update_user_preference(
    db: Session,
    user_id: UUID,
    workflow_id: UUID,
    is_opted_out: bool,
) -> UserWorkflowPreference:
    """Update user's preference for a workflow."""
    pref = (
        db.query(UserWorkflowPreference)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            UserWorkflowPreference.workflow_id == workflow_id,
        )
        .first()
    )

    if pref:
        pref.is_opted_out = is_opted_out
    else:
        pref = UserWorkflowPreference(
            user_id=user_id,
            workflow_id=workflow_id,
            is_opted_out=is_opted_out,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)
    return pref


def is_user_opted_out(
    db: Session,
    user_id: UUID,
    workflow_id: UUID,
) -> bool:
    """Check if user has opted out of a workflow."""
    pref = (
        db.query(UserWorkflowPreference)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            UserWorkflowPreference.workflow_id == workflow_id,
        )
        .first()
    )

    return pref.is_opted_out if pref else False


def to_workflow_read(
    db: Session,
    workflow: AutomationWorkflow,
    can_edit: bool = True,
) -> WorkflowRead:
    """Convert workflow model to read schema with user names."""
    created_by_name = None
    updated_by_name = None
    owner_name = None

    if workflow.created_by_user_id:
        user = user_service.get_user_by_id(db, workflow.created_by_user_id)
        created_by_name = user.display_name if user else None

    if workflow.updated_by_user_id:
        user = user_service.get_user_by_id(db, workflow.updated_by_user_id)
        updated_by_name = user.display_name if user else None

    if workflow.owner_user_id:
        user = user_service.get_user_by_id(db, workflow.owner_user_id)
        owner_name = user.display_name if user else None

    return WorkflowRead(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        schema_version=workflow.schema_version,
        scope=workflow.scope,
        owner_user_id=workflow.owner_user_id,
        owner_name=owner_name,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=workflow.is_enabled,
        run_count=workflow.run_count,
        last_run_at=workflow.last_run_at,
        last_error=workflow.last_error,
        created_by_name=created_by_name,
        updated_by_name=updated_by_name,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        can_edit=can_edit,
    )


def to_workflow_list_item(
    db: Session,
    workflow: AutomationWorkflow,
    can_edit: bool = True,
):
    """Convert workflow model to list item schema with owner name."""
    from app.schemas.workflow import WorkflowListItem

    owner_name = None
    if workflow.owner_user_id:
        user = user_service.get_user_by_id(db, workflow.owner_user_id)
        owner_name = user.display_name if user else None

    return WorkflowListItem(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        scope=workflow.scope,
        owner_user_id=workflow.owner_user_id,
        owner_name=owner_name,
        trigger_type=workflow.trigger_type,
        is_enabled=workflow.is_enabled,
        run_count=workflow.run_count,
        last_run_at=workflow.last_run_at,
        last_error=workflow.last_error,
        created_at=workflow.created_at,
        can_edit=can_edit,
    )


# =============================================================================
# Validation Helpers
# =============================================================================


def _normalize_actions_for_trigger(
    trigger_type: WorkflowTriggerType,
    actions: list[dict],
) -> list[dict]:
    """Normalize workflow actions for trigger-specific rules."""
    normalized = [dict(action) for action in actions]
    if trigger_type != WorkflowTriggerType.FORM_SUBMITTED:
        return normalized

    auto_match_indices = [
        idx for idx, action in enumerate(normalized) if action.get("action_type") == "auto_match_submission"
    ]
    create_lead_indices = [
        idx for idx, action in enumerate(normalized) if action.get("action_type") == "create_intake_lead"
    ]
    if auto_match_indices and create_lead_indices:
        first_match_idx = auto_match_indices[0]
        first_create_idx = create_lead_indices[0]
        if first_match_idx > first_create_idx:
            raise ValueError(
                "For form_submitted workflows, auto_match_submission must be placed before create_intake_lead"
            )

    return normalized


def _validate_trigger_config(trigger_type: WorkflowTriggerType, config: dict) -> None:
    """Validate trigger config matches the trigger type schema."""
    validators = {
        WorkflowTriggerType.STATUS_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.SCHEDULED: ScheduledTriggerConfig,
        WorkflowTriggerType.TASK_DUE: TaskDueTriggerConfig,
        WorkflowTriggerType.INACTIVITY: InactivityTriggerConfig,
        WorkflowTriggerType.SURROGATE_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.FORM_STARTED: FormStartedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMITTED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.INTAKE_LEAD_CREATED: IntakeLeadCreatedTriggerConfig,
    }

    validator = validators.get(trigger_type)
    if validator:
        validator.model_validate(config)


def _validate_action_config(
    db: Session,
    org_id: UUID,
    action: dict,
    workflow_scope: str | None = None,
    owner_user_id: UUID | None = None,
) -> None:
    """Validate action config and referenced entities exist in org."""
    action_type = action.get("action_type")

    if action_type == "update_status":
        stage_id = action.get("stage_id")
        if not stage_id:
            raise ValueError("update_status requires stage_id")
        action["action_type"] = "update_field"
        action["field"] = "stage_id"
        action["value"] = stage_id
        action.pop("stage_id", None)
        action_type = action.get("action_type")

    if action_type == "send_email":
        config = SendEmailActionConfig.model_validate(action)
        # Verify template exists in org
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == config.template_id,
                EmailTemplate.organization_id == org_id,
            )
            .first()
        )
        if not template:
            raise ValueError(f"Email template {config.template_id} not found in organization")
        # Validate internal recipients (if explicit list)
        if isinstance(config.recipients, list):
            from app.db.models import Membership

            recipient_ids = set(config.recipients)
            rows = (
                db.query(Membership.user_id)
                .filter(
                    Membership.organization_id == org_id,
                    Membership.user_id.in_(recipient_ids),
                    Membership.is_active.is_(True),
                )
                .all()
            )
            found_ids = {row[0] for row in rows}
            missing_ids = recipient_ids - found_ids
            if missing_ids:
                missing_str = ", ".join(str(uid) for uid in sorted(missing_ids, key=str))
                raise ValueError(f"Missing recipients in organization: {missing_str}")
        # Enforce scope rules for workflow email templates
        if workflow_scope == "org":
            if template.scope != "org":
                raise ValueError("Org workflows cannot use personal email templates")
        elif workflow_scope == "personal":
            if template.scope == "personal" and template.owner_user_id != owner_user_id:
                raise ValueError("Personal email templates must be owned by the workflow owner")

    elif action_type == "create_task":
        config = CreateTaskActionConfig.model_validate(action)
        # If assignee is UUID, verify user exists in org
        if isinstance(config.assignee, UUID):
            from app.db.models import Membership

            membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == config.assignee,
                    Membership.organization_id == org_id,
                    Membership.is_active.is_(True),
                )
                .first()
            )
            if not membership:
                raise ValueError(f"User {config.assignee} not found in organization")

    elif action_type == "assign_surrogate":
        config = AssignSurrogateActionConfig.model_validate(action)
        # Verify owner exists in org
        if config.owner_type == OwnerType.USER:
            from app.db.models import Membership

            membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == config.owner_id,
                    Membership.organization_id == org_id,
                    Membership.is_active.is_(True),
                )
                .first()
            )
            if not membership:
                raise ValueError(f"User {config.owner_id} not found in organization")
        elif config.owner_type == OwnerType.QUEUE:
            queue = (
                db.query(Queue)
                .filter(
                    Queue.id == config.owner_id,
                    Queue.organization_id == org_id,
                )
                .first()
            )
            if not queue:
                raise ValueError(f"Queue {config.owner_id} not found in organization")

    elif action_type == "send_notification":
        config = SendNotificationActionConfig.model_validate(action)
        # If recipients is list of UUIDs, verify all exist
        if isinstance(config.recipients, list):
            from app.db.models import Membership

            recipient_ids = set(config.recipients)
            rows = (
                db.query(Membership.user_id)
                .filter(
                    Membership.organization_id == org_id,
                    Membership.user_id.in_(recipient_ids),
                    Membership.is_active.is_(True),
                )
                .all()
            )
            found_ids = {row[0] for row in rows}
            missing_ids = recipient_ids - found_ids
            if missing_ids:
                missing_list = ", ".join(str(user_id) for user_id in missing_ids)
                raise ValueError(f"Users not found in organization: {missing_list}")

    elif action_type == "update_field":
        UpdateFieldActionConfig.model_validate(action)

    elif action_type == "add_note":
        AddNoteActionConfig.model_validate(action)

    elif action_type == "promote_intake_lead":
        PromoteIntakeLeadActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("promote_intake_lead is only supported for org workflows")
        if action.get("requires_approval") is True:
            raise ValueError("promote_intake_lead does not support requires_approval")

    elif action_type == "auto_match_submission":
        AutoMatchSubmissionActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("auto_match_submission is only supported for org workflows")

    elif action_type == "create_intake_lead":
        CreateIntakeLeadActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("create_intake_lead is only supported for org workflows")

    else:
        raise ValueError(f"Unknown action type: {action_type}")

    # Validate requires_approval field (optional, defaults to False)
    requires_approval = action.get("requires_approval", False)
    if requires_approval is not None and not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be a boolean")
