"""Tests for Resend-safe correlation tags."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.services.resend_tags import merge_resend_correlation_tags, validate_resend_tags


ORG_ID = UUID("11111111-1111-4111-8111-111111111111")
EMAIL_LOG_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_validate_resend_tags_accepts_documented_shape() -> None:
    assert validate_resend_tags(
        (
            {"name": "message_kind", "value": "case-follow_up"},
            {"name": "campaign_id", "value": "abc_123"},
        )
    ) == (
        {"name": "message_kind", "value": "case-follow_up"},
        {"name": "campaign_id", "value": "abc_123"},
    )


@pytest.mark.parametrize(
    ("tags", "message"),
    [
        (({"name": "unsafe name", "value": "ok"},), "ASCII letters"),
        (({"name": "safe", "value": "contains space"},), "ASCII letters"),
        (({"name": "safe", "value": "é"},), "ASCII letters"),
        (({"name": "safe", "value": "ok"}, {"name": "safe", "value": "again"}), "unique"),
        (({"name": "x" * 257, "value": "ok"},), "256"),
        (({"name": "safe", "value": "x" * 257},), "256"),
        (tuple({"name": f"tag_{index}", "value": "ok"} for index in range(76)), "75"),
    ],
)
def test_validate_resend_tags_rejects_provider_invalid_values(
    tags: tuple[dict[str, str], ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_resend_tags(tags)


def test_merge_resend_correlation_tags_adds_opaque_non_pii_ids() -> None:
    assert merge_resend_correlation_tags(
        ({"name": "message_kind", "value": "campaign"},),
        organization_id=ORG_ID,
        email_log_id=EMAIL_LOG_ID,
    ) == (
        {"name": "message_kind", "value": "campaign"},
        {"name": "organization_id", "value": str(ORG_ID)},
        {"name": "email_log_id", "value": str(EMAIL_LOG_ID)},
    )


@pytest.mark.parametrize("reserved_name", ("organization_id", "email_log_id"))
def test_merge_resend_correlation_tags_rejects_reserved_names(
    reserved_name: str,
) -> None:
    with pytest.raises(ValueError, match="reserved"):
        merge_resend_correlation_tags(
            ({"name": reserved_name, "value": "caller-controlled"},),
            organization_id=ORG_ID,
            email_log_id=EMAIL_LOG_ID,
        )


def test_merge_resend_correlation_tags_enforces_75_tag_limit_after_system_tags() -> None:
    caller_tags = tuple({"name": f"tag_{index}", "value": "ok"} for index in range(74))

    with pytest.raises(ValueError, match="75"):
        merge_resend_correlation_tags(
            caller_tags,
            organization_id=ORG_ID,
            email_log_id=EMAIL_LOG_ID,
        )
