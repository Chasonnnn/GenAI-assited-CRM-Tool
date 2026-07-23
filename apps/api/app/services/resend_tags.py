"""Validation and correlation helpers for Resend email tags."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from uuid import UUID


MAX_RESEND_TAGS = 75
MAX_RESEND_TAG_LENGTH = 256
_TAG_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_CORRELATION_TAG_NAMES = frozenset({"organization_id", "email_log_id"})


def validate_resend_tags(
    tags: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    """Return a copied, provider-valid tag tuple or raise before queueing."""
    if len(tags) > MAX_RESEND_TAGS:
        raise ValueError(f"Resend accepts at most {MAX_RESEND_TAGS} tags")

    validated: list[dict[str, str]] = []
    names: set[str] = set()
    for tag in tags:
        name = tag.get("name")
        value = tag.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Resend tag name and value must be strings")
        if len(name) > MAX_RESEND_TAG_LENGTH or len(value) > MAX_RESEND_TAG_LENGTH:
            raise ValueError(
                f"Resend tag name and value must be {MAX_RESEND_TAG_LENGTH} characters or fewer"
            )
        if not _TAG_VALUE_PATTERN.fullmatch(name) or not _TAG_VALUE_PATTERN.fullmatch(value):
            raise ValueError(
                "Resend tag name and value may contain only ASCII letters, numbers, "
                "underscores, or dashes"
            )
        if name in names:
            raise ValueError("Resend tag names must be unique")
        names.add(name)
        validated.append({"name": name, "value": value})
    return tuple(validated)


def merge_resend_correlation_tags(
    tags: Sequence[Mapping[str, str]],
    *,
    organization_id: UUID,
    email_log_id: UUID,
) -> tuple[dict[str, str], ...]:
    """Add the opaque identifiers required to correlate signed webhooks."""
    validated = validate_resend_tags(tags)
    if any(tag["name"] in _CORRELATION_TAG_NAMES for tag in validated):
        raise ValueError("Resend correlation tag names are reserved")

    return validate_resend_tags(
        (
            *validated,
            {"name": "organization_id", "value": str(organization_id)},
            {"name": "email_log_id", "value": str(email_log_id)},
        )
    )
