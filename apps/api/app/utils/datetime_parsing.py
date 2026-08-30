"""Datetime parsing helpers for imports and integrations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "America/Los_Angeles"

DATETIME_FORMATS: list[str] = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m-%d-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M",
    "%m-%d-%Y %I:%M %p",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
]

DATE_ONLY_FORMATS = {"%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"}


@dataclass
class ParsedDatetime:
    value: datetime | None
    warnings: list[str]
    date_only: bool = False
    used_fallback_timezone: bool = False


def parse_datetime_with_timezone(raw_value: str, org_timezone: str | None) -> ParsedDatetime:
    """Parse datetime using org timezone as default when no timezone is present."""
    value = raw_value.strip()
    if not value:
        return ParsedDatetime(value=None, warnings=[])

    warnings: list[str] = []
    tz, used_fallback = _resolve_timezone(org_timezone, warnings)

    # Epoch timestamps (seconds or milliseconds)
    if re.fullmatch(r"\d{10,13}", value):
        ts = int(value)
        if len(value) == 13:
            ts = ts / 1000
        return ParsedDatetime(
            value=datetime.fromtimestamp(ts, tz=UTC),
            warnings=warnings,
            used_fallback_timezone=used_fallback,
        )

    # ISO 8601 timestamps
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return ParsedDatetime(
            value=dt.astimezone(UTC),
            warnings=warnings,
            used_fallback_timezone=used_fallback,
        )
    except ValueError:
        pass

    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            date_only = fmt in DATE_ONLY_FORMATS
            if date_only:
                warnings.append("Date-only value; assuming 12:00 local time.")
                dt = dt.replace(hour=12, minute=0, second=0)
            dt = dt.replace(tzinfo=tz)
            return ParsedDatetime(
                value=dt.astimezone(UTC),
                warnings=warnings,
                date_only=date_only,
                used_fallback_timezone=used_fallback,
            )
        except ValueError:
            continue

    warnings.append(f"Unrecognized datetime format: {value}")
    return ParsedDatetime(value=None, warnings=warnings, used_fallback_timezone=used_fallback)


def parse_created_from_filter(value: str) -> datetime:
    """Parse an inclusive ISO creation-date lower bound in UTC."""
    normalized = value.strip()
    if "T" not in normalized:
        return datetime.combine(date.fromisoformat(normalized), time.min, tzinfo=UTC)
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_created_to_filter(value: str) -> tuple[datetime, bool]:
    """Parse an ISO upper bound, making a date-only bound inclusive."""
    normalized = value.strip()
    if "T" not in normalized:
        parsed_date = date.fromisoformat(normalized)
        return datetime.combine(parsed_date + timedelta(days=1), time.min, tzinfo=UTC), True
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC), False)


def normalize_effective_at(
    effective_at: datetime | None,
    org_timezone: str,
    *,
    now: datetime | None = None,
) -> datetime:
    """Normalize a stage-change effective time to timezone-aware UTC."""
    current_time = now or datetime.now(UTC)
    if effective_at is None:
        return current_time

    org_tz = ZoneInfo(org_timezone)
    local_effective_at = (
        effective_at.replace(tzinfo=org_tz)
        if effective_at.tzinfo is None
        else effective_at.astimezone(org_tz)
    )
    if local_effective_at.time() == time.min:
        today = current_time.astimezone(org_tz).date()
        if local_effective_at.date() == today:
            return current_time
        if local_effective_at.date() < today:
            return datetime.combine(local_effective_at.date(), time(12), tzinfo=org_tz).astimezone(
                UTC
            )
    return local_effective_at.astimezone(UTC)


def _resolve_timezone(org_timezone: str | None, warnings: list[str]) -> tuple[ZoneInfo, bool]:
    tz_name = org_timezone or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name), False
    except ZoneInfoNotFoundError:
        warnings.append(f"Unknown timezone '{tz_name}', defaulting to {DEFAULT_TIMEZONE}.")
        return ZoneInfo(DEFAULT_TIMEZONE), True
