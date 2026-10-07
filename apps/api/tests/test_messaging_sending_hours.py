"""Recipient-local promotional sending-hours contracts."""

from datetime import UTC, datetime

import pytest


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


def _window(now, timezone_name, state, phone_e164=None):
    from app.services.messaging_sending_hours import evaluate_sending_window

    return evaluate_sending_window(
        now=now, timezone_name=timezone_name, state=state, phone_e164=phone_e164
    )


def test_federal_window_defers_before_eight_to_eight_recipient_local() -> None:
    # 14:30 UTC is 07:30 PDT.
    result = _window(datetime(2026, 7, 31, 14, 30, tzinfo=UTC), "America/Los_Angeles", "CA")

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 7, 31, 15, 0, tzinfo=UTC)
    assert result.reason == "before_sending_hours"


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 7, 31, 15, 30, tzinfo=UTC),  # 08:30 PDT
        datetime(2026, 8, 1, 3, 30, tzinfo=UTC),  # Jul 31, 20:30 PDT
    ],
)
def test_federal_window_allows_eight_to_nine(now) -> None:
    assert _window(now, "America/Los_Angeles", "CA").allowed is True


def test_federal_window_defers_at_nine_pm_to_next_morning() -> None:
    result = _window(datetime(2026, 8, 1, 4, 0, tzinfo=UTC), "America/Los_Angeles", "CA")

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 8, 1, 15, 0, tzinfo=UTC)
    assert result.reason == "after_sending_hours"


@pytest.mark.parametrize("state", ["FL", "OK", "MD", "WA"])
def test_eight_pm_states_close_an_hour_early(state) -> None:
    # 20:30 in the state's own zone.
    zone, now = {
        "FL": ("America/New_York", datetime(2026, 8, 1, 0, 30, tzinfo=UTC)),
        "OK": ("America/Chicago", datetime(2026, 8, 1, 1, 30, tzinfo=UTC)),
        "MD": ("America/New_York", datetime(2026, 8, 1, 0, 30, tzinfo=UTC)),
        "WA": ("America/Los_Angeles", datetime(2026, 8, 1, 3, 30, tzinfo=UTC)),
    }[state]

    result = _window(now, zone, state)

    assert result.allowed is False
    assert result.reason == "after_sending_hours"


def test_florida_area_code_applies_florida_hours_at_a_california_address() -> None:
    # 20:30 PDT: open under the federal rule, closed under Florida's area-code presumption.
    now = datetime(2026, 8, 1, 3, 30, tzinfo=UTC)

    assert _window(now, "America/Los_Angeles", "CA", "+13055550100").allowed is False
    assert _window(now, "America/Los_Angeles", "CA", "+14155550100").allowed is True


def test_texas_opens_at_nine_and_closes_at_nine() -> None:
    # Friday 08:30 CDT, then 20:30 CDT.
    early = _window(datetime(2026, 7, 31, 13, 30, tzinfo=UTC), "America/Chicago", "TX")
    late = _window(datetime(2026, 8, 1, 1, 30, tzinfo=UTC), "America/Chicago", "TX")

    assert early.allowed is False
    assert early.defer_until == datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    assert late.allowed is True


def test_texas_sunday_starts_at_noon() -> None:
    # Sunday, 10:00 CDT.
    result = _window(datetime(2026, 8, 2, 15, 0, tzinfo=UTC), "America/Chicago", "TX")

    assert result.allowed is False
    assert result.defer_until == datetime(2026, 8, 2, 17, 0, tzinfo=UTC)
    assert result.reason == "before_sending_hours"


def test_unknown_state_uses_the_narrowest_state_window() -> None:
    # 08:30 and 20:30 EDT are open federally but closed in Texas and Florida.
    assert (
        _window(datetime(2026, 7, 31, 12, 30, tzinfo=UTC), "America/New_York", None).allowed
        is False
    )
    assert (
        _window(datetime(2026, 8, 1, 0, 30, tzinfo=UTC), "America/New_York", None).allowed is False
    )
    assert (
        _window(datetime(2026, 7, 31, 13, 30, tzinfo=UTC), "America/New_York", None).allowed is True
    )


def test_unknown_timezone_waits_for_hours_open_in_every_us_zone() -> None:
    from app.services.messaging_sending_hours import evaluate_sending_window_in_every_us_timezone

    # 22:00 EDT: closed on the East Coast. Hawaii opens at 08:00 HST = 18:00 UTC.
    closed = evaluate_sending_window_in_every_us_timezone(
        now=datetime(2026, 8, 1, 2, 0, tzinfo=UTC), state="CA"
    )
    open_everywhere = evaluate_sending_window_in_every_us_timezone(
        now=datetime(2026, 8, 1, 19, 0, tzinfo=UTC), state="CA"
    )

    assert closed.allowed is False
    assert closed.defer_until == datetime(2026, 8, 1, 18, 0, tzinfo=UTC)
    assert open_everywhere.allowed is True


@pytest.mark.parametrize(
    ("state", "phone_e164", "applies"),
    [
        ("FL", "+14155550100", True),
        ("CA", "+13055550100", True),
        (None, "+14155550100", True),
        ("CA", "+14155550100", False),
    ],
)
def test_florida_rules_follow_address_or_area_code(state, phone_e164, applies) -> None:
    from app.services.messaging_sending_hours import florida_rules_apply

    assert florida_rules_apply(state=state, phone_e164=phone_e164) is applies
