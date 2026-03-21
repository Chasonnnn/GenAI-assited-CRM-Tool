"""Shared fixed match lifecycle definitions."""

from __future__ import annotations

from app.db.enums import MatchStatus

MATCH_STATUS_DEFINITIONS = [
    {
        "value": MatchStatus.PROPOSED.value,
        "label": "Proposed",
        "color": "#2563EB",
        "order": 1,
        "allowed_transitions": [
            MatchStatus.REVIEWING.value,
            MatchStatus.ACCEPTED.value,
            MatchStatus.REJECTED.value,
            MatchStatus.CANCELLED.value,
        ],
    },
    {
        "value": MatchStatus.REVIEWING.value,
        "label": "Reviewing",
        "color": "#D97706",
        "order": 2,
        "allowed_transitions": [
            MatchStatus.ACCEPTED.value,
            MatchStatus.REJECTED.value,
            MatchStatus.CANCELLED.value,
        ],
    },
    {
        "value": MatchStatus.ACCEPTED.value,
        "label": "Accepted",
        "color": "#059669",
        "order": 3,
        "allowed_transitions": [MatchStatus.CANCEL_PENDING.value],
    },
    {
        "value": MatchStatus.CANCEL_PENDING.value,
        "label": "Cancel Pending",
        "color": "#B45309",
        "order": 4,
        "allowed_transitions": [MatchStatus.ACCEPTED.value, MatchStatus.CANCELLED.value],
    },
    {
        "value": MatchStatus.REJECTED.value,
        "label": "Rejected",
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
]

MATCH_STATUS_BY_VALUE = {definition["value"]: definition for definition in MATCH_STATUS_DEFINITIONS}


def get_match_status_definition(status: str) -> dict[str, object] | None:
    return MATCH_STATUS_BY_VALUE.get(status)
