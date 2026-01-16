"""Tests for Zoom service idempotency."""

import uuid

import pytest

from app.db.enums import EntityType
from app.db.models import ZoomMeeting
from app.services import zoom_service


@pytest.mark.asyncio
async def test_schedule_zoom_meeting_idempotent_returns_existing(
    db, test_org, test_user, monkeypatch
):
    existing = ZoomMeeting(
        organization_id=test_org.id,
        user_id=test_user.id,
        surrogate_id=None,
        intended_parent_id=None,
        zoom_meeting_id="123",
        topic="Test Meeting",
        start_time=None,
        duration=30,
        timezone="UTC",
        join_url="https://zoom.us/j/123",
        start_url="https://zoom.us/s/123",
        password=None,
        idempotency_key="zoom:dedupe",
    )
    db.add(existing)
    db.commit()

    async def should_not_create(*args, **kwargs):
        raise AssertionError("create_zoom_meeting should not be called for idempotent requests")

    monkeypatch.setattr(zoom_service, "create_zoom_meeting", should_not_create)

    result = await zoom_service.schedule_zoom_meeting(
        db=db,
        user_id=test_user.id,
        org_id=test_org.id,
        entity_type=EntityType.SURROGATE,
        entity_id=uuid.uuid4(),
        topic="Test Meeting",
        start_time=None,
        timezone_name="UTC",
        duration=30,
        contact_name=None,
        idempotency_key="zoom:dedupe",
    )

    assert result.meeting.join_url == existing.join_url
    assert str(result.meeting.id) == "123"
