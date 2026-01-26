"""Campaign-related enums."""

from enum import Enum


class CampaignStatus(str, Enum):
    """Status of a campaign."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CampaignRecipientStatus(str, Enum):
    """Status of a campaign recipient."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"
