"""Pydantic schemas for Automation Workflows."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.db.enums import (
    OwnerType,
    Role,
    WorkflowConditionOperator,
    WorkflowTriggerType,
)

# =============================================================================
# Field Registry (Whitelist for conditions and updates)
# =============================================================================

# Condition fields by the record a workflow's conditions read. Task, note, and document
# triggers read their linked surrogate or donor, so they use the subject's fields.
SURROGATE_CONDITION_FIELDS = frozenset(
    {
        "status_label",
        "stage_id",
        "source",
        "is_priority",
        "state",
        "created_at",
        "owner_type",
        "owner_id",
        "email",
        "phone",
        "full_name",
        "date_of_birth",
        "race",
        "marital_status",
        "has_child",
        "is_citizen_or_pr",
        "is_non_smoker",
        "has_surrogate_experience",
        "is_age_eligible",
        "journey_timing_preference",
        "height_ft",
        "weight_lb",
        "num_deliveries",
        "num_csections",
        "contact_status",
        "last_contacted_at",
        "assigned_at",
        "is_archived",
        "embryo_stage",
        "pregnancy_due_date",
        "actual_delivery_date",
        "meta_lead_id",
        "meta_ad_external_id",
        "meta_form_id",
    }
)

DONOR_ALLOWED_CONDITION_FIELDS = frozenset(
    {
        "status_label",
        "stage_id",
        "source",
        "state",
        "created_at",
        "owner_type",
        "owner_id",
        "email",
        "phone",
        "full_name",
        "education",
        "donor_type",
        "donor_number",
        "date_of_birth",
        "race",
        "marital_status",
        "height_ft",
        "weight_lb",
        "college",
        "nicotine",
        "cannabis",
        "infectious_disease",
        "previous_donation",
        "is_archived",
    }
)

FORM_SUBMISSION_CONDITION_FIELDS = frozenset(
    {"form_id", "status", "source_mode", "lead_kind", "match_status", "stage_id", "submitted_at"}
)

INTAKE_LEAD_CONDITION_FIELDS = frozenset(
    {
        "form_id",
        "status",
        "lead_kind",
        "source",
        "full_name",
        "email",
        "phone",
        "stage_id",
        "created_at",
    }
)

MATCH_CONDITION_FIELDS = frozenset({"status", "match_kind", "outcome", "created_at"})

APPOINTMENT_CONDITION_FIELDS = frozenset(
    {"status", "appointment_type_id", "meeting_mode", "scheduled_start", "created_at"}
)

CONDITION_FIELDS_BY_ENTITY: dict[str, frozenset[str]] = {
    "surrogate": SURROGATE_CONDITION_FIELDS,
    "form_submission": FORM_SUBMISSION_CONDITION_FIELDS,
    "intake_lead": INTAKE_LEAD_CONDITION_FIELDS,
    "match": MATCH_CONDITION_FIELDS,
    "appointment": APPOINTMENT_CONDITION_FIELDS,
}

ALLOWED_CONDITION_FIELDS = frozenset().union(
    DONOR_ALLOWED_CONDITION_FIELDS, *CONDITION_FIELDS_BY_ENTITY.values()
)

SURROGATE_ALLOWED_UPDATE_FIELDS = {
    "stage_id",
    "is_priority",
    "contact_status",
    "owner_type",
    "owner_id",
}

DONOR_ALLOWED_UPDATE_FIELDS = {
    "stage_id",
    "state",
    "education",
    "source",
    "owner_type",
    "owner_id",
}

ALLOWED_UPDATE_FIELDS = SURROGATE_ALLOWED_UPDATE_FIELDS | DONOR_ALLOWED_UPDATE_FIELDS

ALLOWED_EMAIL_VARIABLES = {
    "full_name",
    "email",
    "phone",
    "surrogate_number",
    "status_label",
    "state",
    "owner_name",
    "org_name",
    "donor_number",
    "donor_type",
    "education",
    "form_name",
    "submitted_at",
    "record_link",
}

WorkflowSubjectType = Literal[
    "surrogate",
    "form_submission",
    "intake_lead",
    "match",
    "appointment",
    "egg_donor",
    "sperm_donor",
]


def is_supported_simple_cron(cron: str) -> bool:
    """Return whether cron fits the exact subset the workflow runner supports."""
    parts = cron.split()
    if len(parts) != 5:
        return False

    minute, hour, day_of_month, month, day_of_week = parts
    if day_of_month != "*" or month != "*":
        return False

    def _valid_number(value: str, *, minimum: int, maximum: int) -> bool:
        if value == "*":
            return True
        try:
            parsed = int(value)
        except ValueError:
            return False
        return minimum <= parsed <= maximum

    if not _valid_number(minute, minimum=0, maximum=59):
        return False
    if not _valid_number(hour, minimum=0, maximum=23):
        return False
    if day_of_week == "*":
        return True
    if day_of_week.count("-") == 1:
        start_text, end_text = day_of_week.split("-", maxsplit=1)
        if not _valid_number(start_text, minimum=0, maximum=7):
            return False
        if not _valid_number(end_text, minimum=0, maximum=7):
            return False
        return int(start_text) <= int(end_text)
    return _valid_number(day_of_week, minimum=0, maximum=7)


# =============================================================================
# Condition Schemas
# =============================================================================


class Condition(BaseModel):
    """A single condition to evaluate."""

    field: str
    operator: WorkflowConditionOperator
    value: object = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v not in ALLOWED_CONDITION_FIELDS:
            raise ValueError(f"Field '{v}' is not allowed. Allowed: {ALLOWED_CONDITION_FIELDS}")
        return v


# =============================================================================
# Trigger Config Schemas
# =============================================================================


class StatusChangeTriggerConfig(BaseModel):
    """Config for status_changed trigger."""

    from_stage_id: UUID | None = None
    to_stage_id: UUID | None = None


class ScheduledTriggerConfig(BaseModel):
    """Config for scheduled trigger."""

    cron: str = Field(description="Cron expression, e.g., '0 9 * * 1' for Mon 9am")
    timezone: str = Field(default="America/Los_Angeles", description="IANA timezone")

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        if not is_supported_simple_cron(value):
            raise ValueError("Cron must use the supported schedule format: minute hour * * weekday")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value


class TaskDueTriggerConfig(BaseModel):
    """Config for task_due trigger."""

    hours_before: int = Field(ge=1, le=168, default=24)


class InactivityTriggerConfig(BaseModel):
    """Config for inactivity trigger."""

    days: int = Field(ge=1, le=90, default=7)


class SurrogateUpdatedTriggerConfig(BaseModel):
    """Config for surrogate_updated trigger."""

    fields: list[str] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: list[str]) -> list[str]:
        for field in v:
            if field not in ALLOWED_CONDITION_FIELDS:
                raise ValueError(f"Field '{field}' is not allowed")
        return v


class SurrogateAssignedTriggerConfig(BaseModel):
    """Config for surrogate_assigned trigger."""

    to_user_id: UUID | None = None  # Optional: only trigger for specific user


class FormSubmittedTriggerConfig(BaseModel):
    """Config for form_submitted trigger."""

    form_id: UUID | None = None
    lead_kind: Literal["surrogate", "egg_donor", "sperm_donor"] | None = None


class AppointmentTriggerConfig(BaseModel):
    """Config for appointment triggers.

    record_type picks the linked record that record actions run on. Appointment types are
    per host, so the type filter matches type names case-insensitively across hosts.
    """

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["surrogate", "egg_donor", "sperm_donor"] = "surrogate"
    appointment_type_names: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=50
    )


class AppointmentTimeTriggerConfig(AppointmentTriggerConfig):
    """Config for appointment_time: runs once per appointment time, hours from start or end."""

    when: Literal["before_start", "after_end"] = "before_start"
    hours: int = Field(24, ge=1, le=168)


class IntakeLeadCreatedTriggerConfig(BaseModel):
    """Config for intake_lead_created trigger."""

    form_id: UUID | None = None
    lead_type: Literal["surrogate", "egg_donor", "sperm_donor"] | None = None


# =============================================================================
# Action Config Schemas
# =============================================================================


class SendEmailActionConfig(BaseModel):
    """Config for send_email action."""

    action_type: Literal["send_email"] = "send_email"
    template_id: UUID
    recipients: (
        Literal[
            "surrogate",
            "donor",
            "subject",
            "owner",
            "creator",
            "all_admins",
            "queue",
            "role",
            "custom",
        ]
        | list[UUID]
    ) = "surrogate"
    recipient_queue_id: UUID | None = None
    recipient_role: Role | None = None
    recipient_emails: list[EmailStr] | None = Field(default=None, min_length=1, max_length=10)

    @model_validator(mode="after")
    def _require_recipient_target(self) -> SendEmailActionConfig:
        if self.recipients == "queue" and self.recipient_queue_id is None:
            raise ValueError("Queue recipients require a queue")
        if self.recipients == "role" and self.recipient_role is None:
            raise ValueError("Role recipients require a role")
        if self.recipients == "custom" and not self.recipient_emails:
            raise ValueError("Custom recipients require at least one email address")
        return self


# Recipients that are records' contacts rather than staff.
SUBJECT_EMAIL_RECIPIENTS = frozenset({"surrogate", "donor", "subject"})


def is_subject_email_recipient(recipients: object) -> bool:
    return isinstance(recipients, str) and recipients in SUBJECT_EMAIL_RECIPIENTS


class SendMessageActionConfig(BaseModel):
    """Config for consent-gated Twilio messaging outbox materialization."""

    action_type: Literal["send_message"] = "send_message"
    purpose: Literal["operational", "promotional"]
    message_template_version_id: UUID


class CreateTaskActionConfig(BaseModel):
    """Config for create_task action."""

    action_type: Literal["create_task"] = "create_task"
    title: str = Field(max_length=200)
    description: str | None = None
    due_days: int = Field(ge=0, le=365, default=1)
    assignee: Literal["owner", "creator", "admin"] | UUID = "owner"


class AssignSurrogateActionConfig(BaseModel):
    """Config for assign_surrogate action."""

    action_type: Literal["assign_surrogate"] = "assign_surrogate"
    owner_type: OwnerType
    owner_id: UUID


class AssignDonorActionConfig(BaseModel):
    """Config for assigning a donor within its organization."""

    action_type: Literal["assign_donor"] = "assign_donor"
    owner_type: OwnerType
    owner_id: UUID


class SendNotificationActionConfig(BaseModel):
    """Config for send_notification action."""

    action_type: Literal["send_notification"] = "send_notification"
    title: str = Field(max_length=100)
    body: str | None = None
    # "host" is the appointment's staff host; only appointment triggers offer it.
    recipients: Literal["owner", "creator", "all_admins", "host"] | list[UUID] = "owner"


class SendZapierConversionEventActionConfig(BaseModel):
    """Config for send_zapier_conversion_event action."""

    action_type: Literal["send_zapier_conversion_event"] = "send_zapier_conversion_event"


class UpdateFieldActionConfig(BaseModel):
    """Config for update_field action."""

    action_type: Literal["update_field"] = "update_field"
    field: str
    value: object

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v not in ALLOWED_UPDATE_FIELDS:
            raise ValueError(
                f"Field '{v}' is not allowed for update. Allowed: {ALLOWED_UPDATE_FIELDS}"
            )
        return v


class AddNoteActionConfig(BaseModel):
    """Config for add_note action."""

    action_type: Literal["add_note"] = "add_note"
    content: str = Field(min_length=1, max_length=4000)


class PromoteIntakeLeadActionConfig(BaseModel):
    """Config for promote_intake_lead action."""

    action_type: Literal["promote_intake_lead"] = "promote_intake_lead"
    source: str | None = None
    is_priority: bool = False
    assign_to_user: bool | None = None


class AutoMatchSubmissionActionConfig(BaseModel):
    """Config for auto_match_submission action."""

    action_type: Literal["auto_match_submission"] = "auto_match_submission"


class CreateIntakeLeadActionConfig(BaseModel):
    """Config for create_intake_lead action."""

    action_type: Literal["create_intake_lead"] = "create_intake_lead"
    source: str | None = None
    auto_promote: bool = False


# Union of all action configs
ActionConfig = (
    SendEmailActionConfig
    | SendMessageActionConfig
    | CreateTaskActionConfig
    | AssignSurrogateActionConfig
    | AssignDonorActionConfig
    | SendNotificationActionConfig
    | SendZapierConversionEventActionConfig
    | UpdateFieldActionConfig
    | AddNoteActionConfig
    | PromoteIntakeLeadActionConfig
    | AutoMatchSubmissionActionConfig
    | CreateIntakeLeadActionConfig
)


# =============================================================================
# Workflow CRUD Schemas
# =============================================================================


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""

    name: str = Field(max_length=100)
    description: str | None = None
    icon: str = Field(default="workflow", max_length=50)
    # Scope: 'org' for org-wide workflows, 'personal' for user-specific
    scope: Literal["org", "personal"] = "org"
    subject_type: WorkflowSubjectType = "surrogate"
    trigger_type: WorkflowTriggerType
    trigger_config: dict[str, object] = Field(default_factory=dict)
    conditions: list[Condition] = Field(default_factory=list)
    condition_logic: Literal["AND", "OR"] = "AND"
    actions: list[dict[str, object]] = Field(min_length=1)  # Validated per action_type
    is_enabled: bool = True
    # Rate limits (None = unlimited)
    rate_limit_per_hour: int | None = Field(default=None, ge=1, le=1000)
    rate_limit_per_entity_per_day: int | None = Field(default=None, ge=1, le=100)


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=50)
    trigger_type: WorkflowTriggerType | None = None
    trigger_config: dict | None = None
    conditions: list[Condition] | None = None
    condition_logic: Literal["AND", "OR"] | None = None
    actions: list[dict] | None = None
    is_enabled: bool | None = None
    # Rate limits (None = unlimited)
    rate_limit_per_hour: int | None = Field(default=None, ge=1, le=1000)
    rate_limit_per_entity_per_day: int | None = Field(default=None, ge=1, le=100)


class WorkflowRead(BaseModel):
    """Schema for reading a workflow."""

    id: UUID
    name: str
    description: str | None
    icon: str
    schema_version: int
    # Scope and owner
    scope: str  # 'org' or 'personal'
    owner_user_id: UUID | None = None
    owner_name: str | None = None  # Display name of owner (for personal workflows)
    proposed_by_user_id: UUID | None = None
    proposed_by_name: str | None = None
    subject_type: WorkflowSubjectType
    trigger_type: str
    trigger_config: dict
    conditions: list[dict]
    condition_logic: str
    actions: list[dict]
    is_enabled: bool
    run_count: int
    last_run_at: datetime | None
    last_error: str | None
    # Rate limits
    rate_limit_per_hour: int | None = None
    rate_limit_per_entity_per_day: int | None = None
    created_by_name: str | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    config_warnings: list[str] | None = None  # Warnings from template usage
    # Permission info for UI
    can_edit: bool = True
    can_publish: bool = False

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    """Schema for workflow list item."""

    id: UUID
    name: str
    description: str | None
    icon: str
    # Scope and owner
    scope: str  # 'org' or 'personal'
    owner_user_id: UUID | None = None
    owner_name: str | None = None  # Display name of owner (for personal workflows)
    proposed_by_user_id: UUID | None = None
    proposed_by_name: str | None = None
    subject_type: WorkflowSubjectType
    trigger_type: str
    is_enabled: bool
    run_count: int
    last_run_at: datetime | None
    last_error: str | None
    created_at: datetime
    # Permission info for UI
    can_edit: bool = True
    can_publish: bool = False

    model_config = {"from_attributes": True}


# =============================================================================
# Execution Schemas
# =============================================================================


class ExecutionRead(BaseModel):
    """Schema for reading a workflow execution."""

    id: UUID
    workflow_id: UUID
    event_id: UUID
    depth: int
    event_source: str
    entity_type: str
    entity_id: UUID
    subject_type: str | None = None
    subject_id: UUID | None = None
    entity_name: str | None = None
    entity_number: str | None = None
    trigger_event: dict
    matched_conditions: bool
    actions_executed: list[dict]
    status: str
    error_message: str | None
    duration_ms: int | None
    executed_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    """Response for listing executions."""

    items: list[ExecutionRead]
    total: int


# =============================================================================
# Stats and Options Schemas
# =============================================================================


class WorkflowStats(BaseModel):
    """Statistics for workflows dashboard."""

    total_workflows: int
    enabled_workflows: int
    total_executions_24h: int
    success_rate_24h: float
    by_trigger_type: dict[str, int]
    # Counts by scope
    org_workflows: int = 0
    personal_workflows: int = 0

    # Approval metrics
    pending_approvals: int = 0
    approvals_resolved_24h: int = 0
    approval_rate_24h: float = 0.0  # approved / total resolved
    denial_rate_24h: float = 0.0
    expiry_rate_24h: float = 0.0
    avg_approval_latency_hours: float | None = None


class WorkflowOptions(BaseModel):
    """Available options for workflow builder UI."""

    trigger_types: list[dict]  # {value, label, description}
    action_types: list[dict]
    action_types_by_trigger: dict[str, list[str]] | None = None
    trigger_entity_types: dict[str, str] | None = None
    condition_operators: list[dict]
    condition_fields: list[str]
    condition_fields_by_trigger: dict[str, list[str]]
    update_fields: list[str]
    email_variables: list[str]
    email_templates: list[dict]  # {id, name}
    message_templates: list[dict] = []  # {id, name, purpose, version}
    users: list[dict]  # {id, display_name}
    queues: list[dict]  # {id, name}
    statuses: list[dict]  # {id, value, label, is_active}
    forms: list[dict] = []  # {id, name, lead_kind, lead_kinds}
    appointment_type_names: list[str] = []


# =============================================================================
# User Preference Schemas
# =============================================================================


class UserWorkflowPreferenceRead(BaseModel):
    """Schema for reading user workflow preference."""

    id: UUID
    workflow_id: UUID
    workflow_name: str
    is_opted_out: bool

    model_config = {"from_attributes": True}


class UserWorkflowPreferenceUpdate(BaseModel):
    """Schema for updating user workflow preference."""

    is_opted_out: bool


# =============================================================================
# Test/Dry Run Schemas
# =============================================================================


class WorkflowTestRequest(BaseModel):
    """Request to test a workflow (dry run)."""

    entity_id: UUID
    entity_type: str | None = None


class WorkflowTestResponse(BaseModel):
    """Response from testing a workflow."""

    would_trigger: bool
    conditions_matched: bool
    conditions_evaluated: list[dict]  # {field, operator, value, result}
    actions_preview: list[dict]  # {action_type, description}
