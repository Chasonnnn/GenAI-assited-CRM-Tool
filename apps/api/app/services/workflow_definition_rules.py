"""Workflow definition rules that do not require database or permission context."""

from app.db.enums import WorkflowTriggerType
from app.schemas.workflow import (
    FormStartedTriggerConfig,
    FormSubmittedTriggerConfig,
    InactivityTriggerConfig,
    IntakeLeadCreatedTriggerConfig,
    ScheduledTriggerConfig,
    StatusChangeTriggerConfig,
    SurrogateUpdatedTriggerConfig,
    TaskDueTriggerConfig,
)


def normalize_actions_for_trigger(
    trigger_type: WorkflowTriggerType,
    actions: list[dict],
) -> list[dict]:
    """Normalize workflow actions for trigger-specific rules."""
    normalized = [dict(action) for action in actions]
    if trigger_type != WorkflowTriggerType.FORM_SUBMITTED:
        return normalized

    auto_match_indices = [
        idx
        for idx, action in enumerate(normalized)
        if action.get("action_type") == "auto_match_submission"
    ]
    create_lead_indices = [
        idx
        for idx, action in enumerate(normalized)
        if action.get("action_type") == "create_intake_lead"
    ]
    if auto_match_indices and create_lead_indices:
        first_match_idx = auto_match_indices[0]
        first_create_idx = create_lead_indices[0]
        if first_match_idx > first_create_idx:
            raise ValueError(
                "For form_submitted workflows, auto_match_submission must be placed before create_intake_lead"
            )

    return normalized


def validate_trigger_config(trigger_type: WorkflowTriggerType, config: dict) -> None:
    """Validate trigger config matches the trigger type schema."""
    validators = {
        WorkflowTriggerType.STATUS_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.DONOR_STAGE_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.SCHEDULED: ScheduledTriggerConfig,
        WorkflowTriggerType.TASK_DUE: TaskDueTriggerConfig,
        WorkflowTriggerType.INACTIVITY: InactivityTriggerConfig,
        WorkflowTriggerType.SURROGATE_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.DONOR_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.FORM_STARTED: FormStartedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMITTED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.INTAKE_LEAD_CREATED: IntakeLeadCreatedTriggerConfig,
    }

    validator = validators.get(trigger_type)
    if validator:
        validator.model_validate(config)
