"""Structured logging helpers (PHI-safe)."""

import hashlib
import logging
import uuid
from typing import Any


ops_logger = logging.getLogger("app.ops")

SAFE_PATH_ENTITY_ID_KEYS = {
    "surrogate_id",
    "intended_parent_id",
    "ip_id",
    "match_id",
    "task_id",
    "appointment_id",
    "template_id",
    "email_log_id",
}


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _header_value(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", {}) or {}
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    if value is None:
        value = headers.get(name.title())
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def hash_email_for_log(email: str | None) -> str | None:
    """Return a deterministic hash for email identity in operational logs."""
    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_request_id(request: Any) -> str:
    """Return incoming request id or generate one for this request."""
    existing = _header_value(request, "X-Request-ID")
    if existing:
        return existing
    return str(uuid.uuid4())


def extract_trace_id(request: Any) -> str | None:
    """Extract Cloud Trace or W3C traceparent trace id."""
    cloud_trace = _header_value(request, "X-Cloud-Trace-Context")
    if cloud_trace:
        trace_id = cloud_trace.split("/", 1)[0].strip()
        if trace_id:
            return trace_id

    traceparent = _header_value(request, "traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 2 and parts[1].strip():
            return parts[1].strip()

    return None


def extract_safe_path_entity_ids(request: Any) -> dict[str, str]:
    """Return allowlisted path params that are useful for diagnostics."""
    path_params = getattr(request, "path_params", {}) or {}
    return {
        key: str(value)
        for key, value in path_params.items()
        if key in SAFE_PATH_ENTITY_ID_KEYS and _has_value(value)
    }


def get_route_template(request: Any) -> str | None:
    route = getattr(request, "scope", {}).get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return str(route_path)
    url = getattr(request, "url", None)
    path = getattr(url, "path", None)
    return str(path) if path else None


def build_log_context(
    *,
    user_id: str | None = None,
    user_email_hash: str | None = None,
    org_id: str | None = None,
    org_slug: str | None = None,
    role: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    route: str | None = None,
    path: str | None = None,
    method: str | None = None,
    status: int | None = None,
    latency_ms: int | None = None,
    error_code: str | None = None,
    permission: str | None = None,
    safe_entity_ids: dict[str, Any] | None = None,
    **extra_fields: Any,
) -> dict[str, Any]:
    """Return a PHI-safe log context dict."""
    context: dict[str, Any] = {}
    if _has_value(user_id):
        context["user_id"] = user_id
    if _has_value(user_email_hash):
        context["user_email_hash"] = user_email_hash
    if _has_value(org_id):
        context["org_id"] = org_id
    if _has_value(org_slug):
        context["org_slug"] = org_slug
    if _has_value(role):
        context["role"] = role
    if _has_value(request_id):
        context["request_id"] = request_id
    if _has_value(trace_id):
        context["trace_id"] = trace_id
    if _has_value(route):
        context["route"] = route
    if _has_value(path):
        context["path"] = path
    if _has_value(method):
        context["method"] = method
    if status is not None:
        context["status"] = status
    if latency_ms is not None:
        context["latency_ms"] = latency_ms
    if _has_value(error_code):
        context["error_code"] = error_code
    if _has_value(permission):
        context["permission"] = permission
    if safe_entity_ids:
        for key, value in safe_entity_ids.items():
            if key in SAFE_PATH_ENTITY_ID_KEYS and _has_value(value):
                context[key] = str(value)
    for key, value in extra_fields.items():
        if _has_value(value):
            context[key] = value
    return context


def build_request_log_context(
    request: Any,
    *,
    status: int,
    latency_ms: int | None = None,
    error_code: str | None = None,
    permission: str | None = None,
) -> dict[str, Any]:
    """Build the standard structured context for a completed API request."""
    session = getattr(getattr(request, "state", None), "user_session", None)
    role = getattr(session, "role", None)
    role_value = getattr(role, "value", role)
    url = getattr(request, "url", None)
    path = getattr(url, "path", None)
    state = getattr(request, "state", None)
    return build_log_context(
        user_id=str(session.user_id) if session else None,
        user_email_hash=hash_email_for_log(getattr(session, "email", None)) if session else None,
        org_id=str(session.org_id) if session else None,
        org_slug=getattr(state, "org_slug", None),
        role=str(role_value) if role_value else None,
        request_id=getattr(state, "request_id", None) or _header_value(request, "X-Request-ID"),
        trace_id=getattr(state, "trace_id", None) or extract_trace_id(request),
        route=get_route_template(request),
        path=str(path) if path else None,
        method=getattr(request, "method", None),
        status=status,
        latency_ms=latency_ms,
        error_code=error_code or getattr(state, "error_code", None),
        permission=permission or getattr(state, "permission", None),
        safe_entity_ids=extract_safe_path_entity_ids(request),
    )


def log_structured_event(event_name: str, *, level: int = logging.INFO, **context: Any) -> None:
    """Emit an ops structured log event."""
    log_context = build_log_context(**context)
    json_fields = {
        "message": event_name,
        "event": event_name,
        **log_context,
    }
    ops_logger.log(level, event_name, extra={**log_context, "json_fields": json_fields})
