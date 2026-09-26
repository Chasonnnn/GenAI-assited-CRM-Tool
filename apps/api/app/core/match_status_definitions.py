"""Shared fixed match lifecycle definitions."""

from __future__ import annotations

from app.db.enums import MatchStatus

MATCH_STATUS_DEFINITIONS = [
    {
        "value": MatchStatus.UNDER_REVIEW.value,
        "label": "Under Review",
        "color": "#D97706",
        "order": 2,
        "allowed_transitions": [
            MatchStatus.ACCEPTED.value,
            MatchStatus.DECLINED.value,
        ],
    },
    {
        "value": MatchStatus.ACCEPTED.value,
        "label": "Accepted",
        "color": "#059669",
        "order": 3,
        "allowed_transitions": [
            MatchStatus.CANCELLATION_PENDING.value,
            MatchStatus.COMPLETED.value,
        ],
    },
    {
        "value": MatchStatus.CANCELLATION_PENDING.value,
        "label": "Cancellation Pending",
        "color": "#B45309",
        "order": 4,
        "allowed_transitions": [MatchStatus.ACCEPTED.value, MatchStatus.CANCELLED.value],
    },
    {
        "value": MatchStatus.DECLINED.value,
        "label": "Declined",
        "color": "#DC2626",
        "order": 5,
        "allowed_transitions": [],
    },
    {
        "value": MatchStatus.CANCELLED.value,
        "label": "Cancelled",
        "color": "#6B7280",
        "order": 6,
        "allowed_transitions": [],
    },
    {
        "value": MatchStatus.COMPLETED.value,
        "label": "Completed",
        "color": "#059669",
        "order": 7,
        "allowed_transitions": [],
    },
]

MATCH_STATUS_BY_VALUE = {definition["value"]: definition for definition in MATCH_STATUS_DEFINITIONS}


def get_match_status_definition(status: str) -> dict[str, object] | None:
    return MATCH_STATUS_BY_VALUE.get(status)
