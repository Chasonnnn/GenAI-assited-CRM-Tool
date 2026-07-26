"""Email-related enums."""

from enum import Enum


class EmailStatus(str, Enum):
    """Status of outbound emails."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class SuppressionReason(str, Enum):
    """Reason for email suppression."""

    OPT_OUT = "opt_out"
    BOUNCED = "bounced"
    ARCHIVED = "archived"
    COMPLAINT = "complaint"


class EmailProvider(str, Enum):
    """Outbound provider recorded at message creation time."""

    RESEND = "resend"
    GMAIL = "gmail"


class EmailProviderScope(str, Enum):
    """Credential ownership used for an outbound message."""

    PLATFORM = "platform"
    ORGANIZATION = "organization"
    USER = "user"


class EmailSuppressionPolicy(str, Enum):
    """Which suppression evidence a reviewed send may bypass."""

    ENFORCE_ALL = "enforce_all"
    ALLOW_OPT_OUT = "allow_opt_out"


class EmailDeliveryStatus(str, Enum):
    """Lifecycle of a durable outbound-email delivery."""

    PENDING = "pending"
    LEASED = "leased"
    RETRY_SCHEDULED = "retry_scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class EmailDeliveryAttemptOutcome(str, Enum):
    """Recorded outcome for one leased provider attempt."""

    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    RETRYABLE_ERROR = "retryable_error"
    TERMINAL_ERROR = "terminal_error"
    LEASE_EXPIRED = "lease_expired"
