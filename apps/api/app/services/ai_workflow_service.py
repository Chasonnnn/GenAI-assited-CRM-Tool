"""
AI Workflow Generation Service.

Uses AI to generate workflow configurations from natural language descriptions.
Includes strict validation to ensure generated workflows are safe and valid.
"""

import json
import logging
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import (
    AutomationWorkflow,
    EmailTemplate,
    User,
    Pipeline,
    PipelineStage,
)
from app.services import ai_settings_service, workflow_service
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_response_validation import parse_json_object, validate_model
from app.schemas.workflow import ALLOWED_CONDITION_FIELDS


logger = logging.getLogger(__name__)


def _create_workflow_generation_alert(
    db: Session, org_id: UUID, error_msg: str, error_class: str
) -> None:
    """Create system alert for workflow generation failure."""
    try:
        from app.services import alert_service
        from app.db.enums import AlertType, AlertSeverity

        alert_service.create_or_update_alert(
            db=db,
            org_id=org_id,
            alert_type=AlertType.AI_PROVIDER_ERROR,
            severity=AlertSeverity.ERROR,
            title="AI workflow generation failed",
            message=error_msg[:500],
            integration_key="ai_workflow",
            error_class=error_class,
        )
    except Exception as alert_err:
        logger.warning(f"Failed to create workflow generation alert: {alert_err}")


# =============================================================================
# Request/Response Models
# =============================================================================


class WorkflowGenerationRequest(BaseModel):
    """Request to generate a workflow from natural language."""

    description: str = Field(..., min_length=10, max_length=2000)


class GeneratedWorkflow(BaseModel):
    """AI-generated workflow configuration."""

    name: str
    description: str | None = None
    icon: str = "zap"
    trigger_type: str
    trigger_config: dict[str, object] = Field(default_factory=dict)
    conditions: list[dict[str, object]] = Field(default_factory=list)
    condition_logic: str = "AND"
    actions: list[dict[str, object]] = Field(default_factory=list)


class WorkflowGenerationResponse(BaseModel):
    """Response from workflow generation."""

    success: bool
    workflow: GeneratedWorkflow | None = None
    explanation: str | None = None
    validation_errors: list[str] = []
    warnings: list[str] = []


class WorkflowValidationRequest(BaseModel):
    """Request to validate a workflow configuration."""

    workflow: GeneratedWorkflow


