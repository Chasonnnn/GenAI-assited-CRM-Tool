from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import Appointment, Organization, SurrogateActivityLog, SurrogateStatusHistory
from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, surrogate_service, surrogate_status_service
from app.services import surrogate_interview_appointment_service as service


@pytest.fixture
def interview(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(full_name="Interview QA", email=f"{uuid4()}@example.com"),
    )
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    scheduled = pipeline_service.get_stage_by_key(db, pipeline.id, "interview_scheduled")
    surrogate_status_service.change_status(
        db,
        surrogate,
        scheduled.id,
        test_user.id,
        Role.ADMIN,
        interview_scheduled_at=datetime.now(UTC) + timedelta(days=3),
        trigger_workflows=False,
    )
    return surrogate, test_user


def command(db, surrogate, action, *, move=True, start=None):
    appt = service.get_latest(db, surrogate.organization_id, surrogate.id)
    return SurrogateInterviewAppointmentAction(
        action=action,
        move_stage=move,
        scheduled_start=start,
        expected_stage_id=surrogate.stage_id,
        expected_appointment_id=appt.id if appt else None,
        expected_scheduled_start=appt.scheduled_start if appt else None,
    )


def manage(db, surrogate, user, data):
    return service.manage(
        db,
        org_id=surrogate.organization_id,
        surrogate_id=surrogate.id,
        actor_user_id=user.id,
        actor_role=Role.ADMIN,
        data=data,
    )


def payload(data):
    return data.model_dump(mode="json")


@pytest.mark.asyncio
async def test_routes_require_auth_and_csrf(client, authed_client, db, interview):
    surrogate, _ = interview
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    request = payload(command(db, surrogate, "cancel"))

    assert (await client.get(path)).status_code == 401
    assert (await client.post(path, json=request)).status_code == 401

    authed_client.headers.pop(CSRF_HEADER, None)
    response = await authed_client.post(path, json=request)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_routes_hide_cross_tenant_surrogate(authed_client, db, interview):
    surrogate, _ = interview
    other_org = Organization(id=uuid4(), name="Other Interview Org", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    surrogate.organization_id = other_org.id
    db.commit()
    path = f"/surrogates/{surrogate.id}/interview-appointment"

    assert (await authed_client.get(path)).status_code == 404
    response = await authed_client.post(path, json=payload(command(db, surrogate, "cancel")))
    assert response.status_code == 404


def test_cancel_keep_stage_then_book_again(db, interview):
    surrogate, user = interview
    stage_id = surrogate.stage_id
    old = service.get_latest(db, surrogate.organization_id, surrogate.id)
    manage(db, surrogate, user, command(db, surrogate, "cancel", move=False))
    assert surrogate.stage_id == stage_id
    manage(
        db,
        surrogate,
        user,
        command(db, surrogate, "schedule", move=False, start=datetime.now(UTC) + timedelta(days=4)),
    )
    new = service.get_latest(db, surrogate.organization_id, surrogate.id)
    assert new.id != old.id
    assert old.status == "cancelled"
    assert new.status == "confirmed"
    assert surrogate.stage_id == stage_id


def test_cancel_rebook_preserves_history_and_stale_retry(db, interview):
    surrogate, user = interview
    old = service.get_latest(db, surrogate.organization_id, surrogate.id)
    cancel = command(db, surrogate, "cancel")
    manage(db, surrogate, user, cancel)
    assert surrogate.status_label == "Reschedule Needed"
    with pytest.raises(service.InterviewAppointmentError, match="changed"):
        manage(db, surrogate, user, cancel)
    manage(
        db,
        surrogate,
        user,
        command(db, surrogate, "schedule", start=datetime.now(UTC) + timedelta(days=4)),
    )
    assert surrogate.status_label == "Interview Scheduled"
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).id != old.id
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 2
    assert db.query(SurrogateStatusHistory).filter_by(surrogate_id=surrogate.id).count() >= 3


def test_reschedule_keeps_stage_and_enforces_both_appointments_buffers(db, interview):
    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    stage_id = surrogate.stage_id
    appointment.buffer_before_minutes = 15
    appointment.buffer_after_minutes = 0
    occupied_start = datetime.now(UTC) + timedelta(days=8)
    conflict = Appointment(
        organization_id=surrogate.organization_id,
        user_id=user.id,
        appointment_type_id=appointment.appointment_type_id,
        client_name="Conflict",
        client_email=f"{uuid4()}@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=occupied_start,
        scheduled_end=occupied_start + timedelta(minutes=30),
        duration_minutes=30,
        buffer_before_minutes=10,
        buffer_after_minutes=25,
        meeting_mode="phone",
        status="confirmed",
    )
    db.add(conflict)
    db.commit()

    # The requested appointment ends inside the other appointment's pre-buffer.
    requested = occupied_start - timedelta(minutes=35)
    with pytest.raises(service.InterviewAppointmentError, match="no longer available"):
        manage(
            db, surrogate, user, command(db, surrogate, "reschedule", move=False, start=requested)
        )

    # Both the existing appointment's post-buffer and this one's pre-buffer fit.
    accepted = occupied_start + timedelta(minutes=71)
    manage(db, surrogate, user, command(db, surrogate, "reschedule", move=False, start=accepted))
    db.refresh(appointment)
    assert surrogate.stage_id == stage_id
    assert appointment.scheduled_start == accepted
    assert appointment.buffer_before_minutes == 15
    assert appointment.buffer_after_minutes == 0


