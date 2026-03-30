"""Helpers for normalizing and displaying surrogate journey timing values."""

from __future__ import annotations

import re
from typing import Any


JOURNEY_TIMING_PREFERENCE_LABELS: dict[str, str] = {
    "months_0_3": "0–3 months",
    "months_3_6": "3–6 months",
    "still_deciding": "Still deciding",
}

JOURNEY_TIMING_QUESTION_LABEL = "When would you like to start your surrogacy journey?"
JOURNEY_TIMING_FIELD_KEY_ALIASES = (
    "journey_timing_preference",
    "journey_timing",
    "journey_start",
    "journey_start_timing",
    "surrogacy_journey_timing",
)
JOURNEY_TIMING_LABEL_ALIASES = (
    JOURNEY_TIMING_QUESTION_LABEL,
    "When would you like to start your surrogate journey?",
)

_WHITESPACE_RE = re.compile(r"\s+")

_JOURNEY_TIMING_VALUE_ALIASES: dict[str, str] = {
    "months_0_3": "months_0_3",
    "0-3 months": "months_0_3",
    "0–3 months": "months_0_3",
    "0 - 3 months": "months_0_3",
    "0 to 3 months": "months_0_3",
    "months_3_6": "months_3_6",
    "3-6 months": "months_3_6",
    "3–6 months": "months_3_6",
    "3 - 6 months": "months_3_6",
    "3 to 6 months": "months_3_6",
    "still_deciding": "still_deciding",
    "still deciding": "still_deciding",
}


def normalize_journey_timing_text(value: str | None) -> str:
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", value.replace("—", "-").replace("–", "-").strip().lower())


def normalize_journey_timing_preference(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return _JOURNEY_TIMING_VALUE_ALIASES.get(normalize_journey_timing_text(text))


def get_journey_timing_preference_label(value: str | None) -> str:
    if not value:
        return "-"
    return JOURNEY_TIMING_PREFERENCE_LABELS.get(value, value)