class WorkflowValidationResponse(BaseModel):
    """Response from workflow validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class WorkflowSaveRequest(BaseModel):
    """Request to save an approved workflow."""

    workflow: GeneratedWorkflow


# =============================================================================
# Available Triggers and Actions (for prompt context)
# =============================================================================

AVAILABLE_TRIGGERS = {
    "surrogate_created": "When a new surrogate is created",
    "status_changed": "When a surrogate status changes (use conditions for specific statuses)",
    "inactivity": "When a surrogate has no activity for a period (trigger_config.days required)",
    "scheduled": "On a schedule (trigger_config.cron required)",
    "match_proposed": "When a match is proposed",
    "match_accepted": "When a match is accepted",
    "match_rejected": "When a match is rejected",
    "document_uploaded": "When a document is uploaded and scanned",
    "note_added": "When a note is added",
    "appointment_scheduled": "When an appointment is scheduled",
    "appointment_completed": "When an appointment is completed",
}

AVAILABLE_ACTIONS = {
    "send_email": {
        "description": "Send an email using a template",
        "required_fields": ["template_id"],
        "optional_fields": ["to_override"],
    },
    "create_task": {
        "description": "Create a task",
        "required_fields": ["title"],
        "optional_fields": ["description", "due_days", "priority", "assignee"],
    },
    "assign_surrogate": {
        "description": "Assign the surrogate to a user or queue",
        "required_fields": ["owner_type", "owner_id"],
    },
    "update_field": {
        "description": "Update a surrogate field",
        "required_fields": ["field", "value"],
    },
    "add_note": {
        "description": "Add a note to the surrogate",
        "required_fields": ["content"],
        "optional_fields": ["is_pinned"],
    },
    "send_notification": {
        "description": "Send an in-app notification",
        "required_fields": ["title"],
        "optional_fields": ["body", "recipients", "user_id"],
    },
}

CONDITION_OPERATORS = [
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "greater_than",
    "less_than",
    "is_empty",
    "is_not_empty",
    "in",
    "not_in",
]


# =============================================================================
# Workflow Generation Prompt
# =============================================================================

# =============================================================================
# Core Functions
# =============================================================================


def _get_context_for_prompt(
    db: Session,
    org_id: UUID,
    *,
    anonymize_pii: bool = False,
    scope: str = "personal",
    owner_user_id: UUID | None = None,
) -> dict[str, str]:
    """Build context strings for the generation prompt."""
    # Get triggers
    triggers_text = "\n".join([f"- {k}: {v}" for k, v in AVAILABLE_TRIGGERS.items()])

    # Get actions
    actions_text = "\n".join(
        [
            f"- {k}: {v['description']} (required: {v['required_fields']})"
            for k, v in AVAILABLE_ACTIONS.items()
        ]
    )

    # Get email templates
    template_query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.is_active.is_(True),
    )
    from app.services import system_email_template_service

    platform_system_keys = set(system_email_template_service.DEFAULT_SYSTEM_TEMPLATES.keys())
    if platform_system_keys:
        template_query = template_query.filter(
            or_(
                EmailTemplate.system_key.is_(None),
                EmailTemplate.system_key.notin_(platform_system_keys),
            )
        )
    if scope == "org":
        template_query = template_query.filter(EmailTemplate.scope == "org")
    else:
        template_query = template_query.filter(
            or_(
                EmailTemplate.scope == "org",
                and_(
                    EmailTemplate.scope == "personal",
                    EmailTemplate.owner_user_id == owner_user_id,
                ),
            )
        )
    templates = template_query.limit(20).all()
    templates_text = (
        "\n".join([f"- {t.id}: {t.name}" for t in templates]) or "No templates available"
    )

    # Get users
    from app.db.models import Membership

    members = (
        db.query(Membership, User)
        .join(User, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .limit(20)
        .all()
    )
    users_lines = []
    for idx, (membership, user) in enumerate(members, start=1):
        label = f"User {idx}" if anonymize_pii else (user.display_name or user.email)
        users_lines.append(f"- {membership.user_id}: {label}")
    users_text = "\n".join(users_lines) or "No users available"

    # Get pipeline stages
    pipelines = db.query(Pipeline).filter(Pipeline.organization_id == org_id).all()
    stages_text = ""
    for pipeline in pipelines:
        stages = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == pipeline.id,
                PipelineStage.is_active.is_(True),
            )
            .order_by(PipelineStage.order)
            .all()
        )
        for stage in stages:
            stages_text += f"- {stage.id}: {stage.label} ({pipeline.name})\n"
    stages_text = stages_text.strip() or "No stages available"

    return {
        "triggers": triggers_text,
        "actions": actions_text,
        "templates": templates_text,
        "users": users_text,
        "stages": stages_text,
    }


def generate_workflow(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    description: str,
    scope: str = "personal",
) -> WorkflowGenerationResponse:
    """
    Generate a workflow configuration from natural language.

    Returns the generated workflow for user review before saving.
    """
    from app.services.ai_provider import ChatMessage

    # Check AI is enabled
    settings = ai_settings_service.get_ai_settings(db, org_id)
    if not settings or not settings.is_enabled:
        return WorkflowGenerationResponse(
            success=False,
            explanation="AI is not enabled for this organization",
        )

    if ai_settings_service.is_consent_required(settings):
        return WorkflowGenerationResponse(
            success=False,
            explanation="AI consent not accepted",
        )

    provider = ai_settings_service.get_ai_provider_for_settings(settings, org_id, user_id=user_id)
    if not provider:
        message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        return WorkflowGenerationResponse(
            success=False,
            explanation=message,
        )

    # Build prompt context
    context = _get_context_for_prompt(
        db,
        org_id,
        anonymize_pii=settings.anonymize_pii,
        scope=scope,
        owner_user_id=user_id,
    )
    prompt_template = get_prompt("workflow_generation")
    prompt = prompt_template.render_user(
        triggers=context["triggers"],
        actions=context["actions"],
        templates=context["templates"],
        users=context["users"],
        stages=context["stages"],
        user_input=description,
    )

    # Call AI provider
    try:
        from app.core.async_utils import run_async

        async def _run_chat():
            return await provider.chat(
                [
                    ChatMessage(role="system", content=prompt_template.system),
                    ChatMessage(role="user", content=prompt),
                ],
                temperature=0.3,
            )

        response = run_async(_run_chat())

        # Parse response
        workflow_data = parse_json_object(response.content)
        workflow_model = validate_model(GeneratedWorkflow, workflow_data)
        if not workflow_model:
            raise json.JSONDecodeError("Invalid workflow JSON", response.content, 0)

        # Validate the generated workflow
        validation_result = validate_workflow(
            db,
            org_id,
            workflow_model,
            scope=scope,
            owner_user_id=user_id if scope == "personal" else None,
        )

        if not validation_result.valid:
            return WorkflowGenerationResponse(
                success=False,
                workflow=workflow_model,
                explanation="Generated workflow has validation errors",
                validation_errors=validation_result.errors,
                warnings=validation_result.warnings,
            )

        return WorkflowGenerationResponse(
            success=True,
            workflow=workflow_model,
            explanation="Workflow generated successfully. Please review before saving.",
            warnings=validation_result.warnings,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        _create_workflow_generation_alert(db, org_id, str(e), "JSONDecodeError")
        return WorkflowGenerationResponse(
            success=False,
            explanation=f"Failed to parse AI response as JSON: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        _create_workflow_generation_alert(db, org_id, str(e), type(e).__name__)
        return WorkflowGenerationResponse(
            success=False,
            explanation=f"Error generating workflow: {str(e)}",
        )


def validate_workflow(
    db: Session,
    org_id: UUID,
    workflow: GeneratedWorkflow,
    *,
    scope: str | None = None,
    owner_user_id: UUID | None = None,
) -> WorkflowValidationResponse:
    """
    Validate a workflow configuration.

    Checks:
    - Trigger type is valid
    - Actions are valid and have required fields
    - Template IDs exist
    - User IDs exist
    - Stage IDs exist
    """
    errors = []
    warnings = []

    # Validate trigger type
    valid_triggers = set(AVAILABLE_TRIGGERS.keys())
    if workflow.trigger_type not in valid_triggers:
        errors.append(
            f"Invalid trigger type: {workflow.trigger_type}. Must be one of: {', '.join(valid_triggers)}"
        )

    # Validate inactivity trigger has days
    if workflow.trigger_type == "inactivity":
        if not workflow.trigger_config.get("days"):
            errors.append("Inactivity trigger requires 'days' in trigger_config")

    # Validate scheduled trigger has cron
    if workflow.trigger_type == "scheduled":
        if not workflow.trigger_config.get("cron"):
            errors.append("Scheduled trigger requires 'cron' in trigger_config")

    # Validate condition_logic
    if workflow.condition_logic not in ("AND", "OR"):
        errors.append(f"Invalid condition_logic: {workflow.condition_logic}. Must be AND or OR")

    def _normalize_operator(operator: str) -> str:
        if operator == "in_list":
            return "in"
        if operator == "not_in_list":
            return "not_in"
        return operator

    # Validate conditions
    for i, cond in enumerate(workflow.conditions):
        if "field" not in cond:
            errors.append(f"Condition {i + 1} missing 'field'")
        elif cond["field"] not in ALLOWED_CONDITION_FIELDS:
            errors.append(f"Condition {i + 1} has invalid field: {cond['field']}")
        if "operator" not in cond:
            errors.append(f"Condition {i + 1} missing 'operator'")
        else:
            cond["operator"] = _normalize_operator(str(cond["operator"]))
            if cond["operator"] not in CONDITION_OPERATORS:
                warnings.append(f"Condition {i + 1} has unknown operator: {cond['operator']}")

    # Validate actions
    if not workflow.actions:
        errors.append("Workflow must have at least one action")

    for i, action in enumerate(workflow.actions):
        action_type = action.get("action_type")
        if not action_type:
            errors.append(f"Action {i + 1} missing 'action_type'")
            continue

        if action_type not in AVAILABLE_ACTIONS:
            errors.append(f"Invalid action type: {action_type}")
            continue

        action_def = AVAILABLE_ACTIONS[action_type]

        # Check required fields
        for field in action_def["required_fields"]:
            if field not in action:
                errors.append(f"Action {i + 1} ({action_type}) missing required field: {field}")

        # Validate against workflow service to enforce org/user scoping
        from app.services import workflow_service

        try:
            workflow_service._validate_action_config(
                db,
                org_id,
                action,
                scope,
                owner_user_id if scope == "personal" else None,
            )
        except Exception as exc:  # noqa: BLE001 - return validation error details to caller
            errors.append(f"Action {i + 1}: {exc}")

    return WorkflowValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def save_workflow(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    workflow: GeneratedWorkflow,
    scope: str = "personal",
) -> AutomationWorkflow:
    """
    Save an approved workflow to the database.

    The workflow should have been validated and approved by the user.
    """
    # Final validation before save
    validation = validate_workflow(
        db,
        org_id,
        workflow,
        scope=scope,
        owner_user_id=user_id if scope == "personal" else None,
    )
    if not validation.valid:
        raise ValueError(f"Workflow validation failed: {', '.join(validation.errors)}")

    # Create workflow via service
    from app.schemas.workflow import WorkflowCreate

    create_data = WorkflowCreate(
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        scope=scope,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=False,  # Always create disabled for safety
    )

    return workflow_service.create_workflow(db, org_id, user_id, create_data)