def test_stale_stage_and_appointment_versions_are_rejected(db, interview):
    surrogate, user = interview
    stale = command(
        db, surrogate, "reschedule", move=False, start=datetime.now(UTC) + timedelta(days=5)
    )
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.scheduled_start += timedelta(minutes=1)
    appointment.scheduled_end += timedelta(minutes=1)
    db.commit()
    with pytest.raises(service.InterviewAppointmentError, match="appointment changed"):
        manage(db, surrogate, user, stale)

    current = command(db, surrogate, "cancel", move=False)
    current.expected_stage_id = uuid4()
    with pytest.raises(service.InterviewAppointmentError, match="stage changed"):
        manage(db, surrogate, user, current)


@pytest.mark.asyncio
async def test_stage_change_failure_rolls_back_cancel_atomically(
    authed_client, db, interview, monkeypatch
):
    surrogate, _ = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    original_stage = surrogate.stage_id
    rollback_called = False
    state_before_rollback = None
    real_rollback = db.rollback

    def track_rollback():
        nonlocal rollback_called, state_before_rollback
        rollback_called = True
        state_before_rollback = (appointment.status, surrogate.stage_id)
        real_rollback()

    def fail_stage_change(*args, **kwargs):
        raise ValueError("injected stage failure")

    monkeypatch.setattr(surrogate_status_service, "change_status", fail_stage_change)
    monkeypatch.setattr(db, "rollback", track_rollback)
    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/interview-appointment",
        json=payload(command(db, surrogate, "cancel")),
    )
    assert response.status_code == 400
    assert rollback_called
    assert state_before_rollback == ("cancelled", original_stage)


def test_cross_org_and_wrong_owner_denied(db, interview):
    surrogate, user = interview
    data = command(db, surrogate, "cancel")
    with pytest.raises(service.InterviewAppointmentError) as exc:
        service.manage(
            db,
            org_id=uuid4(),
            surrogate_id=surrogate.id,
            actor_user_id=user.id,
            actor_role=Role.ADMIN,
            data=data,
        )
    assert exc.value.status_code == 404
    with pytest.raises(service.InterviewAppointmentError) as exc:
        service.manage(
            db,
            org_id=surrogate.organization_id,
            surrogate_id=surrogate.id,
            actor_user_id=uuid4(),
            actor_role=Role.INTAKE_SPECIALIST,
            data=data,
        )
    assert exc.value.status_code == 403


def test_missing_rollout_stage_leaves_appointment_unchanged(db, interview):
    surrogate, user = interview
    stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
    needed = pipeline_service.get_stage_by_key(db, stage.pipeline_id, "reschedule_needed")
    needed.is_active = False
    db.commit()
    before = db.query(SurrogateActivityLog).filter_by(surrogate_id=surrogate.id).count()
    with pytest.raises(service.InterviewAppointmentError):
        manage(db, surrogate, user, command(db, surrogate, "cancel"))
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).status == "confirmed"
    assert db.query(SurrogateActivityLog).filter_by(surrogate_id=surrogate.id).count() == before


def test_case_manager_can_cancel_and_rebook_without_regression_approval(db, interview):
    surrogate, user = interview
    surrogate.owner_type = "user"
    surrogate.owner_id = user.id
    db.commit()
    for action, start in [("cancel", None), ("schedule", datetime.now(UTC) + timedelta(days=7))]:
        service.manage(
            db,
            org_id=surrogate.organization_id,
            surrogate_id=surrogate.id,
            actor_user_id=user.id,
            actor_role=Role.CASE_MANAGER,
            data=command(db, surrogate, action, start=start),
        )
        assert surrogate.status_label == (
            "Reschedule Needed" if action == "cancel" else "Interview Scheduled"
        )
    assert (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=surrogate.id, activity_type="interview_cancelled")
        .count()
        == 1
    )


def test_reschedule_existing_appointment_from_needed_stage_does_not_duplicate(db, interview):
    surrogate, user = interview
    scheduled = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
    needed = pipeline_service.get_stage_by_key(db, scheduled.pipeline_id, "reschedule_needed")
    surrogate_status_service.change_status(
        db, surrogate, needed.id, user.id, Role.ADMIN, trigger_workflows=False
    )
    original = service.get_latest(db, surrogate.organization_id, surrogate.id)
    start = datetime.now(UTC) + timedelta(days=9)
    manage(db, surrogate, user, command(db, surrogate, "reschedule", start=start))
    assert surrogate.stage_id == scheduled.id
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).id == original.id
    assert original.scheduled_start == start
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 1
    assert (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=surrogate.id, activity_type="interview_rescheduled")
        .count()
        == 1
    )
