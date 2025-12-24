"""
AI Workflow Generation Service.

Uses AI to generate workflow configurations from natural language descriptions.
Includes strict validation to ensure generated workflows are safe and valid.
"""

import json
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.enums import WorkflowTriggerType
from app.db.models import AISettings, AutomationWorkflow, EmailTemplate, User, Pipeline, PipelineStage
from app.services import ai_settings_service, workflow_service


logger = logging.getLogger(__name__)


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
    trigger_config: dict[str, Any] = {}
    conditions: list[dict[str, Any]] = []
    condition_logic: str = "AND"
    actions: list[dict[str, Any]] = []


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
    "case_created": "When a new case is created",
    "status_changed": "When a case status changes (use conditions for specific statuses)",
    "inactivity": "When a case has no activity for a period (trigger_config.days required)",
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
        "optional_fields": ["description", "due_days", "priority", "assignee_type", "assignee_id"],
    },
    "assign_case": {
        "description": "Assign the case to a user or queue",
        "required_fields": ["assignee_type", "assignee_id"],
    },
    "update_status": {
        "description": "Update the case status to a specific stage",
        "required_fields": ["stage_id"],
    },
    "add_note": {
        "description": "Add a note to the case",
        "required_fields": ["content"],
        "optional_fields": ["is_pinned"],
    },
    "send_notification": {
        "description": "Send an in-app notification",
        "required_fields": ["user_id", "title"],
        "optional_fields": ["body"],
    },
}

CONDITION_OPERATORS = [
    "equals", "not_equals", "contains", "not_contains",
    "greater_than", "less_than", "is_empty", "is_not_empty",
    "in_list", "not_in_list"
]


# =============================================================================
# Workflow Generation Prompt
# =============================================================================

WORKFLOW_GENERATION_PROMPT = """You are a workflow configuration assistant for a surrogacy agency CRM.

Your task is to generate a workflow configuration JSON based on the user's natural language description.

## Available Triggers
{triggers}

## Available Actions
{actions}

## Available Email Templates
{templates}

## Available Users (for assignment)
{users}

## Available Pipeline Stages (for status changes)
{stages}

## Condition Operators
equals, not_equals, contains, not_contains, greater_than, less_than, is_empty, is_not_empty, in_list, not_in_list

## Condition Fields
status, status_label, stage_id, state, source, is_priority, email, phone, full_name, days_inactive

## User Request
{user_input}

## Output Format
Respond with ONLY a valid JSON object (no markdown, no explanation) in this exact format:
{{
  "name": "Workflow name (concise, descriptive)",
  "description": "Brief description of what this workflow does",
  "icon": "zap",
  "trigger_type": "one of the available triggers",
  "trigger_config": {{}},
  "conditions": [
    {{"field": "field_name", "operator": "operator", "value": "value"}}
  ],
  "condition_logic": "AND",
  "actions": [
    {{"action_type": "action_name", "other_required_fields": "..."}}
  ]
}}

## Rules
1. Only use triggers from the available list
2. Only use actions from the available list
3. For send_email action, use a real template_id from the list
4. For assign_case actions, use a real user_id from the list or "owner" for case owner
5. For update_status actions, use a real stage_id from the list
6. Keep the workflow simple and focused on the user's request
7. Add conditions only when the user specifies filtering criteria
8. Use descriptive but concise names
"""


# =============================================================================
# Core Functions
# =============================================================================

