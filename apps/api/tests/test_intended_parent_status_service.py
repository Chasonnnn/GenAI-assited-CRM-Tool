from datetime import datetime, timedelta, timezone, time
import uuid
from zoneinfo import ZoneInfo

import pytest

from app.db.enums import IntendedParentStatus
from app.db.models import IntendedParentStatusHistory, StatusChangeRequest
from app.services import ip_service
from app.services import intended_parent_status_service


def _create_ip(db, org_id, user_id):
    return ip_service.create_intended_parent(
        db,
        org_id,
        user_id,
        full_name="IP Status Test",
        email=f"ip-{uuid.uuid4().hex[:8]}@example.com",
    )


def test_ip_status_backdate_requires_reason(db, test_org, test_user):
    ip = _create_ip(db, test_org.id, test_user.id)
    ip.created_at = datetime.now(timezone.utc) - timedelta(days=7)
    db.commit()

    org_now = datetime.now(ZoneInfo("America/Los_Angeles"))
    yesterday = org_now.date() - timedelta(days=1)
    effective_at = datetime.combine(yesterday, time(0, 0))

    with pytest.raises(ValueError, match="Reason required"):
        intended_parent_status_service.change_status(
            db=db,
            ip=ip,
            new_status=IntendedParentStatus.READY_TO_MATCH.value,
            user_id=test_user.id,
            effective_at=effective_at,
        )


def test_ip_status_regression_creates_pending_request(db, test_org, test_user):
    ip = _create_ip(db, test_org.id, test_user.id)

    applied = intended_parent_status_service.change_status(
        db=db,
        ip=ip,
        new_status=IntendedParentStatus.READY_TO_MATCH.value,
        user_id=test_user.id,
    )
    assert applied["status"] == "applied"

    history = (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == ip.id)
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )
    assert history is not None
    history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    regression = intended_parent_status_service.change_status(
        db=db,
        ip=ip,
        new_status=IntendedParentStatus.NEW.value,
        user_id=test_user.id,
        reason="Requested correction",
    )
    assert regression["status"] == "pending_approval"

    db.refresh(ip)
    assert ip.status == IntendedParentStatus.READY_TO_MATCH.value

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "intended_parent",
            StatusChangeRequest.entity_id == ip.id,
        )
        .first()
    )
    assert request is not None
    assert request.status == "pending"
    assert request.target_status == IntendedParentStatus.NEW.value


def test_ip_status_undo_within_grace_period_applies(db, test_org, test_user):
    ip = _create_ip(db, test_org.id, test_user.id)

    applied = intended_parent_status_service.change_status(
        db=db,
        ip=ip,
        new_status=IntendedParentStatus.READY_TO_MATCH.value,
        user_id=test_user.id,
    )
    assert applied["status"] == "applied"

    undo = intended_parent_status_service.change_status(
        db=db,
        ip=ip,
        new_status=IntendedParentStatus.NEW.value,
        user_id=test_user.id,
        reason="Undoing mistake",
    )
    assert undo["status"] == "applied"

    undo_history = (
        db.query(IntendedParentStatusHistory)
        .filter(
            IntendedParentStatusHistory.intended_parent_id == ip.id,
            IntendedParentStatusHistory.new_status == IntendedParentStatus.NEW.value,
        )
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )
    assert undo_history is not None
    assert undo_history.is_undo is True

    request_count = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "intended_parent",
            StatusChangeRequest.entity_id == ip.id,
            StatusChangeRequest.status == "pending",
        )
        .count()
    )
    assert request_count == 0
