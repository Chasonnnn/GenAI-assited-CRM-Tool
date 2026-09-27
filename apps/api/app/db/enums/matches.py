"""Match-related enums."""

from enum import Enum


class MatchStatus(str, Enum):
    """Status of a match, separate from party pipeline stages."""

    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    CANCELLATION_PENDING = "cancellation_pending"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


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
