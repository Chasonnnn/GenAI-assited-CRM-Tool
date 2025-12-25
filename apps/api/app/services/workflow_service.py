"""Workflow service - CRUD operations for automation workflows."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.db.models import (
    AutomationWorkflow, WorkflowExecution, UserWorkflowPreference,
    User, Queue, EmailTemplate
)
from app.db.enums import (
    WorkflowTriggerType, WorkflowActionType, WorkflowExecutionStatus,
    OwnerType
)
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowRead, WorkflowListItem,
    WorkflowStats, WorkflowOptions,
    ALLOWED_CONDITION_FIELDS, ALLOWED_UPDATE_FIELDS, ALLOWED_EMAIL_VARIABLES,
    StatusChangeTriggerConfig, ScheduledTriggerConfig, TaskDueTriggerConfig,
    InactivityTriggerConfig, CaseUpdatedTriggerConfig,
    SendEmailActionConfig, CreateTaskActionConfig, AssignCaseActionConfig,
    SendNotificationActionConfig, UpdateFieldActionConfig, AddNoteActionConfig,
)


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
    
    # Validate actions
    for action in data.actions:
        _validate_action_config(db, org_id, action)
    
    workflow = AutomationWorkflow(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        trigger_type=data.trigger_type.value,
        trigger_config=data.trigger_config,
        conditions=[c.model_dump() for c in data.conditions],
        condition_logic=data.condition_logic,
        actions=data.actions,
        is_enabled=data.is_enabled,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def update_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
    data: WorkflowUpdate,
) -> AutomationWorkflow:
    """Update an existing workflow with validation."""
    if data.trigger_type is not None or data.trigger_config is not None:
        trigger_type = data.trigger_type or WorkflowTriggerType(workflow.trigger_type)
        trigger_config = data.trigger_config if data.trigger_config is not None else workflow.trigger_config
        _validate_trigger_config(trigger_type, trigger_config)
    
    if data.actions is not None:
        for action in data.actions:
            _validate_action_config(db, workflow.organization_id, action)
    
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
    if data.actions is not None:
        workflow.actions = data.actions
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
    return db.query(AutomationWorkflow).filter(
        AutomationWorkflow.id == workflow_id,
        AutomationWorkflow.organization_id == org_id,
    ).first()


def list_workflows(
    db: Session,
    org_id: UUID,
    enabled_only: bool = False,
    trigger_type: WorkflowTriggerType | None = None,
) -> list[AutomationWorkflow]:
    """List workflows for an organization."""
    query = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == org_id
    )
    
    if enabled_only:
        query = query.filter(AutomationWorkflow.is_enabled == True)
    
    if trigger_type:
        query = query.filter(AutomationWorkflow.trigger_type == trigger_type.value)
    
    return query.order_by(AutomationWorkflow.created_at.desc()).all()


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
) -> AutomationWorkflow:
    """Duplicate an existing workflow."""
    # Find unique name
    base_name = f"{workflow.name} (Copy)"
    name = base_name
    counter = 1
    while db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == workflow.organization_id,
        AutomationWorkflow.name == name,
    ).first():
        counter += 1
        name = f"{base_name} {counter}"
    
    new_workflow = AutomationWorkflow(
        organization_id=workflow.organization_id,
        name=name,
        description=workflow.description,
        icon=workflow.icon,
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
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    
    # Total and enabled counts
    total = db.query(func.count(AutomationWorkflow.id)).filter(
        AutomationWorkflow.organization_id == org_id
    ).scalar() or 0
    
    enabled = db.query(func.count(AutomationWorkflow.id)).filter(
        AutomationWorkflow.organization_id == org_id,
        AutomationWorkflow.is_enabled == True,
    ).scalar() or 0
    
    # Executions in last 24h
    executions_24h = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
    ).scalar() or 0
    
    # Success rate
    if executions_24h > 0:
        successes = db.query(func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
            WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value,
        ).scalar() or 0
        success_rate = round(successes / executions_24h * 100, 1)
    else:
        success_rate = 0.0
    
    # By trigger type
    by_trigger = {}
    trigger_counts = db.query(
        AutomationWorkflow.trigger_type,
        func.count(AutomationWorkflow.id)
    ).filter(
        AutomationWorkflow.organization_id == org_id
    ).group_by(AutomationWorkflow.trigger_type).all()
    
    for trigger_type, count in trigger_counts:
        by_trigger[trigger_type] = count
    
    return WorkflowStats(
        total_workflows=total,
        enabled_workflows=enabled,
        total_executions_24h=executions_24h,
        success_rate_24h=success_rate,
        by_trigger_type=by_trigger,
    )


def get_workflow_options(db: Session, org_id: UUID) -> WorkflowOptions:
    """Get available options for workflow builder UI."""
    # Trigger types with descriptions
    trigger_types = [
        {"value": "case_created", "label": "Case Created", "description": "When a new case is created"},
        {"value": "status_changed", "label": "Status Changed", "description": "When case status changes"},
        {"value": "case_assigned", "label": "Case Assigned", "description": "When case is assigned"},
        {"value": "case_updated", "label": "Case Updated", "description": "When specific fields change"},
        {"value": "task_due", "label": "Task Due", "description": "Before a task is due"},
        {"value": "task_overdue", "label": "Task Overdue", "description": "When a task becomes overdue"},
        {"value": "scheduled", "label": "Scheduled", "description": "On a recurring schedule"},
        {"value": "inactivity", "label": "Inactivity", "description": "When case has no activity"},
    ]
    
    # Action types
    action_types = [
        {"value": "send_email", "label": "Send Email", "description": "Send email using template"},
        {"value": "create_task", "label": "Create Task", "description": "Create a task on the case"},
        {"value": "assign_case", "label": "Assign Case", "description": "Assign to user or queue"},
        {"value": "send_notification", "label": "Send Notification", "description": "Send in-app notification"},
        {"value": "update_field", "label": "Update Field", "description": "Update a case field"},
        {"value": "add_note", "label": "Add Note", "description": "Add a note to the case"},
    ]
    
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
    
    # Email templates
    templates = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.is_active == True,
    ).all()
    email_templates = [{"id": str(t.id), "name": t.name} for t in templates]
    
    # Users in org
    from app.db.models import Membership
    memberships = db.query(Membership).filter(
        Membership.organization_id == org_id
    ).all()
    users = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            users.append({"id": str(user.id), "display_name": user.display_name})
    
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
    
    return WorkflowOptions(
        trigger_types=trigger_types,
        action_types=action_types,
        condition_operators=condition_operators,
        condition_fields=list(ALLOWED_CONDITION_FIELDS),
        update_fields=list(ALLOWED_UPDATE_FIELDS),
        email_variables=list(ALLOWED_EMAIL_VARIABLES),
        email_templates=email_templates,
        users=users,
        queues=queue_options,
        statuses=statuses,
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
    query = db.query(WorkflowExecution).filter(
        WorkflowExecution.workflow_id == workflow_id
    )
    
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
    query = db.query(WorkflowExecution).join(
        AutomationWorkflow, WorkflowExecution.workflow_id == AutomationWorkflow.id
    ).filter(
        WorkflowExecution.organization_id == org_id
    )
    
    if status:
        query = query.filter(WorkflowExecution.status == status)
    
    if workflow_id:
        query = query.filter(WorkflowExecution.workflow_id == workflow_id)
    
    total = query.count()
    items = query.order_by(WorkflowExecution.executed_at.desc()).offset(offset).limit(limit).all()
    
    # Build response with workflow name
    result = []
    for exec in items:
        workflow = db.query(AutomationWorkflow).filter(
            AutomationWorkflow.id == exec.workflow_id
        ).first()
        
        result.append({
            "id": exec.id,
            "workflow_id": exec.workflow_id,
            "workflow_name": workflow.name if workflow else "Unknown",
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
        })
    
    return result, total


def get_execution_stats(db: Session, org_id: UUID) -> dict:
    """Get execution statistics for the dashboard."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    
    # Total in last 24h
    total_24h = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
    ).scalar() or 0
    
    # Failed in last 24h
    failed_24h = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
        WorkflowExecution.status == WorkflowExecutionStatus.FAILED.value,
    ).scalar() or 0
    
    # Success rate
    if total_24h > 0:
        successes = db.query(func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.executed_at >= day_ago,
            WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value,
        ).scalar() or 0
        success_rate = round(successes / total_24h * 100, 1)
    else:
        success_rate = 0.0
    
    # Average duration
    avg_duration = db.query(func.avg(WorkflowExecution.duration_ms)).filter(
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
        WorkflowExecution.duration_ms.isnot(None),
    ).scalar() or 0
    
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
    return db.query(UserWorkflowPreference).join(
        AutomationWorkflow
    ).filter(
        UserWorkflowPreference.user_id == user_id,
        AutomationWorkflow.organization_id == org_id,
    ).all()


