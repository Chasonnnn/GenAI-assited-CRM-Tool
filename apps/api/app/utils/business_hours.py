"""Business hours calculator with US federal holidays support.

Calculates due dates based on business hours (8am-6pm, Mon-Fri),
excluding US federal holidays. Minute-level precision, DST-safe.
"""

from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import holidays

from app.core.constants import BUSINESS_HOURS_START, BUSINESS_HOURS_END


@lru_cache(maxsize=10)
def get_us_holidays(year: int) -> set:
    """Cache holiday sets per year for performance."""
    return set(holidays.US(years=year).keys())


def is_business_day(dt: datetime) -> bool:
    """Check if date is a business day (Mon-Fri, not a holiday)."""
    if dt.weekday() >= 5:  # Weekend
        return False
    if dt.date() in get_us_holidays(dt.year):
        return False
    return True


def is_business_time(dt: datetime) -> bool:
    """Check if datetime is within business hours (8am-6pm, Mon-Fri, not holiday)."""
    if not is_business_day(dt):
        return False
    return BUSINESS_HOURS_START <= dt.hour < BUSINESS_HOURS_END


def next_business_start(dt: datetime) -> datetime:
    """Get next business hour start (8:00am on next business day if outside hours)."""
    # If before 8am on a business day, start at 8am same day
    if is_business_day(dt):
        if dt.hour < BUSINESS_HOURS_START:
            return dt.replace(hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0)
        if dt.hour < BUSINESS_HOURS_END:
            return dt  # Already in business hours

    # Move to next day and find next business day
    dt = dt.replace(hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    while not is_business_day(dt):
        dt += timedelta(days=1)
    return dt


def add_business_hours(start_utc: datetime, hours: int, timezone: str) -> datetime:
    """
    Add business hours (8am-6pm, Mon-Fri, excl US federal holidays).

    Args:
        start_utc: Start time in UTC
        hours: Number of business hours to add (e.g., 48)
        timezone: IANA timezone (e.g., 'America/New_York')

    Returns:
        Due datetime in UTC
    """
    tz = ZoneInfo(timezone)
    local = start_utc.astimezone(tz)

    # If outside business hours, start clock at next business hour
    if not is_business_time(local):
        local = next_business_start(local)

    remaining_minutes = hours * 60

    while remaining_minutes > 0:
        # Skip to next business day if needed
        while not is_business_time(local):
            local = next_business_start(local)

        # Calculate minutes remaining in current business day
        end_of_day = local.replace(hour=BUSINESS_HOURS_END, minute=0, second=0, microsecond=0)
        minutes_left_today = int((end_of_day - local).total_seconds() / 60)

        if remaining_minutes <= minutes_left_today:
            local += timedelta(minutes=remaining_minutes)
            remaining_minutes = 0
        else:
            remaining_minutes -= minutes_left_today
            # Move to next day 8am
            local = local.replace(
                hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)

    return local.astimezone(ZoneInfo("UTC"))


def get_effective_timezone(owner, org) -> str:
    """Get timezone with fallback: owner → org → UTC."""
    if owner and hasattr(owner, "timezone") and owner.timezone:
        return owner.timezone
    if org and hasattr(org, "timezone") and org.timezone:
        return org.timezone
    return "UTC"


def calculate_approval_due_date(
    start_utc: datetime,
    owner,
    org,
    timeout_hours: int = 48,
) -> datetime:
    """
    Calculate workflow approval due date based on business hours.

    Args:
        start_utc: Start time in UTC (usually now)
        owner: User model with optional timezone attribute
        org: Organization model with optional timezone attribute
        timeout_hours: Number of business hours (default 48)

    Returns:
        Due datetime in UTC
    """
    tz = get_effective_timezone(owner, org)
    return add_business_hours(start_utc, timeout_hours, tz)
