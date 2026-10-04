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
    MATCH_CONFLICT = "match_conflict"
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
    FORM_SUBMISSION_ROUTING_REVIEW = "form_submission_routing_review"

    # Contact attempt reminders
    CONTACT_REMINDER = "contact_reminder"  # Reminder to follow up on case

    # Intelligent suggestion digest
    INTELLIGENT_SUGGESTION_DIGEST = "intelligent_suggestion_digest"

    # Interview notifications
    INTERVIEW_TRANSCRIPTION_COMPLETED = "interview_transcription_completed"

    # Attachment notifications
    ATTACHMENT_INFECTED = "attachment_infected"


class NotificationTier(str, Enum):
    """Inbox tier: action items count toward the bell badge; updates do not."""

    ACTION = "action"
    UPDATE = "update"


# Types that ask the recipient to do something. Every other type is an update.
ACTION_NOTIFICATION_TYPES: frozenset[str] = frozenset(
    {
        NotificationType.WORKFLOW_APPROVAL_REQUESTED.value,
        NotificationType.STATUS_CHANGE_REQUESTED.value,
        NotificationType.TASK_ASSIGNED.value,
        NotificationType.TASK_OVERDUE.value,
        NotificationType.SURROGATE_CLAIM_AVAILABLE.value,
        NotificationType.SURROGATE_ASSIGNED.value,
        NotificationType.APPOINTMENT_REQUESTED.value,
        NotificationType.MATCH_CONFLICT.value,
        NotificationType.CONTACT_REMINDER.value,
        NotificationType.ATTACHMENT_INFECTED.value,
    }
)


def notification_tier(notification_type: str) -> NotificationTier:
    if notification_type in ACTION_NOTIFICATION_TYPES:
        return NotificationTier.ACTION
    return NotificationTier.UPDATE
