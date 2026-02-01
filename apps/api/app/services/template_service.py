"""Template service for workflow template marketplace."""

from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import WorkflowTemplate, WorkflowTemplateTarget, AutomationWorkflow


def list_templates(
    db: Session,
    org_id: UUID,
    category: str | None = None,
) -> list[WorkflowTemplate]:
    """
    List available templates (global + org-specific).

    Returns templates visible to the organization.
    """
    target_exists = (
        db.query(WorkflowTemplateTarget)
        .filter(
            WorkflowTemplateTarget.template_id == WorkflowTemplate.id,
            WorkflowTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    query = db.query(WorkflowTemplate).filter(
        or_(
            WorkflowTemplate.organization_id == org_id,
            and_(
                WorkflowTemplate.is_global.is_(True),
                WorkflowTemplate.published_version > 0,
                or_(
                    WorkflowTemplate.is_published_globally.is_(True),
                    target_exists,
                ),
            ),
        )
    )

    if category:
        query = query.filter(WorkflowTemplate.category == category)

    return query.order_by(
        WorkflowTemplate.is_global.desc(),
        WorkflowTemplate.usage_count.desc(),
        WorkflowTemplate.name,
    ).all()


def get_template(
    db: Session,
    template_id: UUID,
    org_id: UUID,
) -> WorkflowTemplate | None:
    """Get a template by ID if accessible to the org."""
    target_exists = (
        db.query(WorkflowTemplateTarget)
        .filter(
            WorkflowTemplateTarget.template_id == WorkflowTemplate.id,
            WorkflowTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.id == template_id,
            or_(
                WorkflowTemplate.organization_id == org_id,
                and_(
                    WorkflowTemplate.is_global.is_(True),
                    WorkflowTemplate.published_version > 0,
                    or_(
                        WorkflowTemplate.is_published_globally.is_(True),
                        target_exists,
                    ),
                ),
            ),
        )
        .first()
    )


def create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    description: str | None,
    category: str,
    trigger_type: str,
    trigger_config: dict,
    conditions: list,
    condition_logic: str,
    actions: list,
    icon: str = "template",
) -> WorkflowTemplate:
    """Create a new org-specific template."""
    existing = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.organization_id == org_id,
            WorkflowTemplate.name == name,
        )
        .first()
    )
    if existing:
        raise ValueError("Template name already exists")

    template = WorkflowTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=name,
        description=description,
        icon=icon,
        category=category,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        conditions=conditions,
        condition_logic=condition_logic,
        actions=actions,
        is_global=False,
        usage_count=0,
    )
    db.add(template)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Template name already exists")
    db.refresh(template)
    return template


def create_template_from_workflow(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    workflow_id: UUID,
    name: str,
    description: str | None,
    category: str = "general",
) -> WorkflowTemplate:
    """Create a template from an existing workflow."""
    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.id == workflow_id,
            AutomationWorkflow.organization_id == org_id,
        )
        .first()
    )

    if not workflow:
        raise ValueError("Workflow not found")

    return create_template(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=name,
        description=description or workflow.description,
        category=category,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        icon=workflow.icon,
    )


