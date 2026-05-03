from datetime import datetime, timedelta, timezone, time
import uuid
from zoneinfo import ZoneInfo

import pytest

from app.db.enums import OwnerType, Role, TaskType
from app.db.models import (
    Appointment,
    AppointmentType,
    StatusChangeRequest,
    SurrogateStatusHistory,
    Task,
)
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
        user_role=Role.INTAKE_SPECIALIST,
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
        user_role=Role.INTAKE_SPECIALIST,
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


@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
def test_status_change_regression_self_approves_for_admin_or_developer(
    db, test_org, test_user, role
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    applied = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=contacted_stage.id,
        user_id=test_user.id,
        user_role=role,
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
        user_role=role,
        reason="Requested correction",
    )
    assert regression["status"] == "applied"

    db.refresh(surrogate)
    assert surrogate.stage_id == new_unread_stage.id

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

    regression_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate.id,
            SurrogateStatusHistory.to_stage_id == new_unread_stage.id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert regression_history is not None
    assert regression_history.request_id is None
    assert regression_history.changed_by_user_id == test_user.id
    assert regression_history.approved_by_user_id == test_user.id
    assert regression_history.approved_at is not None


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


def test_on_hold_requires_reason(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    on_hold_stage = _get_stage(db, test_org.id, "on_hold")

    with pytest.raises(ValueError, match="Reason required"):
        surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=on_hold_stage.id,
            user_id=test_user.id,
            user_role=Role.DEVELOPER,
        )


def test_interview_scheduled_requires_interview_datetime(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    interview_stage = _get_stage(db, test_org.id, "interview_scheduled")

    with pytest.raises(ValueError, match="Interview date and time required"):
        surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=interview_stage.id,
            user_id=test_user.id,
            user_role=Role.DEVELOPER,
        )


def test_interview_scheduled_creates_confirmed_interview_appointment(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    surrogate.phone = "5551234567"
    interview_stage = _get_stage(db, test_org.id, "interview_scheduled")
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=3)

    result = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=interview_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        interview_scheduled_at=scheduled_at,
    )

    assert result["status"] == "applied"
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_org.id,
            Appointment.surrogate_id == surrogate.id,
        )
        .one()
    )
    assert appointment.status == "confirmed"
    assert appointment.client_name == surrogate.full_name
    assert appointment.client_email == surrogate.email
    assert appointment.client_phone == surrogate.phone
    assert appointment.scheduled_start == scheduled_at
    assert appointment.scheduled_end == scheduled_at + timedelta(minutes=30)
    assert appointment.approved_by_user_id == test_user.id

    appointment_type = (
        db.query(AppointmentType)
        .filter(AppointmentType.id == appointment.appointment_type_id)
        .one()
    )
    assert appointment_type.name == "Initial Interview"


def test_on_hold_creates_follow_up_and_resume_cleans_up(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")
    on_hold_stage = _get_stage(db, test_org.id, "on_hold")

    surrogate.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.commit()

    effective_at = datetime(2026, 1, 31, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

    applied = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=on_hold_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        reason="Waiting on family timing",
        effective_at=effective_at,
        on_hold_follow_up_months=1,
    )
    assert applied["status"] == "applied"

    db.refresh(surrogate)
    assert surrogate.stage_id == on_hold_stage.id
    assert surrogate.paused_from_stage_id == new_unread_stage.id
    assert surrogate.on_hold_follow_up_task_id is not None

    follow_up_task = (
        db.query(Task).filter(Task.id == surrogate.on_hold_follow_up_task_id).one_or_none()
    )
    assert follow_up_task is not None
    assert follow_up_task.task_type == TaskType.FOLLOW_UP.value
    assert follow_up_task.title == "On-Hold follow-up"
    assert follow_up_task.owner_type == "user"
    assert follow_up_task.owner_id == surrogate.owner_id
    assert follow_up_task.due_date.isoformat() == "2026-02-28"
    assert "Waiting on family timing" in (follow_up_task.description or "")
    assert "New Unread" in (follow_up_task.description or "")

    latest_history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert latest_history is not None
    latest_history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    resumed = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=new_unread_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )
    assert resumed["status"] == "applied"

    db.refresh(surrogate)
    assert surrogate.stage_id == new_unread_stage.id
    assert surrogate.paused_from_stage_id is None
    assert surrogate.on_hold_follow_up_task_id is None
    assert db.query(Task).filter(Task.id == follow_up_task.id).one_or_none() is None


def test_on_hold_follow_up_assigns_queue_owned_cases_to_actor(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    on_hold_stage = _get_stage(db, test_org.id, "on_hold")

    surrogate.owner_type = OwnerType.QUEUE.value
    surrogate.owner_id = uuid.uuid4()
    surrogate.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.commit()

    surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=on_hold_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        reason="Waiting on next outreach window",
        effective_at=datetime(2026, 2, 1, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        on_hold_follow_up_months=3,
    )

    db.refresh(surrogate)
    follow_up_task = (
        db.query(Task).filter(Task.id == surrogate.on_hold_follow_up_task_id).one_or_none()
    )
    assert follow_up_task is not None
    assert follow_up_task.owner_type == OwnerType.USER.value
    assert follow_up_task.owner_id == test_user.id


def test_leaving_on_hold_uses_paused_from_stage_for_regression_logic(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    approved_stage = _get_stage(db, test_org.id, "approved")
    on_hold_stage = _get_stage(db, test_org.id, "on_hold")

    surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=contacted_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )
    surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=on_hold_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        reason="Paused before approval",
    )

    latest_history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert latest_history is not None
    latest_history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    applied = surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=approved_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )
    assert applied["status"] == "applied"

    db.refresh(surrogate)
    assert surrogate.stage_id == approved_stage.id
    assert surrogate.paused_from_stage_id is None
    assert surrogate.on_hold_follow_up_task_id is None
