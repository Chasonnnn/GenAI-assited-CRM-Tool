"""Deterministic classification for inbound messaging consent instructions."""

from __future__ import annotations

import re
from typing import Literal

ConsentInstruction = Literal[
    "global_opt_out",
    "promotional_opt_out",
    "ambiguous_hold",
    "restore",
    "none",
]

GLOBAL_STOP_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
RESTORE_KEYWORDS = {"start", "unstop"}
PROMOTIONAL_TERMS = {
    "ad",
    "ads",
    "campaign",
    "marketing",
    "offer",
    "offers",
    "promotion",
    "promotional",
    "referral bonus",
}
REVOCATION_SIGNALS = (
    "stop",
    "unsubscribe",
    "opt out",
    "do not send",
    "dont send",
    "no more",
    "remove me",
)
GLOBAL_REVOCATION_PHRASES = (
    "stop all message",
    "stop texting me",
    "dont send me any more text",
    "do not send me any more text",
    "remove me from all message",
    "no more text",
    "opt me out of all",
    "dont contact me",
    "do not contact me",
    "dont text this number",
    "do not text this number",
)
AMBIGUOUS_REVOCATION_PHRASES = (
    "stop this",
    "stop these",
    "dont want this",
    "dont want these",
    "not interested in this",
)


def _normalize(value: str) -> str:
    folded = value.casefold().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def classify_consent_instruction(message_text: str) -> ConsentInstruction:
    """Classify one instruction without network calls or probabilistic behavior."""
    normalized = _normalize(message_text)
    if normalized in RESTORE_KEYWORDS:
        return "restore"
    if normalized in GLOBAL_STOP_KEYWORDS:
        return "global_opt_out"
    if any(phrase in normalized for phrase in GLOBAL_REVOCATION_PHRASES):
        return "global_opt_out"
    has_promotional_term = any(term in normalized for term in PROMOTIONAL_TERMS)
    has_revocation_signal = any(signal in normalized for signal in REVOCATION_SIGNALS)
    if has_promotional_term and has_revocation_signal:
        return "promotional_opt_out"
    if any(phrase in normalized for phrase in AMBIGUOUS_REVOCATION_PHRASES):
        return "ambiguous_hold"
    return "none"