def use_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    template_id: UUID,
    workflow_name: str,
    workflow_description: str | None = None,
    is_enabled: bool = True,
    action_overrides: dict | None = None,
    scope: str = "org",
) -> AutomationWorkflow:
    """Create a workflow from a template.

    Returns workflow.
    If actions have missing required fields, a validation error is raised.
    """
    template = get_template(db, template_id, org_id)
    if not template:
        raise ValueError("Template not found")

    # Apply action overrides if provided
    actions = template.actions.copy() if template.actions else []
    if action_overrides:
        if not isinstance(action_overrides, dict):
            raise ValueError("action_overrides must be an object")
        for idx_str, overrides in action_overrides.items():
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid action override index: {idx_str}")
            if idx < 0 or idx >= len(actions):
                raise ValueError(f"Action override index out of range: {idx}")
            if not isinstance(overrides, dict):
                raise ValueError(f"Action override for index {idx} must be an object")
            actions[idx] = {**actions[idx], **overrides}

    # Validate actions for missing required fields
    for i, action in enumerate(actions):
        action_type = action.get("action_type")
        if action_type == "send_email" and not action.get("template_id"):
            raise ValueError(f"Action {i + 1} (send_email) missing email template")

    from app.services import workflow_service
    from app.db.enums import WorkflowTriggerType

    workflow_service._validate_trigger_config(
        WorkflowTriggerType(template.trigger_type),
        template.trigger_config or {},
    )
    for action in actions:
        workflow_service._validate_action_config(
            db, org_id, action, scope, user_id if scope == "personal" else None
        )

    effective_enabled = is_enabled

    # Create workflow copy
    workflow = AutomationWorkflow(
        organization_id=org_id,
        name=workflow_name,
        description=workflow_description or template.description,
        icon=template.icon,
        trigger_type=template.trigger_type,
        trigger_config=template.trigger_config,
        conditions=template.conditions,
        condition_logic=template.condition_logic,
        actions=actions,
        is_enabled=effective_enabled,
        scope=scope,
        owner_user_id=user_id if scope == "personal" else None,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(workflow)

    # Update template usage count
    template.usage_count += 1

    db.commit()
    db.refresh(workflow)
    return workflow


def delete_template(
    db: Session,
    org_id: UUID,
    template_id: UUID,
) -> bool:
    """Delete an org-specific template (cannot delete global templates)."""
    template = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.organization_id == org_id,
            WorkflowTemplate.is_global.is_(False),
        )
        .first()
    )

    if not template:
        return False

    db.delete(template)
    db.commit()
    return True


def seed_global_templates(db: Session) -> int:
    """Seed default global templates."""
    templates_data = [
        {
            "name": "Welcome New Lead",
            "description": "Send a welcome email when a new lead is created",
            "category": "onboarding",
            "icon": "mail",
            "trigger_type": "surrogate_created",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "send_email",
                    "template_id": None,
                }  # User selects template
            ],
        },
        {
            "name": "Follow Up After Inactivity",
            "description": "Create a task when a case has no activity for 7 days",
            "category": "follow-up",
            "icon": "clock",
            "trigger_type": "inactivity",
            "trigger_config": {"days": 7},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "create_task",
                    "title": "Follow up on inactive case",
                    "due_days": 1,
                }
            ],
        },
        {
            "name": "Owner Assignment Notification",
            "description": "Notify user when a case is assigned to them",
            "category": "notifications",
            "icon": "bell",
            "trigger_type": "surrogate_assigned",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "send_notification",
                    "title": "New case assigned",
                    "recipients": "owner",
                }
            ],
        },
        {
            "name": "Status Change Alert",
            "description": "Notify managers when a surrogate status changes",
            "category": "notifications",
            "icon": "activity",
            "trigger_type": "status_changed",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "send_notification",
                    "title": "Surrogate status updated",
                    "recipients": "all_admins",
                }
            ],
        },
        {
            "name": "Task Due Reminder",
            "description": "Send notification when a task is due today",
            "category": "compliance",
            "icon": "alert-circle",
            "trigger_type": "task_due",
            "trigger_config": {"hours_before": 24},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "send_notification",
                    "title": "Task due soon",
                    "recipients": "owner",
                }
            ],
        },
    ]

    created = 0
    template_names = [data["name"] for data in templates_data]
    existing_names = {
        row[0]
        for row in db.query(WorkflowTemplate.name)
        .filter(
            WorkflowTemplate.is_global.is_(True),
            WorkflowTemplate.name.in_(template_names),
        )
        .all()
    }
    for data in templates_data:
        if data["name"] in existing_names:
            continue
        template = WorkflowTemplate(
            is_global=True,
            organization_id=None,
            created_by_user_id=None,
            status="published",
            published_version=1,
            is_published_globally=True,
            published_at=datetime.now(timezone.utc),
            **data,
        )
        db.add(template)
        created += 1

    if created > 0:
        db.commit()

    return created
