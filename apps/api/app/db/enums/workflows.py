"""Workflow-related enums."""

from enum import Enum


class WorkflowTriggerType(str, Enum):
    """Events that can trigger a workflow."""

    SURROGATE_CREATED = "surrogate_created"
    STATUS_CHANGED = "status_changed"
    SURROGATE_ASSIGNED = "surrogate_assigned"
    SURROGATE_UPDATED = "surrogate_updated"
    TASK_DUE = "task_due"
    TASK_OVERDUE = "task_overdue"
    SCHEDULED = "scheduled"
    INACTIVITY = "inactivity"
    # Match triggers
    MATCH_PROPOSED = "match_proposed"
    MATCH_ACCEPTED = "match_accepted"
    MATCH_REJECTED = "match_rejected"
    # Document trigger
    DOCUMENT_UPLOADED = "document_uploaded"  # Fires after scan_status = 'clean'
    # Note trigger (high-volume, requires condition to activate)
    NOTE_ADDED = "note_added"
    # Appointment triggers
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    APPOINTMENT_COMPLETED = "appointment_completed"


class RecurrenceMode(str, Enum):
    """Recurrence mode for workflows."""

    ONE_TIME = "one_time"  # Fire once per entity per trigger event
    RECURRING = "recurring"  # Fire on schedule until resolved/stopped


class WorkflowActionType(str, Enum):
    """Actions a workflow can execute."""

    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    ASSIGN_SURROGATE = "assign_surrogate"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_FIELD = "update_field"
    ADD_NOTE = "add_note"


class WorkflowConditionOperator(str, Enum):
    """Operators for workflow conditions."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN = "in"
    NOT_IN = "not_in"


class WorkflowExecutionStatus(str, Enum):
    """Execution result status."""

    SUCCESS = "success"
    PARTIAL = "partial"  # some actions succeeded
    FAILED = "failed"
    SKIPPED = "skipped"  # conditions not met
    PAUSED = "paused"  # waiting for human approval
    CANCELED = "canceled"  # user denied approval or owner changed
    EXPIRED = "expired"  # approval timed out


class WorkflowEventSource(str, Enum):
    """Source that triggered a workflow event."""

    USER = "user"
    SYSTEM = "system"
    WORKFLOW = "workflow"
