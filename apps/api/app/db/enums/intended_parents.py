"""Intended parent enums."""

from enum import Enum


class IntendedParentStatus(str, Enum):
    """
    Intended Parent status workflow.

    new → ready_to_match → matched → delivered
    Plus archive/restore pseudo-statuses for history tracking.
    """

    NEW = "new"
    READY_TO_MATCH = "ready_to_match"
    MATCHED = "matched"
    DELIVERED = "delivered"

    # Archive pseudo-statuses (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"
