"""Scheduling v2 command invariants on a disposable PostgreSQL database."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.core.config import settings
from app.db.enums import AppointmentStatus, JobType, MeetingMode, Role
from app.db.models import Appointment, AppointmentType, AuditLog, AvailabilityRule, Job, Membership
from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
from app.schemas.surrogate import SurrogateCreate
from app.services import (
    pipeline_service,
    scheduling_v2_service,
    surrogate_interview_appointment_service,
    surrogate_service,
    surrogate_status_service,
)


@pytest.fixture
def booking_type(db, test_org, test_user):
    start = (datetime.now(UTC) + timedelta(days=14)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    appointment_type = AppointmentType(
        organization_id=test_org.id,
        user_id=test_user.id,
        name="Scheduling v2 phone",
        slug=f"scheduling-v2-{uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        auto_approve=False,
        reminder_hours_before=0,
        is_active=True,
    )
    db.add_all(
        [
            appointment_type,
            AvailabilityRule(
                organization_id=test_org.id,
                user_id=test_user.id,
                day_of_week=start.weekday(),
                start_time=time(8),
                end_time=time(18),
                timezone="UTC",
            ),
        ]
    )
    db.commit()
    return appointment_type, start


def _create(
    db,
    org_id,
    owner_id,
    appointment_type_id,
    start,
    *,
    request_id="create-one",
    meeting_mode=MeetingMode.PHONE.value,
):
    return scheduling_v2_service.create_booking(
        db,
        org_id=org_id,
        user_id=owner_id,
        appointment_type_id=appointment_type_id,
        client_name="Scheduling QA",
        client_email="scheduling-v2@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        client_notes=None,
        idempotency_key=None,
        meeting_mode=meeting_mode,
        record_links=None,
        actor_scope="test-public-booking",
        actor_user_id=None,
        request_id=request_id,
        expected_revision=0,
        override_availability=False,
        override_reason=None,
    )


def test_pending_create_is_atomic_with_expiry_and_receipt(
    db, test_org, test_user, booking_type, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    assert appointment.status == AppointmentStatus.PENDING.value
    assert appointment.revision == 1
    jobs = db.query(Job).filter(Job.organization_id == test_org.id).all()
    assert any(job.job_type == JobType.APPOINTMENT_EXPIRE.value for job in jobs)
    replay = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    assert replay.id == appointment.id
    assert db.query(Appointment).filter(Appointment.organization_id == test_org.id).count() == 1


def test_offboarded_owner_cannot_receive_new_public_booking(
    db, test_org, test_user, booking_type, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    membership = (
        db.query(Membership)
        .filter(
            Membership.organization_id == test_org.id,
            Membership.user_id == test_user.id,
        )
        .one()
    )
    membership.is_active = False
    db.commit()
    with pytest.raises(ValueError, match="owner is unavailable"):
        _create(db, test_org.id, test_user.id, appointment_type.id, start)
    assert db.query(Appointment).filter(Appointment.organization_id == test_org.id).count() == 0


def test_expiry_job_is_revision_fenced(db, test_org, test_user, booking_type, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment.pending_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert not scheduling_v2_service.expire_booking(
        db, appointment_id=appointment.id, org_id=test_org.id, revision=appointment.revision + 1
    )
    assert scheduling_v2_service.expire_booking(
        db, appointment_id=appointment.id, org_id=test_org.id, revision=appointment.revision
    )
    assert appointment.status == AppointmentStatus.EXPIRED.value
    assert appointment.revision == 2
    assert not scheduling_v2_service.expire_booking(
        db, appointment_id=appointment.id, org_id=test_org.id, revision=1
    )


def test_stage_booking_uses_v2_command_and_records_override(
    db, test_org, test_user, booking_type, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    _, start = booking_type
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(full_name="Scheduling Stage", email=f"stage-{uuid4()}@example.com"),
    )
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "interview_scheduled")
    surrogate_status_service.change_status(
        db,
        surrogate,
        stage.id,
        test_user.id,
        Role.DEVELOPER,
        interview_scheduled_at=start,
        override_availability=True,
        override_reason="Staff-approved conflict for urgent interview",
        trigger_workflows=False,
    )
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_org.id,
            Appointment.surrogate_id == surrogate.id,
        )
        .one()
    )
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert appointment.revision == 1
    assert appointment.origin == "crm"
    assert (
        appointment.availability_override_reason == "Staff-approved conflict for urgent interview"
    )
    from app.services import oauth_service

    override_audit = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == test_org.id, AuditLog.target_id == appointment.id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert override_audit is not None
    encrypted = override_audit.details["availability_override_reason_encrypted"]
    assert "Staff-approved" not in encrypted
    assert oauth_service.decrypt_token(encrypted) == appointment.availability_override_reason
    from app.routers.audit import _response_details

    projected = _response_details(override_audit.details)
    assert projected["availability_override_reason"] == appointment.availability_override_reason
    assert "availability_override_reason_encrypted" not in projected
    action = SurrogateInterviewAppointmentAction(
        action="reschedule",
        scheduled_start=start + timedelta(days=7),
        move_stage=False,
        expected_stage_id=surrogate.stage_id,
        expected_appointment_id=appointment.id,
        expected_scheduled_start=appointment.scheduled_start,
        expected_revision=1,
        request_id="stage-move-one",
    )
    surrogate_interview_appointment_service.manage(
        db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        actor_user_id=test_user.id,
        actor_role=Role.DEVELOPER,
        data=action,
    )
    db.refresh(appointment)
    assert appointment.revision == 2
    assert appointment.scheduled_start == start + timedelta(days=7)
    cancel = SurrogateInterviewAppointmentAction(
        action="cancel",
        move_stage=False,
        expected_stage_id=surrogate.stage_id,
        expected_appointment_id=appointment.id,
        expected_scheduled_start=appointment.scheduled_start,
        expected_revision=2,
        request_id="stage-cancel-one",
    )
    surrogate_interview_appointment_service.manage(
        db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        actor_user_id=test_user.id,
        actor_role=Role.DEVELOPER,
        data=cancel,
    )
    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CANCELLED.value
    assert appointment.revision == 3


def test_phone_lifecycle_replays_exact_public_result_and_rejects_stale_revision(
    db, test_org, test_user, booking_type, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment = scheduling_v2_service.approve_booking(
        db,
        appointment,
        approved_by_user_id=test_user.id,
        expected_revision=1,
        request_id="approve-one",
    )
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert appointment.revision == 2
    with pytest.raises(scheduling_v2_service.SchedulingConflict):
        scheduling_v2_service.reschedule_booking(
            db,
            appointment,
            start + timedelta(days=7),
            by_client=False,
            token=None,
            actor_user_id=test_user.id,
            expected_revision=1,
            request_id="stale-move",
            actor_scope=scheduling_v2_service.staff_actor_scope(test_user.id),
            override_availability=False,
            override_reason=None,
        )
    old_token = appointment.reschedule_token
    move_id = "move-one"
    moved = scheduling_v2_service.reschedule_booking(
        db,
        appointment,
        start + timedelta(days=7),
        by_client=True,
        token=old_token,
        actor_user_id=None,
        expected_revision=2,
        request_id=move_id,
        actor_scope=scheduling_v2_service.public_actor_scope(old_token),
        override_availability=False,
        override_reason=None,
    )
    assert moved.revision == 3
    assert moved.scheduled_start == start + timedelta(days=7)
    assert moved.reschedule_token != old_token
    replay = scheduling_v2_service.replay_public_change(
        db,
        org_id=test_org.id,
        token=old_token,
        request_id=move_id,
        action="reschedule",
        new_start=start + timedelta(days=7),
    )
    assert replay.id == moved.id
    assert replay._scheduling_replay_result["revision"] == 3
    with pytest.raises(scheduling_v2_service.SchedulingConflict):
        scheduling_v2_service.replay_public_change(
            db,
            org_id=test_org.id,
            token=old_token,
            request_id=move_id,
            action="reschedule",
            new_start=start + timedelta(days=14),
        )
    cancel_token = moved.cancel_token
    cancelled = scheduling_v2_service.cancel_booking(
        db,
        moved,
        reason="Client requested",
        by_client=True,
        token=cancel_token,
        actor_user_id=None,
        expected_revision=3,
        request_id="cancel-one",
        actor_scope=scheduling_v2_service.public_actor_scope(cancel_token),
    )
    assert cancelled.status == AppointmentStatus.CANCELLED.value
    assert cancelled.revision == 4
    assert cancelled.cancel_token is None
    cancel_replay = scheduling_v2_service.replay_public_change(
        db,
        org_id=test_org.id,
        token=cancel_token,
        request_id="cancel-one",
        action="cancel",
        reason="Client requested",
    )
    assert cancel_replay._scheduling_replay_result["revision"] == 4


def test_unlinked_meet_queues_crm_confirmation_notice(
    db, test_org, test_user, booking_type, monkeypatch
):
    from app.db.models import AppointmentEmailLog

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment_type.auto_approve = True
    appointment_type.meeting_mode = MeetingMode.GOOGLE_MEET.value
    appointment_type.meeting_modes = [MeetingMode.GOOGLE_MEET.value]
    db.commit()
    appointment = _create(
        db,
        test_org.id,
        test_user.id,
        appointment_type.id,
        start,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
    )
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert appointment.google_sync_state == "unlinked"
    assert appointment.google_event_id is None
    assert (
        db.query(AppointmentEmailLog)
        .filter(
            AppointmentEmailLog.organization_id == test_org.id,
            AppointmentEmailLog.appointment_id == appointment.id,
            AppointmentEmailLog.email_type == "confirmed",
        )
        .count()
        == 1
    )


def test_complete_booking_is_revision_fenced(db, test_org, test_user, booking_type, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment = scheduling_v2_service.approve_booking(
        db,
        appointment,
        approved_by_user_id=test_user.id,
        expected_revision=1,
        request_id="approve-complete",
    )
    appointment = scheduling_v2_service.complete_booking(
        db,
        appointment,
        status=AppointmentStatus.COMPLETED.value,
        actor_user_id=test_user.id,
        expected_revision=2,
        request_id="complete-one",
    )
    assert appointment.status == AppointmentStatus.COMPLETED.value
    assert appointment.revision == 3
    replay = scheduling_v2_service.complete_booking(
        db,
        appointment,
        status=AppointmentStatus.COMPLETED.value,
        actor_user_id=test_user.id,
        expected_revision=2,
        request_id="complete-one",
    )
    assert replay._scheduling_replay_result["revision"] == 3


@pytest.mark.asyncio
async def test_retry_route_commits_exact_receipt_once(
    authed_client, db, test_org, test_user, booking_type, monkeypatch
):
    from app.db.models import SchedulingRequestReceipt
    from app.services import appointment_google_sync_service

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment.google_sync_state = "failed"
    db.commit()
    calls = []

    def retry(_db, current, *, commit=True):
        assert commit is False
        calls.append(current.id)
        current.google_sync_state = "pending"

    monkeypatch.setattr(appointment_google_sync_service, "retry", retry)
    payload = {"expected_revision": 1, "request_id": "retry-once"}
    first = await authed_client.post(f"/appointments/{appointment.id}/sync/retry", json=payload)
    second = await authed_client.post(f"/appointments/{appointment.id}/sync/retry", json=payload)
    assert first.status_code == second.status_code == 200
    assert len(calls) == 1
    assert (
        db.query(SchedulingRequestReceipt)
        .filter(
            SchedulingRequestReceipt.organization_id == test_org.id,
            SchedulingRequestReceipt.request_key == "retry-once",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_resolve_route_commits_exact_receipt_after_preflight(
    authed_client, db, test_org, test_user, booking_type, monkeypatch
):
    from app.db.models import SchedulingRequestReceipt
    from app.services import appointment_google_sync_service

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment.google_sync_state = "conflict"
    appointment.google_conflict = {"remote": {"etag": "etag-one"}, "observed_revision": 1}
    db.commit()
    calls = []

    def resolve(_db, current, *, commit=True, **_kwargs):
        assert commit is False
        calls.append(current.id)
        appointment_id = current.id
        _db.expire_all()
        refreshed = (
            _db.query(Appointment).filter(Appointment.id == appointment_id).with_for_update().one()
        )
        refreshed.google_sync_state = "completed"
        refreshed.google_conflict = None
        refreshed.revision += 1

    monkeypatch.setattr(appointment_google_sync_service, "resolve_conflict", resolve)
    payload = {
        "expected_revision": 1,
        "expected_etag": "etag-one",
        "resolution": "crm",
        "request_id": "resolve-once",
    }
    first = await authed_client.post(f"/appointments/{appointment.id}/sync/resolve", json=payload)
    second = await authed_client.post(f"/appointments/{appointment.id}/sync/resolve", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["scheduling"]["revision"] == 2
    assert second.json()["scheduling"]["revision"] == 2
    assert len(calls) == 1
    assert (
        db.query(SchedulingRequestReceipt)
        .filter(
            SchedulingRequestReceipt.organization_id == test_org.id,
            SchedulingRequestReceipt.request_key == "resolve-once",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_public_cancel_response_after_reschedule_replay_is_current(
    client, db, test_org, test_user, booking_type, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment = scheduling_v2_service.approve_booking(
        db,
        appointment,
        approved_by_user_id=test_user.id,
        expected_revision=1,
        request_id="public-approve",
    )
    old_token = appointment.reschedule_token
    payload = {
        "scheduled_start": (start + timedelta(days=7)).isoformat(),
        "expected_revision": 2,
        "request_id": "public-move",
    }
    url = f"/book/self-service/{test_org.id}/reschedule/{old_token}"
    first = await client.post(url, json=payload)
    replay = await client.post(url, json=payload)
    assert first.status_code == replay.status_code == 200
    assert first.json()["scheduling"]["revision"] == 3
    db.refresh(appointment)
    cancel = await client.post(
        f"/book/self-service/{test_org.id}/cancel/{appointment.cancel_token}",
        json={"reason": "Client requested", "expected_revision": 3, "request_id": "public-cancel"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == AppointmentStatus.CANCELLED.value
    assert cancel.json()["scheduling"]["revision"] == 4


@pytest.mark.asyncio
async def test_new_staff_mutations_hide_other_organization_appointment(
    authed_client, db, test_org, test_user, booking_type, monkeypatch
):
    from app.db.models import Organization, User

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    _, start = booking_type
    other_org = Organization(
        name="Scheduling other tenant", slug=f"scheduling-other-{uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    other_user = User(
        email=f"scheduling-other-{uuid4().hex[:8]}@example.com",
        display_name="Other tenant user",
        is_active=True,
    )
    db.add(other_user)
    db.flush()
    db.add(Membership(user_id=other_user.id, organization_id=other_org.id, role=Role.DEVELOPER))
    other_appointment = Appointment(
        organization_id=other_org.id,
        user_id=other_user.id,
        client_name="Other tenant",
        client_email="other-tenant@example.com",
        client_phone="555-0101",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
        revision=1,
    )
    db.add(other_appointment)
    db.commit()
    for action, payload in (
        ("complete", {"status": "completed", "expected_revision": 1, "request_id": "xorg-1"}),
        ("sync/retry", {"expected_revision": 1, "request_id": "xorg-2"}),
        (
            "sync/resolve",
            {
                "resolution": "crm",
                "expected_revision": 1,
                "expected_etag": "etag",
                "request_id": "xorg-3",
            },
        ),
    ):
        response = await authed_client.post(
            f"/appointments/{other_appointment.id}/{action}", json=payload
        )
        assert response.status_code == 404


def test_legacy_linked_google_row_has_no_v2_mutation_capability(
    db, test_org, test_user, booking_type, monkeypatch
):
    from app.services import appointment_service

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = Appointment(
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appointment_type.id,
        client_name="Legacy link",
        client_email="legacy-link@example.com",
        client_phone="555-0102",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
        status=AppointmentStatus.CONFIRMED.value,
        origin="legacy_unknown",
        google_event_id="legacy-event",
        google_sync_state="completed",
    )
    db.add(appointment)
    db.commit()
    read = appointment_service.scheduling_read(db, appointment, can_edit=True)
    assert read.google_sync.error_code == "legacy_ownership_requires_review"
    assert not read.capabilities.can_reschedule
    assert not read.capabilities.can_cancel
    assert not read.capabilities.can_retry_google_sync
    assert not read.capabilities.can_resolve_google_conflict


@pytest.mark.asyncio
async def test_completion_route_requires_csrf(
    authed_client, db, test_org, test_user, booking_type, monkeypatch
):
    from app.core.csrf import CSRF_HEADER

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    appointment_type, start = booking_type
    appointment = _create(db, test_org.id, test_user.id, appointment_type.id, start)
    appointment = scheduling_v2_service.approve_booking(
        db,
        appointment,
        approved_by_user_id=test_user.id,
        expected_revision=1,
        request_id="approve-csrf",
    )
    response = await authed_client.post(
        f"/appointments/{appointment.id}/complete",
        json={"status": "completed", "expected_revision": 2, "request_id": "csrf-denied"},
        headers={CSRF_HEADER: ""},
    )
    assert response.status_code == 403
    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CONFIRMED.value