def _get_context_for_prompt(db: Session, org_id: UUID) -> dict[str, str]:
    """Build context strings for the generation prompt."""
    # Get triggers
    triggers_text = "\n".join([f"- {k}: {v}" for k, v in AVAILABLE_TRIGGERS.items()])
    
    # Get actions
    actions_text = "\n".join([
        f"- {k}: {v['description']} (required: {v['required_fields']})"
        for k, v in AVAILABLE_ACTIONS.items()
    ])
    
    # Get email templates
    templates = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.is_archived == False
    ).limit(20).all()
    templates_text = "\n".join([f"- {t.id}: {t.name}" for t in templates]) or "No templates available"
    
    # Get users
    from app.db.models import Membership
    members = db.query(Membership, User).join(
        User, Membership.user_id == User.id
    ).filter(
        Membership.organization_id == org_id,
        User.is_active == True
    ).limit(20).all()
    users_text = "\n".join([
        f"- {m.user_id}: {u.display_name or u.email}"
        for m, u in members
    ]) or "No users available"
    
    # Get pipeline stages
    pipelines = db.query(Pipeline).filter(
        Pipeline.organization_id == org_id,
        Pipeline.is_active == True
    ).all()
    stages_text = ""
    for pipeline in pipelines:
        stages = db.query(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline.id
        ).order_by(PipelineStage.sort_order).all()
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
) -> WorkflowGenerationResponse:
    """
    Generate a workflow configuration from natural language.
    
    Returns the generated workflow for user review before saving.
    """
    from app.services.ai_provider import ChatMessage, get_provider
    
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
    
    # Get API key
    api_key = ai_settings_service.get_decrypted_key(settings)
    if not api_key:
        return WorkflowGenerationResponse(
            success=False,
            explanation="AI API key not configured",
        )
    
    # Build prompt context
    context = _get_context_for_prompt(db, org_id)
    prompt = WORKFLOW_GENERATION_PROMPT.format(
        triggers=context["triggers"],
        actions=context["actions"],
        templates=context["templates"],
        users=context["users"],
        stages=context["stages"],
        user_input=description,
    )
    
    # Call AI provider
    try:
        provider = get_provider(settings.provider, api_key, settings.model)
        
        import asyncio
        response = asyncio.get_event_loop().run_until_complete(
            provider.chat([
                ChatMessage(
                    role="system",
                    content="You are a workflow configuration generator. Always respond with ONLY valid JSON, no markdown or explanation."
                ),
                ChatMessage(role="user", content=prompt),
            ], temperature=0.3)
        )
        
        # Parse response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        workflow_data = json.loads(content)
        
        # Validate the generated workflow
        validation_result = validate_workflow(
            db, org_id,
            GeneratedWorkflow(**workflow_data)
        )
        
        if not validation_result.valid:
            return WorkflowGenerationResponse(
                success=False,
                workflow=GeneratedWorkflow(**workflow_data),
                explanation="Generated workflow has validation errors",
                validation_errors=validation_result.errors,
                warnings=validation_result.warnings,
            )
        
        return WorkflowGenerationResponse(
            success=True,
            workflow=GeneratedWorkflow(**workflow_data),
            explanation="Workflow generated successfully. Please review before saving.",
            warnings=validation_result.warnings,
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return WorkflowGenerationResponse(
            success=False,
            explanation=f"Failed to parse AI response as JSON: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        return WorkflowGenerationResponse(
            success=False,
            explanation=f"Error generating workflow: {str(e)}",
        )


def validate_workflow(
    db: Session,
    org_id: UUID,
    workflow: GeneratedWorkflow,
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
        errors.append(f"Invalid trigger type: {workflow.trigger_type}. Must be one of: {', '.join(valid_triggers)}")
    
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
    
    # Validate conditions
    for i, cond in enumerate(workflow.conditions):
        if "field" not in cond:
            errors.append(f"Condition {i+1} missing 'field'")
        if "operator" not in cond:
            errors.append(f"Condition {i+1} missing 'operator'")
        elif cond["operator"] not in CONDITION_OPERATORS:
            warnings.append(f"Condition {i+1} has unknown operator: {cond['operator']}")
    
    # Validate actions
    if not workflow.actions:
        errors.append("Workflow must have at least one action")
    
    for i, action in enumerate(workflow.actions):
        action_type = action.get("action_type")
        if not action_type:
            errors.append(f"Action {i+1} missing 'action_type'")
            continue
        
        if action_type not in AVAILABLE_ACTIONS:
            errors.append(f"Invalid action type: {action_type}")
            continue
        
        action_def = AVAILABLE_ACTIONS[action_type]
        
        # Check required fields
        for field in action_def["required_fields"]:
            if field not in action:
                errors.append(f"Action {i+1} ({action_type}) missing required field: {field}")
        
        # Validate template_id exists
        if action_type == "send_email" and "template_id" in action:
            template = db.query(EmailTemplate).filter(
                EmailTemplate.id == action["template_id"],
                EmailTemplate.organization_id == org_id
            ).first()
            if not template:
                errors.append(f"Action {i+1}: Template ID does not exist: {action['template_id']}")
        
        # Validate stage_id exists
        if action_type == "update_status" and "stage_id" in action:
            from app.db.models import PipelineStage, Pipeline
            stage = db.query(PipelineStage).join(
                Pipeline, PipelineStage.pipeline_id == Pipeline.id
            ).filter(
                PipelineStage.id == action["stage_id"],
                Pipeline.organization_id == org_id
            ).first()
            if not stage:
                errors.append(f"Action {i+1}: Stage ID does not exist: {action['stage_id']}")
        
        # Validate assignee_id for notifications
        if action_type == "send_notification" and "user_id" in action:
            from app.db.models import Membership
            member = db.query(Membership).filter(
                Membership.user_id == action["user_id"],
                Membership.organization_id == org_id
            ).first()
            if not member:
                errors.append(f"Action {i+1}: User ID does not exist: {action['user_id']}")
    
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
) -> AutomationWorkflow:
    """
    Save an approved workflow to the database.
    
    The workflow should have been validated and approved by the user.
    """
    # Final validation before save
    validation = validate_workflow(db, org_id, workflow)
    if not validation.valid:
        raise ValueError(f"Workflow validation failed: {', '.join(validation.errors)}")
    
    # Create workflow via service
    from app.schemas.workflow import WorkflowCreate
    
    create_data = WorkflowCreate(
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=False,  # Always create disabled for safety
    )
    
    return workflow_service.create_workflow(db, org_id, user_id, create_data)
