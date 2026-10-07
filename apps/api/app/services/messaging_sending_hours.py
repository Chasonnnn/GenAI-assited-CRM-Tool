"""Recipient-local sending windows for promotional messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import phonenumbers
from phonenumbers import geocoder
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


@dataclass(frozen=True, slots=True)
class _Window:
    start_hour: int
    end_hour: int
    sunday_start_hour: int | None = None


# Quiet hours bind telephone solicitations only, so they apply to promotional
# messages. Transactional (operational) messages have no legal sending window.
# Federal TCPA: 08:00-21:00 recipient-local.
FEDERAL_PROMOTIONAL_WINDOW = _Window(8, 21)
STATE_PROMOTIONAL_WINDOWS = {
    "FL": _Window(8, 20),  # Florida Telephone Solicitation Act
    "OK": _Window(8, 20),  # Oklahoma Telephone Solicitation Act
    # Sources disagree on 8 or 9 p.m. for Maryland and Washington; 8 p.m. until counsel confirms.
    "MD": _Window(8, 20),
    "WA": _Window(8, 20),
    "TX": _Window(9, 21, sunday_start_hour=12),  # Texas SB 140
}
# Applies when the recipient's state is unknown, so every state's rule holds.
_UNKNOWN_STATE = "*"
# Applies when the recipient's time zone is unknown: send only when the window is open in all of them.
US_TIMEZONES = (
    "America/New_York",
    "America/Puerto_Rico",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
)
_STATE_CODES_BY_NAME = {
    "florida": "FL",
    "oklahoma": "OK",
    "maryland": "MD",
    "washington": "WA",
    "washington state": "WA",
    "texas": "TX",
}


def _area_code_state(phone_e164: str | None) -> str | None:
    """Return the state an area code implies, when that state has its own window."""
    if not phone_e164:
        return None
    try:
        parsed = phonenumbers.parse(phone_e164, None)
    except phonenumbers.NumberParseException:
        return None
    description = geocoder.description_for_number(parsed, "en").strip()
    if "," in description:
        # "City, ST" descriptions carry the postal code after the comma.
        return description.rsplit(",", 1)[1].strip().upper() or None
    return _STATE_CODES_BY_NAME.get(description.casefold())


def _applicable_windows(state: str | None, phone_e164: str | None) -> list[_Window]:
    """Windows of the address state and of the area-code state, which some laws presume."""
    normalized_state = (state or "").strip().upper() or _UNKNOWN_STATE
    states = {normalized_state, _area_code_state(phone_e164)}
    if _UNKNOWN_STATE in states:
        return [FEDERAL_PROMOTIONAL_WINDOW, *STATE_PROMOTIONAL_WINDOWS.values()]
    return [FEDERAL_PROMOTIONAL_WINDOW] + [
        STATE_PROMOTIONAL_WINDOWS[code] for code in states if code in STATE_PROMOTIONAL_WINDOWS
    ]


def _bounds(local_day: date, windows: list[_Window], zone: ZoneInfo) -> tuple[datetime, datetime]:
    is_sunday = local_day.weekday() == 6
    start_hour = max(
        window.sunday_start_hour
        if is_sunday and window.sunday_start_hour is not None
        else window.start_hour
        for window in windows
    )
    end_hour = min(window.end_hour for window in windows)
    return (
        datetime.combine(local_day, time(hour=start_hour), tzinfo=zone),
        datetime.combine(local_day, time(hour=end_hour), tzinfo=zone),
    )


def evaluate_sending_window(
    *,
    now: datetime,
    timezone_name: str,
    state: str | None,
    phone_e164: str | None = None,
) -> SendingWindowDecision:
    """Apply the narrowest promotional window of the federal rule and the recipient's states."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown recipient timezone") from exc

    windows = _applicable_windows(state, phone_e164)
    local_now = now.astimezone(zone)
    start, end = _bounds(local_now.date(), windows, zone)
    if local_now < start:
        return SendingWindowDecision(
            allowed=False,
            defer_until=start.astimezone(UTC),
            reason="before_sending_hours",
        )
    if local_now >= end:
        next_start, _ = _bounds(local_now.date() + timedelta(days=1), windows, zone)
        return SendingWindowDecision(
            allowed=False,
            defer_until=next_start.astimezone(UTC),
            reason="after_sending_hours",
        )
    return SendingWindowDecision(allowed=True, defer_until=None, reason=None)


def evaluate_sending_window_in_every_us_timezone(
    *,
    now: datetime,
    state: str | None,
    phone_e164: str | None = None,
) -> SendingWindowDecision:
    """Find the first moment the window is open in every US time zone."""
    candidate = now
    # The narrowest window still overlaps across US zones each day, so this settles quickly.
    for _ in range(len(US_TIMEZONES) * 3):
        blocked = [
            decision
            for decision in (
                evaluate_sending_window(
                    now=candidate, timezone_name=zone, state=state, phone_e164=phone_e164
                )
                for zone in US_TIMEZONES
            )
            if not decision.allowed
        ]
        if not blocked:
            if candidate == now:
                return SendingWindowDecision(allowed=True, defer_until=None, reason=None)
            return SendingWindowDecision(
                allowed=False, defer_until=candidate, reason="outside_shared_sending_hours"
            )
        candidate = max(decision.defer_until for decision in blocked if decision.defer_until)
    raise RuntimeError("No sending window is open in every US time zone")
