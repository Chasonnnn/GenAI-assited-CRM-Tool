"""Recipient-local application sending-hours contracts."""

from datetime import UTC, datetime


def test_california_state_wins_over_phone_area_code() -> None:
    from app.services.messaging_sending_hours import resolve_recipient_timezone

    resolved = resolve_recipient_timezone(
        phone_e164="+12125550110",
        state="CA",
        postal_code="94105",
    )

    assert resolved.timezone_name == "America/Los_Angeles"
    assert resolved.source == "postal_state"


def test_phone_area_timezone_is_used_only_when_location_is_absent() -> None:
    from app.services.messaging_sending_hours import resolve_recipient_timezone

    resolved = resolve_recipient_timezone(
        phone_e164="+12125550110",
        state=None,
        postal_code=None,
    )

    assert resolved.timezone_name == "America/New_York"
    assert resolved.source == "phone_area_code"


def test_ambiguous_location_fails_closed() -> None:
    from app.services.messaging_sending_hours import resolve_recipient_timezone

    resolved = resolve_recipient_timezone(
        phone_e164="+18005550110",
        state=None,
        postal_code=None,
    )

    assert resolved.timezone_name is None
    assert resolved.source == "ambiguous"


def test_before_nine_is_deferred_to_nine_recipient_local() -> None:
    from app.services.messaging_sending_hours import evaluate_sending_window

    # 15:30 UTC is 08:30 PDT.
    result = evaluate_sending_window(
        now=datetime(2026, 7, 31, 15, 30, tzinfo=UTC),
        timezone_name="America/Los_Angeles",
        state="CA",
    )

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 7, 31, 16, 0, tzinfo=UTC)
    assert result.reason == "before_sending_hours"


def test_at_eight_pm_is_deferred_to_next_day() -> None:
    from app.services.messaging_sending_hours import evaluate_sending_window

    result = evaluate_sending_window(
        now=datetime(2026, 8, 1, 3, 0, tzinfo=UTC),  # Jul 31, 20:00 PDT
        timezone_name="America/Los_Angeles",
        state="CA",
    )

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 8, 1, 16, 0, tzinfo=UTC)
    assert result.reason == "after_sending_hours"


def test_texas_sunday_starts_at_noon() -> None:
    from app.services.messaging_sending_hours import evaluate_sending_window

    # Sunday, 10:00 CDT.
    result = evaluate_sending_window(
        now=datetime(2026, 8, 2, 15, 0, tzinfo=UTC),
        timezone_name="America/Chicago",
        state="TX",
    )

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 8, 2, 17, 0, tzinfo=UTC)
    assert result.reason == "texas_sunday_before_noon"


def test_inside_window_is_allowed() -> None:
    from app.services.messaging_sending_hours import evaluate_sending_window

    result = evaluate_sending_window(
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
        timezone_name="America/Los_Angeles",
        state="CA",
    )

    assert result.allowed is True
    assert result.defer_until is None
    assert result.reason is None
