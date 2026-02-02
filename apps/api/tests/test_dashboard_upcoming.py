from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.db.models import Surrogate, Task, ZoomMeeting
from app.db.enums import OwnerType, Role, SurrogateSource

@pytest.mark.asyncio
async def test_upcoming_includes_surrogate_number(db, authed_client, test_org, test_user, default_stage):
    now = datetime.now(timezone.utc)

    # Create surrogate
    surrogate = Surrogate(
        id=uuid.uuid4(),
        surrogate_number="S-TEST-01",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        source=SurrogateSource.MANUAL.value,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Test Surrogate",
        email="surrogate@test.com",
        email_hash="hash",
        created_at=now,
        updated_at=now,
    )
    db.add(surrogate)
    db.flush()

    # Create task linked to surrogate
    task = Task(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="Test Task",
        due_date=now.date(),
        surrogate_id=surrogate.id,
        created_at=now,
        updated_at=now,
    )
    db.add(task)

    # Create meeting linked to surrogate
    meeting = ZoomMeeting(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        surrogate_id=surrogate.id,
        zoom_meeting_id="123456789",
        topic="Test Meeting",
        start_time=now + timedelta(hours=1),
        join_url="https://zoom.us/j/123456789",
        start_url="https://zoom.us/s/123456789",
    )
    db.add(meeting)
    db.flush()

    response = await authed_client.get("/dashboard/upcoming?days=7")
    assert response.status_code == 200
    data = response.json()

    # Verify task
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["surrogate_number"] == "S-TEST-01"

    # Verify meeting
    assert len(data["meetings"]) == 1
    assert data["meetings"][0]["surrogate_number"] == "S-TEST-01"
