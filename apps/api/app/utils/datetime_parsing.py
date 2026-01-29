"""Datetime parsing helpers for imports and integrations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
            value=datetime.fromtimestamp(ts, tz=timezone.utc),
            warnings=warnings,
            used_fallback_timezone=used_fallback,
        )

    # ISO 8601 timestamps
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return ParsedDatetime(
            value=dt.astimezone(timezone.utc),
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
                value=dt.astimezone(timezone.utc),
                warnings=warnings,
                date_only=date_only,
                used_fallback_timezone=used_fallback,
            )
        except ValueError:
            continue

    warnings.append(f"Unrecognized datetime format: {value}")
    return ParsedDatetime(value=None, warnings=warnings, used_fallback_timezone=used_fallback)


def _resolve_timezone(org_timezone: str | None, warnings: list[str]) -> tuple[ZoneInfo, bool]:
    tz_name = org_timezone or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name), False
    except ZoneInfoNotFoundError:
        warnings.append(f"Unknown timezone '{tz_name}', defaulting to {DEFAULT_TIMEZONE}.")
        return ZoneInfo(DEFAULT_TIMEZONE), True
