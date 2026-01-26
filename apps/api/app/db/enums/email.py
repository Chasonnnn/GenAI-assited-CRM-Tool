"""Email-related enums."""

from enum import Enum


class EmailStatus(str, Enum):
    """Status of outbound emails."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class SuppressionReason(str, Enum):
    """Reason for email suppression."""

    OPT_OUT = "opt_out"
    BOUNCED = "bounced"
    ARCHIVED = "archived"
    COMPLAINT = "complaint"
