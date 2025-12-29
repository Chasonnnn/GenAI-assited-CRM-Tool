"""Structured logging helpers (PHI-safe)."""

from typing import Any


def build_log_context(
    *,
    user_id: str | None = None,
    org_id: str | None = None,
    request_id: str | None = None,
    route: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Return a PHI-safe log context dict."""
    context: dict[str, Any] = {}
    if user_id:
        context["user_id"] = user_id
    if org_id:
        context["org_id"] = org_id
    if request_id:
        context["request_id"] = request_id
    if route:
        context["route"] = route
    if method:
        context["method"] = method
    return context
