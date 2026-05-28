"""Tests for structured logging helpers."""

import logging
from types import SimpleNamespace

from app.core.structured_logging import (
    build_log_context,
    extract_safe_path_entity_ids,
    extract_trace_id,
    hash_email_for_log,
    log_structured_event,
)


def test_build_log_context_includes_only_provided_fields():
    context = build_log_context(
        user_id="user-1",
        user_email_hash="email-hash",
        org_id="org-1",
        org_slug="org-slug",
        role="case_manager",
        request_id="req-1",
        trace_id="trace-1",
        route="/surrogates",
        path="/surrogates/123",
        method="GET",
        status=200,
        latency_ms=12,
        safe_entity_ids={"surrogate_id": "surrogate-1"},
    )

    assert context == {
        "user_id": "user-1",
        "user_email_hash": "email-hash",
        "org_id": "org-1",
        "org_slug": "org-slug",
        "role": "case_manager",
        "request_id": "req-1",
        "trace_id": "trace-1",
        "route": "/surrogates",
        "path": "/surrogates/123",
        "method": "GET",
        "status": 200,
        "latency_ms": 12,
        "surrogate_id": "surrogate-1",
    }


def test_build_log_context_ignores_empty_fields():
    context = build_log_context(
        user_id="",
        org_id=None,
        request_id="req-1",
    )

    assert context == {"request_id": "req-1"}


def test_hash_email_for_log_is_deterministic_and_has_no_raw_email():
    first = hash_email_for_log("Niki.Torres@Example.COM ")
    second = hash_email_for_log("niki.torres@example.com")

    assert first == second
    assert len(first) == 64
    assert "niki" not in first.lower()
    assert "example" not in first.lower()


def test_extract_trace_id_from_cloud_trace_and_traceparent():
    cloud_request = SimpleNamespace(
        headers={"X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/1;o=1"}
    )
    traceparent_request = SimpleNamespace(
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    )

    assert extract_trace_id(cloud_request) == "105445aa7843bc8bf206b12000100000"
    assert extract_trace_id(traceparent_request) == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_extract_safe_path_entity_ids_only_allows_known_ids():
    request = SimpleNamespace(
        path_params={
            "surrogate_id": "surrogate-1",
            "match_id": "match-1",
            "token": "secret-token",
            "slug": "public-form",
        }
    )

    assert extract_safe_path_entity_ids(request) == {
        "surrogate_id": "surrogate-1",
        "match_id": "match-1",
    }


def test_log_structured_event_adds_cloud_logging_json_fields(caplog):
    with caplog.at_level(logging.INFO, logger="app.ops"):
        log_structured_event(
            "email_send_success",
            user_id="user-1",
            org_id="org-1",
            surrogate_id="surrogate-1",
            recipient_email_hash="email-hash",
        )

    record = next(
        record
        for record in caplog.records
        if record.name == "app.ops" and record.message == "email_send_success"
    )

    assert record.user_id == "user-1"
    assert record.json_fields == {
        "message": "email_send_success",
        "event": "email_send_success",
        "user_id": "user-1",
        "org_id": "org-1",
        "surrogate_id": "surrogate-1",
        "recipient_email_hash": "email-hash",
    }
