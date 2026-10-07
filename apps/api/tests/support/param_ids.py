"""Reject parametrized tests whose large payloads became their test ids.

pytest prints auto-generated ids in every `-v` line. A megabyte bytes parameter
without `ids=` made GitHub Actions jobs hang with no log (PR #781).
"""

from __future__ import annotations

from collections.abc import Iterable

LARGE_PARAM_BYTES = 1024
MAX_PARAM_ID_LENGTH = 200


def oversized_param_ids(items: Iterable[object]) -> list[str]:
    """Return node ids that carry a large bytes/str parameter in their test id."""
    offenders = []
    for item in items:
        callspec = getattr(item, "callspec", None)
        if callspec is None or len(callspec.id) <= MAX_PARAM_ID_LENGTH:
            continue
        if any(
            isinstance(value, (bytes, bytearray, str)) and len(value) > LARGE_PARAM_BYTES
            for value in callspec.params.values()
        ):
            offenders.append(item.nodeid[:MAX_PARAM_ID_LENGTH])
    return offenders