def update_user_preference(
    db: Session,
    user_id: UUID,
    workflow_id: UUID,
    is_opted_out: bool,
) -> UserWorkflowPreference:
    """Update user's preference for a workflow."""
    pref = db.query(UserWorkflowPreference).filter(
        UserWorkflowPreference.user_id == user_id,
        UserWorkflowPreference.workflow_id == workflow_id,
    ).first()
    
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
    pref = db.query(UserWorkflowPreference).filter(
        UserWorkflowPreference.user_id == user_id,
        UserWorkflowPreference.workflow_id == workflow_id,
    ).first()
    
    return pref.is_opted_out if pref else False


# =============================================================================
# Validation Helpers
# =============================================================================

def _validate_trigger_config(trigger_type: WorkflowTriggerType, config: dict) -> None:
    """Validate trigger config matches the trigger type schema."""
    validators = {
        WorkflowTriggerType.STATUS_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.SCHEDULED: ScheduledTriggerConfig,
        WorkflowTriggerType.TASK_DUE: TaskDueTriggerConfig,
        WorkflowTriggerType.INACTIVITY: InactivityTriggerConfig,
        WorkflowTriggerType.CASE_UPDATED: CaseUpdatedTriggerConfig,
    }
    
    validator = validators.get(trigger_type)
    if validator:
        validator.model_validate(config)


