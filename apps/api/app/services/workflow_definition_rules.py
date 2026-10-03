"""Workflow definition rules that do not require database or permission context."""

from app.db.enums import WorkflowTriggerType
from app.schemas.workflow import (
    AppointmentTimeTriggerConfig,
    AppointmentTriggerConfig,
    FormSubmittedTriggerConfig,
    InactivityTriggerConfig,
    IntakeLeadCreatedTriggerConfig,
    ScheduledTriggerConfig,
    StatusChangeTriggerConfig,
    SurrogateUpdatedTriggerConfig,
    TaskDueTriggerConfig,
)

RETIRED_TRIGGER_TYPES = frozenset({WorkflowTriggerType.FORM_STARTED})
APPOINTMENT_TRIGGER_TYPES = frozenset(
    {
        WorkflowTriggerType.APPOINTMENT_REQUESTED,
        WorkflowTriggerType.APPOINTMENT_SCHEDULED,
        WorkflowTriggerType.APPOINTMENT_RESCHEDULED,
        WorkflowTriggerType.APPOINTMENT_COMPLETED,
        WorkflowTriggerType.APPOINTMENT_CANCELLED,
        WorkflowTriggerType.APPOINTMENT_NO_SHOW,
        WorkflowTriggerType.APPOINTMENT_EXPIRED,
        WorkflowTriggerType.APPOINTMENT_TIME,
    }
)


def appointment_timing_key(trigger_config: dict | None) -> str:
    """'<when>:<hours>' for an appointment_time config, with the schema defaults."""
    config = trigger_config or {}
    return f"{config.get('when') or 'before_start'}:{config.get('hours') or 24}"


def appointment_record_type(trigger_config: dict | None) -> str:
    """Record type an appointment workflow's record actions run on."""
    record_type = (trigger_config or {}).get("record_type")
    return record_type if record_type in {"egg_donor", "sperm_donor"} else "surrogate"


def validate_trigger_config(trigger_type: WorkflowTriggerType, config: dict) -> None:
    """Validate trigger config matches the trigger type schema."""
    if trigger_type in RETIRED_TRIGGER_TYPES:
        raise ValueError(f"Trigger {trigger_type.value} is no longer available")
    validators = {
        WorkflowTriggerType.STATUS_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.DONOR_STAGE_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.SCHEDULED: ScheduledTriggerConfig,
        WorkflowTriggerType.TASK_DUE: TaskDueTriggerConfig,
        WorkflowTriggerType.INACTIVITY: InactivityTriggerConfig,
        WorkflowTriggerType.SURROGATE_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.DONOR_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMITTED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMISSION_APPROVED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMISSION_REJECTED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.INTAKE_LEAD_CREATED: IntakeLeadCreatedTriggerConfig,
        **dict.fromkeys(APPOINTMENT_TRIGGER_TYPES, AppointmentTriggerConfig),
        WorkflowTriggerType.APPOINTMENT_TIME: AppointmentTimeTriggerConfig,
    }

    validator = validators.get(trigger_type)
    if validator:
        validator.model_validate(config)
