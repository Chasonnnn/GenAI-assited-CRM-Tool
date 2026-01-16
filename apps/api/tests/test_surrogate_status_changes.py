from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID
import uuid

import pytest

from app.db.models import StatusChangeRequest, Surrogate, SurrogateStatusHistory
from app.services import pipeline_service


def _org_timezone() -> ZoneInfo:
    return ZoneInfo("America/Los_Angeles")


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


async def _create_surrogate(authed_client):
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Status Change Test",
            "email": f"status-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_surrogate_status_change_backdate_requires_reason(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    # Set surrogate created_at to allow backdating to yesterday
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    surrogate_row.created_at = datetime.now(_org_timezone()) - timedelta(days=7)
    db.commit()

    yesterday = (datetime.now(_org_timezone()).date() - timedelta(days=1)).isoformat()

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id), "effective_at": yesterday},
    )
    assert response.status_code == 403
    assert "Reason required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_surrogate_status_change_today_date_no_time_is_effective_now(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    today = datetime.now(_org_timezone()).date().isoformat()
    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id), "effective_at": today},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "applied"

    surrogate_id = UUID(surrogate["id"])
    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert history is not None
    assert history.effective_at is not None
    delta_seconds = abs((history.recorded_at - history.effective_at).total_seconds())
    assert delta_seconds < 10


@pytest.mark.asyncio
async def test_surrogate_status_regression_creates_pending_request(authed_client, db, test_auth):
    """Regression outside the 5-minute undo grace period requires admin approval."""
    surrogate = await _create_surrogate(authed_client)
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    new_unread_stage = _get_stage(db, test_auth.org.id, "new_unread")

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    # Move the history record's recorded_at back to be outside the 5-minute undo grace period
    surrogate_id = UUID(surrogate["id"])
    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .first()
    )
    history.recorded_at = datetime.now(_org_timezone()) - timedelta(minutes=10)
    db.commit()

    regression = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(new_unread_stage.id), "reason": "Requested correction"},
    )
    assert regression.status_code == 200, regression.text
    regression_payload = regression.json()
    assert regression_payload["status"] == "pending_approval"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == contacted_stage.id

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "surrogate",
            StatusChangeRequest.entity_id == surrogate_id,
        )
        .first()
    )
    assert request is not None
    assert request.status == "pending"
    assert request.target_stage_id == new_unread_stage.id

    # Only 1 history entry (from new_unread -> contacted), no new entry for pending regression
    history_count = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .count()
    )
    assert history_count == 1


@pytest.mark.asyncio
async def test_approve_status_change_request_applies_regression(authed_client, db, test_auth):
    """Admin approval of a regression request applies the change and records audit trail."""
    surrogate = await _create_surrogate(authed_client)
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    new_unread_stage = _get_stage(db, test_auth.org.id, "new_unread")

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert response.status_code == 200, response.text

    # Move history outside undo grace period
    surrogate_id = UUID(surrogate["id"])
    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .first()
    )
    history.recorded_at = datetime.now(_org_timezone()) - timedelta(minutes=10)
    db.commit()

    regression = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(new_unread_stage.id), "reason": "Regression request"},
    )
    assert regression.status_code == 200, regression.text
    assert regression.json()["status"] == "pending_approval"
    request_id = UUID(regression.json()["request_id"])

    approve = await authed_client.post(f"/status-change-requests/{request_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == new_unread_stage.id

    regression_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.request_id == request_id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert regression_history is not None
    assert regression_history.approved_by_user_id == test_auth.user.id


@pytest.mark.asyncio
async def test_surrogate_status_undo_within_grace_period_bypasses_approval(
    authed_client, db, test_auth
):
    """Regression within 5-minute undo grace period by same user applies immediately."""
    surrogate = await _create_surrogate(authed_client)
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    new_unread_stage = _get_stage(db, test_auth.org.id, "new_unread")

    # Move to contacted
    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    # Undo immediately (within grace period) - should apply without approval
    undo = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(new_unread_stage.id), "reason": "Undoing mistake"},
    )
    assert undo.status_code == 200, undo.text
    undo_payload = undo.json()
    assert undo_payload["status"] == "applied"  # Immediate, not pending_approval

    surrogate_id = UUID(surrogate["id"])
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == new_unread_stage.id

    # Check history has is_undo=True
    undo_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.to_stage_id == new_unread_stage.id,
        )
        .first()
    )
    assert undo_history is not None
    assert undo_history.is_undo is True
