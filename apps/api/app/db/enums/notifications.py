"""Notification-related enums."""

from enum import Enum


class NotificationType(str, Enum):
    """Types of in-app notifications."""

    # Surrogate notifications
    SURROGATE_ASSIGNED = "surrogate_assigned"
    SURROGATE_STATUS_CHANGED = "surrogate_status_changed"
    SURROGATE_CLAIM_AVAILABLE = "surrogate_claim_available"

    # Task notifications
    TASK_ASSIGNED = "task_assigned"
    TASK_DUE_SOON = "task_due_soon"  # Due within 24h
    TASK_OVERDUE = "task_overdue"  # Past due date
    WORKFLOW_APPROVAL_REQUESTED = "workflow_approval_requested"
    WORKFLOW_APPROVAL_EXPIRED = "workflow_approval_expired"
    WORKFLOW_NOTIFICATION = "workflow_notification"
    STATUS_CHANGE_REQUESTED = "status_change_requested"
    STATUS_CHANGE_APPROVED = "status_change_approved"
    STATUS_CHANGE_REJECTED = "status_change_rejected"

    # Appointment notifications
    APPOINTMENT_REQUESTED = "appointment_requested"  # New appointment request
    APPOINTMENT_CONFIRMED = "appointment_confirmed"  # Appointment confirmed
    APPOINTMENT_CANCELLED = "appointment_cancelled"  # Appointment cancelled
    APPOINTMENT_REMINDER = "appointment_reminder"  # Reminder before appointment

    # Form notifications
    FORM_SUBMISSION_RECEIVED = "form_submission_received"  # Application submitted

    # Contact attempt reminders
    CONTACT_REMINDER = "contact_reminder"  # Reminder to follow up on case

    # Interview notifications
    INTERVIEW_TRANSCRIPTION_COMPLETED = "interview_transcription_completed"

    # Attachment notifications
    ATTACHMENT_INFECTED = "attachment_infected"
