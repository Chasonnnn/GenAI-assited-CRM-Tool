from datetime import datetime, timedelta, timezone, time
import uuid
from zoneinfo import ZoneInfo

import pytest

from app.db.enums import Role
from app.db.models import StatusChangeRequest, SurrogateStatusHistory
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, surrogate_service, surrogate_status_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


def _create_surrogate(db, org_id, user_id):
    return surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="Service Status Test",
            email=f"status-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )


def test_status_change_backdate_requires_reason(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    surrogate.created_at = datetime.now(timezone.utc) - timedelta(days=7)
    db.commit()

    target_stage = _get_stage(db, test_org.id, "contacted")
    org_now = datetime.now(ZoneInfo("America/Los_Angeles"))
    yesterday = org_now.date() - timedelta(days=1)
    effective_at = datetime.combine(yesterday, time(0, 0))

    with pytest.raises(ValueError, match="Reason required"):
        surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=target_stage.id,
            user_id=test_user.id,
            user_role=Role.DEVELOPER,
            effective_at=effective_at,
        )


def test_status_change_regression_creates_pending_request(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    applied = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=contacted_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )
    assert applied["status"] == "applied"

    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
        .first()
    )
    assert history is not None
    history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    regression = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=new_unread_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        reason="Requested correction",
    )
    assert regression["status"] == "pending_approval"

    db.refresh(surrogate)
    assert surrogate.stage_id == contacted_stage.id

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "surrogate",
            StatusChangeRequest.entity_id == surrogate.id,
        )
        .first()
    )
    assert request is not None
    assert request.status == "pending"
    assert request.target_stage_id == new_unread_stage.id


def test_status_change_undo_within_grace_period_applies(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    applied = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=contacted_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )
    assert applied["status"] == "applied"

    undo = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=new_unread_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        reason="Undoing mistake",
    )
    assert undo["status"] == "applied"

    undo_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate.id,
            SurrogateStatusHistory.to_stage_id == new_unread_stage.id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert undo_history is not None
    assert undo_history.is_undo is True

    request_count = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "surrogate",
            StatusChangeRequest.entity_id == surrogate.id,
            StatusChangeRequest.status == "pending",
        )
        .count()
    )
    assert request_count == 0
