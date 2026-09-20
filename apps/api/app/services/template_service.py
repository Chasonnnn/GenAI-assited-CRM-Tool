"""Template service for workflow template marketplace."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import FormStatus
from app.db.models import AutomationWorkflow, Form, WorkflowTemplate, WorkflowTemplateTarget

FORM_TRIGGER_TYPES = {"form_started", "form_submitted", "intake_lead_created"}

# Triggers that only run against donor records and therefore require an
# explicit donor subject (egg_donor or sperm_donor) on the template.
DONOR_ONLY_TRIGGER_TYPES = {
    "donor_created",
    "donor_stage_changed",
    "donor_assigned",
    "donor_updated",
}

TEMPLATE_REPAIR_REQUIRED = (
    "This donor workflow template needs repair: set an explicit egg_donor or "
    "sperm_donor subject before it can be used"
)


def resolve_template_subject_type(template: WorkflowTemplate) -> str:
    """Resolve the workflow subject a template produces.

    Legacy templates (NULL subject_type) fall back to the same trigger-based
    mapping workflow creation uses. Donor-trigger templates without an explicit
    subject are repair-required: the donor subtype must never be guessed.
    """
    if template.subject_type is not None:
        return template.subject_type
    if template.trigger_type in DONOR_ONLY_TRIGGER_TYPES:
        raise ValueError(TEMPLATE_REPAIR_REQUIRED)
    from app.services.workflow_service import LEGACY_TRIGGER_SUBJECT_TYPES

    return LEGACY_TRIGGER_SUBJECT_TYPES.get(template.trigger_type, "surrogate")


def _validate_new_template_subject(subject_type: str | None, trigger_type: str) -> str | None:
    """Validate and resolve the subject stored on a new template."""
    from app.db.enums import WorkflowTriggerType
    from app.services import workflow_service

    try:
        trigger = WorkflowTriggerType(trigger_type)
    except ValueError:
        raise ValueError(f"Unsupported trigger type: {trigger_type}")
    if subject_type is None:
        if trigger_type in DONOR_ONLY_TRIGGER_TYPES:
            raise ValueError(
                "Donor workflow templates must specify an explicit subject type "
                "(egg_donor or sperm_donor)"
            )
        return workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES.get(trigger_type, "surrogate")
    workflow_service._validate_subject_trigger(subject_type, trigger)
    return subject_type


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
    subject_type: str | None = None,
) -> WorkflowTemplate:
    """Create a new org-specific template."""
    resolved_subject = _validate_new_template_subject(subject_type, trigger_type)
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
        subject_type=resolved_subject,
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
        subject_type=workflow.subject_type,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        icon=workflow.icon,
    )


def resolve_template_trigger_config(
    db: Session,
    org_id: UUID,
    template: WorkflowTemplate,
    trigger_form_id: UUID | None = None,
) -> dict:
    """Resolve dynamic trigger references (for example, form name -> form id)."""
    trigger_config = dict(template.trigger_config or {})
    if trigger_form_id is not None:
        if template.trigger_type not in FORM_TRIGGER_TYPES:
            raise ValueError("trigger_form_id is only valid for form-trigger workflow templates")
        selected_form = (
            db.query(Form)
            .filter(
                Form.id == trigger_form_id,
                Form.organization_id == org_id,
                Form.status == FormStatus.PUBLISHED.value,
            )
            .first()
        )
        if not selected_form:
            raise ValueError("Selected published form not found in this organization")
        trigger_config["form_id"] = str(selected_form.id)
        trigger_config.pop("form_name", None)
    elif template.trigger_type in FORM_TRIGGER_TYPES:
        form_name = trigger_config.get("form_name")
        if isinstance(form_name, str):
            normalized_form_name = form_name.strip()
            if not normalized_form_name:
                trigger_config.pop("form_name", None)
            else:
                matched_forms = (
                    db.query(Form.id)
                    .filter(
                        Form.organization_id == org_id,
                        Form.status == FormStatus.PUBLISHED.value,
                        Form.name == normalized_form_name,
                    )
                    .limit(2)
                    .all()
                )
                if not matched_forms:
                    raise ValueError(
                        f"Published form '{normalized_form_name}' not found in this organization"
                    )
                if len(matched_forms) > 1:
                    raise ValueError(
                        f"Multiple published forms named '{normalized_form_name}' found; "
                        "set trigger form manually"
                    )
                trigger_config["form_id"] = str(matched_forms[0][0])
                trigger_config.pop("form_name", None)
    return trigger_config


def merge_action_overrides(
    template_actions: list | None,
    action_overrides: dict | None,
) -> list:
    """Apply per-index action overrides to a copy of the template's actions."""
    actions = [dict(action) for action in template_actions or []]
    if action_overrides:
        if not isinstance(action_overrides, dict):
            raise ValueError("action_overrides must be an object")
        for idx_str, overrides in action_overrides.items():
            try:
                idx = int(idx_str)
            except TypeError, ValueError:
                raise ValueError(f"Invalid action override index: {idx_str}")
            if idx < 0 or idx >= len(actions):
                raise ValueError(f"Action override index out of range: {idx}")
            if not isinstance(overrides, dict):
                raise ValueError(f"Action override for index {idx} must be an object")
            actions[idx] = {**actions[idx], **overrides}
    return actions


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
    trigger_form_id: UUID | None = None,
) -> AutomationWorkflow:
    """Create a workflow from a template through the canonical workflow boundary.

    Returns workflow.
    If actions have missing required fields, a validation error is raised.
    """
    template = get_template(db, template_id, org_id)
    if not template:
        raise ValueError("Template not found")

    trigger_config = resolve_template_trigger_config(db, org_id, template, trigger_form_id)
    actions = merge_action_overrides(template.actions, action_overrides)

    # Validate actions for missing required fields
    for i, action in enumerate(actions):
        action_type = action.get("action_type")
        if action_type == "send_email" and not action.get("template_id"):
            raise ValueError(f"Action {i + 1} (send_email) missing email template")

    subject_type = resolve_template_subject_type(template)

    from app.db.enums import WorkflowTriggerType
    from app.schemas.workflow import WorkflowCreate
    from app.services import workflow_service

    data = WorkflowCreate(
        name=workflow_name,
        description=workflow_description or template.description,
        icon=template.icon,
        scope=scope,
        subject_type=subject_type,
        trigger_type=WorkflowTriggerType(template.trigger_type),
        trigger_config=trigger_config,
        conditions=template.conditions or [],
        condition_logic=template.condition_logic,
        actions=actions,
        is_enabled=is_enabled,
    )

    # Committed together with the workflow by create_workflow's transaction.
    template.usage_count += 1

    return workflow_service.create_workflow(db, org_id, user_id, data)


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
            "subject_type": "surrogate",
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
            "subject_type": "surrogate",
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
            "subject_type": "surrogate",
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
            "subject_type": "surrogate",
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
            "subject_type": "surrogate",
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
            published_at=datetime.now(UTC),
            **data,
        )
        db.add(template)
        created += 1

    if created > 0:
        db.commit()

    return created
