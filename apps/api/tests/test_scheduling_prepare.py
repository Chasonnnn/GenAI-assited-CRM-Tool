"""Operator preparation is membership-scoped and preserves calendar choices."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.db.models import CalendarBinding, Membership, Organization, UserIntegration
from app.services import calendar_binding_service, google_scheduling_adapter
from scripts.scheduling_prepare import prepare_primary


@pytest.fixture
def primary_calendar(db, test_auth, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="google_calendar",
        account_email="synthetic@example.test",
        access_token_encrypted="synthetic",
    )
    db.add(integration)
    db.flush()
    monkeypatch.setattr(
        calendar_binding_service,
        "discover_calendars",
        AsyncMock(
            return_value=[
                {
                    "calendar_id": "primary-calendar",
                    "display_name": "Primary",
                    "access_role": "owner",
                    "timezone": "UTC",
                    "primary": True,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        google_scheduling_adapter,
        "read_incremental_events",
        AsyncMock(
            return_value={
                "events": [],
                "complete": True,
                "calendar_id": "primary-calendar",
                "next_sync_token": "instances-v1:synthetic",
            }
        ),
    )
    return integration


@pytest.mark.asyncio
async def test_operator_prepares_primary_binding_and_complete_busy_snapshot(
    db, test_auth, primary_calendar
):
    result = await prepare_primary(db, organization_id=test_auth.org.id, user_id=test_auth.user.id)
    binding = db.query(CalendarBinding).one()
    assert binding.organization_id == test_auth.org.id
    assert binding.user_id == test_auth.user.id
    assert binding.integration_id == primary_calendar.id
    assert binding.calendar_id == "primary-calendar"
    assert (
        binding.is_active and binding.check_busy and binding.show_events and binding.write_bookings
    )
    assert binding.synced_at is not None and binding.sync_error is None
    assert result == {
        "ready": True,
        "projection_rows": 0,
        "synced_at": binding.synced_at.isoformat(),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["other_org", "inactive_member", "inactive_user"])
async def test_operator_denies_invalid_membership_before_provider_access(
    db, test_auth, primary_calendar, denial
):
    org_id = test_auth.org.id
    if denial == "other_org":
        other = Organization(name="Other", slug=f"other-{uuid4().hex}")
        db.add(other)
        db.flush()
        org_id = other.id
    elif denial == "inactive_member":
        membership = (
            db.query(Membership).filter_by(organization_id=org_id, user_id=test_auth.user.id).one()
        )
        membership.is_active = False
    else:
        test_auth.user.is_active = False
    db.flush()
    with pytest.raises(ValueError, match="Active organization membership required"):
        await prepare_primary(db, organization_id=org_id, user_id=test_auth.user.id)
    calendar_binding_service.discover_calendars.assert_not_awaited()
    assert db.query(CalendarBinding).count() == 0


@pytest.mark.asyncio
async def test_operator_does_not_replace_a_different_calendar_selection(
    db, test_auth, primary_calendar
):
    binding = CalendarBinding(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        integration_id=primary_calendar.id,
        account_email=primary_calendar.account_email,
        calendar_id="staff-selected-calendar",
        display_name="Staff selected",
        access_role="writer",
        timezone="UTC",
        write_bookings=True,
    )
    db.add(binding)
    db.commit()
    with pytest.raises(ValueError, match="Existing calendar selection"):
        await prepare_primary(db, organization_id=test_auth.org.id, user_id=test_auth.user.id)
    db.refresh(binding)
    assert binding.calendar_id == "staff-selected-calendar" and binding.write_bookings
    assert db.query(CalendarBinding).count() == 1
    google_scheduling_adapter.read_incremental_events.assert_not_awaited()
