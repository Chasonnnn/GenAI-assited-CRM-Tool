from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import (
    Appointment,
    Membership,
    Organization,
    OrganizationPermissionPolicy,
    Queue,
    RecordCollaborator,
    RolePermission,
    RoleRecordScope,
    SurrogateActivityLog,
    SurrogateStatusHistory,
)
from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, surrogate_service, surrogate_status_service
from app.services import surrogate_interview_appointment_service as service


@pytest.fixture(autouse=True)
def notifications(monkeypatch):
    from app.services import appointment_email_service

    sent = {name: Mock() for name in ("send_rescheduled", "send_cancelled")}
    for name, mock in sent.items():
        monkeypatch.setattr(appointment_email_service, name, mock)
    return sent


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
    authed_client, db, interview, monkeypatch, notifications
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
    for mock in notifications.values():
        mock.assert_not_called()


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
    scheduled_activities = (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=surrogate.id, activity_type="interview_scheduled")
        .count()
    )
    start = datetime.now(UTC) + timedelta(days=9)
    manage(db, surrogate, user, command(db, surrogate, "reschedule", start=start))
    assert surrogate.stage_id == scheduled.id
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).id == original.id
    assert original.scheduled_start == start
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 1
    assert (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=surrogate.id, activity_type="interview_scheduled")
        .count()
        == scheduled_activities
    )
    assert (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=surrogate.id, activity_type="interview_rescheduled")
        .count()
        == 1
    )


@pytest.mark.parametrize("action", ["schedule", "reschedule", "cancel"])
@pytest.mark.parametrize("move", [False, True])
def test_exact_retry_has_no_duplicate_mutations_or_notifications(
    db, interview, notifications, action, move
):
    surrogate, user = interview
    if action == "schedule":
        manage(db, surrogate, user, command(db, surrogate, "cancel", move=move))
        for mock in notifications.values():
            mock.reset_mock()
    old_start = service.get_latest(db, surrogate.organization_id, surrogate.id).scheduled_start
    request = command(
        db,
        surrogate,
        action,
        move=move,
        start=None if action == "cancel" else datetime.now(UTC) + timedelta(days=8),
    )
    manage(db, surrogate, user, request)
    counts = [
        db.query(model).filter_by(surrogate_id=surrogate.id).count()
        for model in (Appointment, SurrogateActivityLog, SurrogateStatusHistory)
    ]
    manage(db, surrogate, user, request)
    assert counts == [
        db.query(model).filter_by(surrogate_id=surrogate.id).count()
        for model in (Appointment, SurrogateActivityLog, SurrogateStatusHistory)
    ]
    if action != "schedule":
        mock = notifications["send_cancelled" if action == "cancel" else "send_rescheduled"]
        mock.assert_called_once()
        if action == "reschedule":
            assert mock.call_args.args[2] == old_start
    # An altered request is not an exact retry, even when the desired time matches.
    changed = request.model_copy(update={"expected_stage_id": uuid4()})
    with pytest.raises(service.InterviewAppointmentError):
        manage(db, surrogate, user, changed)


