"""Server-sent events helpers."""

from __future__ import annotations

import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE event payload."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}
