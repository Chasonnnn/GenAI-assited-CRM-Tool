"""Fail-closed recipient-local sending-window resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import phonenumbers
from phonenumbers import timezone as phone_timezone


@dataclass(frozen=True, slots=True)
class RecipientTimezone:
    timezone_name: str | None
    source: str


@dataclass(frozen=True, slots=True)
class SendingWindowDecision:
    allowed: bool
    defer_until: datetime | None
    reason: str | None


# Only states whose mailing locations share one practical civil time zone are
# resolved from state alone. Split-zone states fail over to ZIP/area evidence.
SINGLE_ZONE_STATES = {
    "AZ": "America/Phoenix",
    "CA": "America/Los_Angeles",
    "CO": "America/Denver",
    "CT": "America/New_York",
    "DC": "America/New_York",
    "DE": "America/New_York",
    "GA": "America/New_York",
    "IL": "America/Chicago",
    "IA": "America/Chicago",
    "LA": "America/Chicago",
    "MA": "America/New_York",
    "MD": "America/New_York",
    "ME": "America/New_York",
    "MN": "America/Chicago",
    "MO": "America/Chicago",
    "MS": "America/Chicago",
    "MT": "America/Denver",
    "NC": "America/New_York",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NM": "America/Denver",
    "NY": "America/New_York",
    "OH": "America/New_York",
    "OK": "America/Chicago",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "UT": "America/Denver",
    "VA": "America/New_York",
    "VT": "America/New_York",
    "WA": "America/Los_Angeles",
    "WI": "America/Chicago",
    "WV": "America/New_York",
    "WY": "America/Denver",
}


def _texas_postal_timezone(postal_code: str | None) -> str | None:
    digits = "".join(character for character in (postal_code or "") if character.isdigit())
    if len(digits) < 3:
        return None
    prefix = int(digits[:3])
    # El Paso/Hudspeth ZIP prefixes use Mountain Time; the remaining Texas
    # prefixes use Central Time. Invalid/non-Texas prefixes remain unresolved.
    if prefix in {798, 799, 885}:
        return "America/Denver"
    if prefix == 733 or 750 <= prefix <= 797:
        return "America/Chicago"
    return None


def resolve_recipient_timezone(
    *,
    phone_e164: str,
    state: str | None,
    postal_code: str | None,
    known_timezone: str | None = None,
) -> RecipientTimezone:
    """Prefer verified location, then accept only an unambiguous area-code zone."""
    if known_timezone:
        try:
            ZoneInfo(known_timezone)
        except ZoneInfoNotFoundError:
            pass
        else:
            return RecipientTimezone(known_timezone, "known_location")

    normalized_state = (state or "").strip().upper()
    if normalized_state == "TX":
        texas_timezone = _texas_postal_timezone(postal_code)
        if texas_timezone:
            return RecipientTimezone(texas_timezone, "postal_state")
    state_timezone = SINGLE_ZONE_STATES.get(normalized_state)
    if state_timezone:
        return RecipientTimezone(
            state_timezone,
            "postal_state" if postal_code else "state",
        )

    try:
        parsed = phonenumbers.parse(phone_e164, None)
        zones = tuple(
            zone
            for zone in phone_timezone.time_zones_for_number(parsed)
            if zone and zone != "Etc/Unknown"
        )
    except phonenumbers.NumberParseException:
        zones = ()
    unique_zones = tuple(dict.fromkeys(zones))
    if len(unique_zones) == 1:
        return RecipientTimezone(unique_zones[0], "phone_area_code")
    return RecipientTimezone(None, "ambiguous")


def _local_start(local_day, *, state: str | None, zone: ZoneInfo) -> datetime:
    is_texas_sunday = (state or "").strip().upper() == "TX" and local_day.weekday() == 6
    start_hour = 12 if is_texas_sunday else 9
    return datetime.combine(local_day, time(hour=start_hour), tzinfo=zone)


def evaluate_sending_window(
    *,
    now: datetime,
    timezone_name: str,
    state: str | None,
) -> SendingWindowDecision:
    """Allow 09:00-20:00 local, except Texas Sundays begin at 12:00."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown recipient timezone") from exc

    local_now = now.astimezone(zone)
    start = _local_start(local_now.date(), state=state, zone=zone)
    end = datetime.combine(local_now.date(), time(hour=20), tzinfo=zone)
    if local_now < start:
        reason = (
            "texas_sunday_before_noon"
            if (state or "").strip().upper() == "TX" and local_now.weekday() == 6
            else "before_sending_hours"
        )
        return SendingWindowDecision(
            allowed=False,
            defer_until=start.astimezone(UTC),
            reason=reason,
        )
    if local_now >= end:
        next_start = _local_start(
            local_now.date() + timedelta(days=1),
            state=state,
            zone=zone,
        )
        return SendingWindowDecision(
            allowed=False,
            defer_until=next_start.astimezone(UTC),
            reason="after_sending_hours",
        )
    return SendingWindowDecision(allowed=True, defer_until=None, reason=None)
