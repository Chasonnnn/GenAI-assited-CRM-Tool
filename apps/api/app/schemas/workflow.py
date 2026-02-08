"""Pydantic schemas for Automation Workflows."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.enums import (
    WorkflowTriggerType,
    WorkflowConditionOperator,
    OwnerType,
)


# =============================================================================
# Field Registry (Whitelist for conditions and updates)
# =============================================================================

ALLOWED_CONDITION_FIELDS = {
    # Basic fields
    "status_label",
    "stage_id",
    "source",
    "is_priority",
    "state",
    "created_at",
    # Owner fields
    "owner_type",
    "owner_id",
    # Contact fields
    "email",
    "phone",
    "full_name",
    # Demographics
    "age",
    "bmi",
    "date_of_birth",
    "race",
    # Eligibility flags
    "has_child",
    "is_citizen_or_pr",
    "is_non_smoker",
    "has_surrogate_experience",
    "is_age_eligible",
    # Physical measurements
    "height_ft",
    "weight_lb",
    "num_deliveries",
    "num_csections",
    # Meta tracking
    "meta_lead_id",
    "meta_ad_external_id",
    "meta_form_id",
}

ALLOWED_UPDATE_FIELDS = {
    "stage_id",
    "is_priority",
    "owner_type",
    "owner_id",
}

ALLOWED_EMAIL_VARIABLES = {
    "full_name",
    "email",
    "phone",
    "surrogate_number",
    "status_label",
    "state",
    "owner_name",
    "org_name",
}


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
    to_stage_id: UUID


class ScheduledTriggerConfig(BaseModel):
    """Config for scheduled trigger."""

    cron: str = Field(description="Cron expression, e.g., '0 9 * * 1' for Mon 9am")
    timezone: str = Field(default="America/Los_Angeles", description="IANA timezone")


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


class FormStartedTriggerConfig(BaseModel):
    """Config for form_started trigger."""

    form_id: UUID


class FormSubmittedTriggerConfig(BaseModel):
    """Config for form_submitted trigger."""

    form_id: UUID


# =============================================================================
# Action Config Schemas
# =============================================================================


class SendEmailActionConfig(BaseModel):
    """Config for send_email action."""

    action_type: Literal["send_email"] = "send_email"
    template_id: UUID
    recipients: Literal["surrogate", "owner", "creator", "all_admins"] | list[UUID] = "surrogate"


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


class SendNotificationActionConfig(BaseModel):
    """Config for send_notification action."""

    action_type: Literal["send_notification"] = "send_notification"
    title: str = Field(max_length=100)
    body: str | None = None
    recipients: Literal["owner", "creator", "all_admins"] | list[UUID] = "owner"


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


# Union of all action configs
ActionConfig = (
    SendEmailActionConfig
    | CreateTaskActionConfig
    | AssignSurrogateActionConfig
    | SendNotificationActionConfig
    | UpdateFieldActionConfig
    | AddNoteActionConfig
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
    trigger_type: str
    is_enabled: bool
    run_count: int
    last_run_at: datetime | None
    last_error: str | None
    created_at: datetime
    # Permission info for UI
    can_edit: bool = True

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
    update_fields: list[str]
    email_variables: list[str]
    email_templates: list[dict]  # {id, name}
    users: list[dict]  # {id, display_name}
    queues: list[dict]  # {id, name}
    statuses: list[dict]  # {id, value, label, is_active}
    forms: list[dict] = []  # {id, name}


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
