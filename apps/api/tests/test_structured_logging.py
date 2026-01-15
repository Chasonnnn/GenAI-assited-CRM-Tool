"""Tests for structured logging helpers."""

from app.core.structured_logging import build_log_context


def test_build_log_context_includes_only_provided_fields():
    context = build_log_context(
        user_id="user-1",
        org_id="org-1",
        request_id="req-1",
        route="/surrogates",
        method="GET",
    )

    assert context == {
        "user_id": "user-1",
        "org_id": "org-1",
        "request_id": "req-1",
        "route": "/surrogates",
        "method": "GET",
    }


def test_build_log_context_ignores_empty_fields():
    context = build_log_context(
        user_id="",
        org_id=None,
        request_id="req-1",
    )

    assert context == {"request_id": "req-1"}
