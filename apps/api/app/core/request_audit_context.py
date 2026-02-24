"""Per-request audit context for mutation fallback deduplication."""

from contextvars import ContextVar, Token


_REQUEST_AUDIT_CONTEXT: ContextVar[dict[str, bool] | None] = ContextVar(
    "request_audit_context",
    default=None,
)


def start_request_audit_context() -> Token:
    """Initialize request-local audit state and return context token."""
    return _REQUEST_AUDIT_CONTEXT.set({"explicit_event_emitted": False})


def reset_request_audit_context(token: Token) -> None:
    """Restore the previous request-local audit state."""
    _REQUEST_AUDIT_CONTEXT.reset(token)


def mark_explicit_event_emitted() -> None:
    """Mark the current request context as having emitted an explicit audit event."""
    context = _REQUEST_AUDIT_CONTEXT.get()
    if context is None:
        return
    context["explicit_event_emitted"] = True


def explicit_event_emitted() -> bool:
    """Return whether an explicit audit event has been emitted in this request."""
    context = _REQUEST_AUDIT_CONTEXT.get()
    if context is None:
        return False
    return bool(context.get("explicit_event_emitted"))
