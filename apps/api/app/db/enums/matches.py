"""Match-related enums."""

from enum import Enum


class MatchStatus(str, Enum):
    """
    Status of a match between surrogate and intended parent.

    Workflow: proposed → reviewing → accepted/rejected
    A cancelled status marks withdrawn proposals.
    """

    PROPOSED = "proposed"  # Initial match proposal
    REVIEWING = "reviewing"  # Under review by coordinator
    ACCEPTED = "accepted"  # Match finalized
    CANCEL_PENDING = "cancel_pending"  # Cancellation pending admin approval
    REJECTED = "rejected"  # Match declined with reason
    COMPLETED = "completed"  # Relationship completed
    CANCELLED = "cancelled"  # Proposal withdrawn


class MatchEventType(str, Enum):
    """
    Types of events for Match calendar.

    Color coding:
    - 🟠 Orange: Medications
    - 🔵 Blue: Medical exams
    - 🟡 Yellow: Legal milestones
    - 🔴 Red: Delivery/critical dates
    - ⚪ Gray: Custom/other
    """

    MEDICATION = "medication"
    MEDICAL_EXAM = "medical_exam"
    LEGAL = "legal"
    DELIVERY = "delivery"
    CUSTOM = "custom"


class MatchEventPerson(str, Enum):
    """
    Who the match event is for.

    Color coding:
    - 🟢 Green: IP events
    - 🟣 Purple: Surrogate events
    """

    SURROGATE = "surrogate"
    IP = "ip"