def test_commit_failure_does_not_notify(db, interview, notifications, monkeypatch):
    surrogate, user = interview
    request = command(db, surrogate, "cancel")
    monkeypatch.setattr(db, "commit", Mock(side_effect=RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        manage(db, surrogate, user, request)
    for mock in notifications.values():
        mock.assert_not_called()


def test_retry_after_a_later_edit_is_still_stale(db, interview, notifications):
    surrogate, user = interview
    request = command(
        db, surrogate, "reschedule", move=False, start=datetime.now(UTC) + timedelta(days=6)
    )
    manage(db, surrogate, user, request)
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    # A separate edit invalidates the receipt even if its starting time still matches.
    appointment.scheduled_end += timedelta(minutes=15)
    db.commit()
    with pytest.raises(service.InterviewAppointmentError, match="appointment changed"):
        manage(db, surrogate, user, request)
    notifications["send_rescheduled"].assert_called_once()


@pytest.mark.asyncio
async def test_http_retry_after_rebooking_returns_success(authed_client, db, interview):
    surrogate, user = interview
    manage(db, surrogate, user, command(db, surrogate, "cancel"))
    request = payload(
        command(db, surrogate, "schedule", start=datetime.now(UTC) + timedelta(days=6))
    )
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    first = await authed_client.post(path, json=request)
    retry = await authed_client.post(path, json=request)
    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json() == first.json()


@pytest.fixture
def v2_interview(db, interview):
    surrogate, user = interview
    membership = (
        db.query(Membership)
        .filter_by(organization_id=surrogate.organization_id, user_id=user.id)
        .one()
    )
    membership.role = Role.CASE_MANAGER
    surrogate.owner_type = "user"
    surrogate.owner_id = user.id
    db.add(OrganizationPermissionPolicy(organization_id=surrogate.organization_id, version=2))
    db.add(
        RoleRecordScope(
            organization_id=surrogate.organization_id,
            role="case_manager",
            module="surrogates",
            assignment="assigned",
            phase="all",
            stage_ids=[],
        )
    )
    db.commit()
    return surrogate, user, membership


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permission",
    [
        "view_surrogates",
        "edit_surrogates",
        "change_surrogate_status",
        "manage_appointments",
    ],
)
async def test_v2_appointment_requires_each_action(
    authed_client, db, v2_interview, notifications, permission
):
    surrogate, _, _ = v2_interview
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    assert (await authed_client.get(path)).json()["can_manage"] is True
    request = payload(command(db, surrogate, "cancel"))
    original_stage = surrogate.stage_id
    db.add(
        RolePermission(
            organization_id=surrogate.organization_id,
            role="case_manager",
            permission=permission,
            is_granted=False,
        )
    )
    db.commit()

    read = await authed_client.get(path)
    if permission == "view_surrogates":
        assert read.status_code == 403
    else:
        assert read.status_code == 200
        assert read.json()["can_manage"] is False
    assert (await authed_client.post(path, json=request)).status_code == 403
    db.refresh(surrogate)
    assert surrogate.stage_id == original_stage
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).status == "confirmed"
    for mock in notifications.values():
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_v2_appointment_collaboration_revocation_blocks_owner_of_appointment(
    authed_client, db, v2_interview, notifications
):
    surrogate, user, membership = v2_interview
    queue = Queue(organization_id=surrogate.organization_id, name="Interview pool", is_active=True)
    db.add(queue)
    db.flush()
    surrogate.owner_id = queue.id
    surrogate.owner_type = "queue"
    collaborator = RecordCollaborator(
        organization_id=surrogate.organization_id,
        membership_id=membership.id,
        user_id=user.id,
        surrogate_id=surrogate.id,
    )
    db.add(collaborator)
    db.commit()
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    visible = await authed_client.get(path)
    assert visible.status_code == 200
    assert visible.json()["can_manage"] is True
    request = payload(command(db, surrogate, "cancel"))
    db.delete(collaborator)
    db.commit()

    assert (await authed_client.get(path)).status_code == 403
    assert (await authed_client.post(path, json=request)).status_code == 403
    assert service.get_latest(db, surrogate.organization_id, surrogate.id).status == "confirmed"
    for mock in notifications.values():
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_v2_appointment_cancel_rebook_and_revoked_retry(authed_client, db, v2_interview):
    surrogate, _, _ = v2_interview
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    cancelled = await authed_client.post(path, json=payload(command(db, surrogate, "cancel")))
    assert cancelled.status_code == 200
    assert surrogate.status_label == "Reschedule Needed"
    request = payload(
        command(db, surrogate, "schedule", start=datetime.now(UTC) + timedelta(days=8))
    )
    booked = await authed_client.post(path, json=request)
    assert booked.status_code == 200
    assert booked.json()["appointment"]["status"] == "confirmed"
    assert surrogate.status_label == "Interview Scheduled"
    assert (await authed_client.post(path, json=request)).status_code == 200

    db.add(
        RolePermission(
            organization_id=surrogate.organization_id,
            role="case_manager",
            permission="manage_appointments",
            is_granted=False,
        )
    )
    db.commit()
    assert (await authed_client.post(path, json=request)).status_code == 403
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 2


@pytest.mark.asyncio
async def test_v2_appointment_hides_other_organization(authed_client, db, v2_interview):
    surrogate, _, _ = v2_interview
    request = payload(command(db, surrogate, "cancel"))
    other_org = Organization(id=uuid4(), name="Other org", slug=f"v2-other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    surrogate.organization_id = other_org.id
    db.commit()
    path = f"/surrogates/{surrogate.id}/interview-appointment"
    assert (await authed_client.get(path)).status_code == 404
    assert (await authed_client.post(path, json=request)).status_code == 404
