"""Ticketing and email-ingest enums."""

from enum import Enum


class MailboxKind(str, Enum):
    """Mailbox source kind."""

    JOURNAL = "journal"
    USER_SENT = "user_sent"


class MailboxProvider(str, Enum):
    """Mailbox provider."""

    GMAIL = "gmail"


class EmailDirection(str, Enum):
    """Canonical message direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EmailOccurrenceState(str, Enum):
    """Pipeline state for a mailbox occurrence."""

    DISCOVERED = "discovered"
    RAW_FETCHED = "raw_fetched"
    PARSED = "parsed"
    STITCHED = "stitched"
    LINKED = "linked"
    FAILED = "failed"


class RecipientSource(str, Enum):
    """How original recipient was resolved."""

    WORKSPACE_HEADER = "workspace_header"
    DELIVERED_TO = "delivered_to"
    X_ORIGINAL_TO = "x_original_to"
    TO_CC_SCAN = "to_cc_scan"
    UNKNOWN = "unknown"


class LinkConfidence(str, Enum):
    """Confidence bucket for stitch/link decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    """Ticket lifecycle status."""

    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    SPAM = "spam"


class TicketPriority(str, Enum):
    """Ticket priority level."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketLinkStatus(str, Enum):
    """Surrogate link status on ticket."""

    UNLINKED = "unlinked"
    LINKED = "linked"
    NEEDS_REVIEW = "needs_review"


class SurrogateEmailContactSource(str, Enum):
    """Source for surrogate contact address."""

    SYSTEM = "system"
    MANUAL = "manual"
