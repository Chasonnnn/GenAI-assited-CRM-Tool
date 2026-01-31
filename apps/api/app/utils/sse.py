"""Server-sent events helpers."""

from __future__ import annotations

import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE event payload."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def format_sse_comment(comment: str = "ping") -> str:
    """Format a comment event to prompt early flush through proxies."""
    return f": {comment}\n\n"


def sse_preamble(padding_bytes: int = 8192) -> str:
    """Send a padding comment to encourage proxies to flush SSE early."""
    if padding_bytes < 1:
        padding_bytes = 1
    return format_sse_comment(" " * padding_bytes)


STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Content-Encoding": "identity",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
