"""Validation for React Email editor documents stored beside template bodies.

``body_design`` is the editor's TipTap JSON document (ADR 0010). The server
never renders it; ``body`` HTML stays the send artifact. The checks here keep
the column to a bounded editor document so it cannot carry arbitrary payloads.
"""

from __future__ import annotations

import json
from typing import Any

MAX_BODY_DESIGN_BYTES = 500_000


class InvalidBodyDesignError(ValueError):
    """The value is not a bounded editor document."""


def validate_body_design(value: object) -> dict[str, Any] | None:
    """Return the document unchanged, or raise when it is not an editor doc."""
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("type") != "doc":
        raise InvalidBodyDesignError("body_design must be an editor document")
    content = value.get("content", [])
    if not isinstance(content, list):
        raise InvalidBodyDesignError("body_design content must be a list")
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    if len(encoded) > MAX_BODY_DESIGN_BYTES:
        raise InvalidBodyDesignError("body_design is too large")
    return value