def _validate_action_config(db: Session, org_id: UUID, action: dict) -> None:
    """Validate action config and referenced entities exist in org."""
    action_type = action.get("action_type")
    
    if action_type == "send_email":
        config = SendEmailActionConfig.model_validate(action)
        # Verify template exists in org
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == config.template_id,
            EmailTemplate.organization_id == org_id,
        ).first()
        if not template:
            raise ValueError(f"Email template {config.template_id} not found in organization")
    
    elif action_type == "create_task":
        config = CreateTaskActionConfig.model_validate(action)
        # If assignee is UUID, verify user exists in org
        if isinstance(config.assignee, UUID):
            from app.db.models import Membership
            membership = db.query(Membership).filter(
                Membership.user_id == config.assignee,
                Membership.organization_id == org_id,
            ).first()
            if not membership:
                raise ValueError(f"User {config.assignee} not found in organization")
    
    elif action_type == "assign_case":
        config = AssignCaseActionConfig.model_validate(action)
        # Verify owner exists in org
        if config.owner_type == OwnerType.USER:
            from app.db.models import Membership
            membership = db.query(Membership).filter(
                Membership.user_id == config.owner_id,
                Membership.organization_id == org_id,
            ).first()
            if not membership:
                raise ValueError(f"User {config.owner_id} not found in organization")
        elif config.owner_type == OwnerType.QUEUE:
            queue = db.query(Queue).filter(
                Queue.id == config.owner_id,
                Queue.organization_id == org_id,
            ).first()
            if not queue:
                raise ValueError(f"Queue {config.owner_id} not found in organization")
    
    elif action_type == "send_notification":
        config = SendNotificationActionConfig.model_validate(action)
        # If recipients is list of UUIDs, verify all exist
        if isinstance(config.recipients, list):
            from app.db.models import Membership
            for user_id in config.recipients:
                membership = db.query(Membership).filter(
                    Membership.user_id == user_id,
                    Membership.organization_id == org_id,
                ).first()
                if not membership:
                    raise ValueError(f"User {user_id} not found in organization")
    
    elif action_type == "update_field":
        UpdateFieldActionConfig.model_validate(action)
    
    elif action_type == "add_note":
        AddNoteActionConfig.model_validate(action)
    
    else:
        raise ValueError(f"Unknown action type: {action_type}")
