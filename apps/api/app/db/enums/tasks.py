"""Task-related enums."""

from enum import Enum


class TaskType(str, Enum):
    """Types of tasks."""

    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    CONTACT = "contact"
    REVIEW = "review"
    MEDICATION = "medication"  # For medication schedules
    EXAM = "exam"  # For medical exams
    APPOINTMENT = "appointment"  # For appointments
    WORKFLOW_APPROVAL = "workflow_approval"  # Workflow action requiring approval
    OTHER = "other"


class TaskStatus(str, Enum):
    """
    Task status for workflow approvals and other tracked statuses.

    Standard tasks use is_completed boolean.
    Workflow approval tasks use this status enum for richer state tracking.
    """

    PENDING = "pending"  # Awaiting action
    IN_PROGRESS = "in_progress"  # Work started
    COMPLETED = "completed"  # Successfully completed
    DENIED = "denied"  # Explicitly denied (workflow approvals)
    EXPIRED = "expired"  # Timed out (workflow approvals)
