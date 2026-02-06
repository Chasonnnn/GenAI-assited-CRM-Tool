"""Presentation helpers for turning internal values into human-friendly labels.

These helpers are intentionally conservative: they avoid "pretty printing" text
that already appears to be a user-facing label (mixed/upper-case), while still
fixing common internal formats like snake_case or kebab-case.
"""

from __future__ import annotations

import re


_SEPARATORS_RE = re.compile(r"[_-]+")
_WHITESPACE_RE = re.compile(r"\s+")
_SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "via",
    "vs",
}


def humanize_identifier(value: str | None) -> str:
    """Convert identifiers (e.g. snake_case) into human-friendly text.

    Examples:
        "intake_specialist" -> "Intake Specialist"
        "Intake_Specialist" -> "Intake Specialist"
        "ready-to-match" -> "Ready to Match"

    If the input already contains uppercase letters, we assume it is already a
    user-facing label (e.g. "Second hCG confirmed") and avoid `.title()` to
    prevent damaging acronym casing.
    """
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = _SEPARATORS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    if any(ch.isupper() for ch in text):
        return text

    words = text.split(" ")
    last_idx = len(words) - 1
    titled: list[str] = []
    for i, word in enumerate(words):
        if not word:
            continue
        if i not in (0, last_idx) and word in _SMALL_WORDS:
            titled.append(word)
        else:
            titled.append(word.capitalize())

    return " ".join(titled)
