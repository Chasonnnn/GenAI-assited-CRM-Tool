"""Acceptance coverage for shared appointment change commands at existing HTTP boundaries."""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.db.enums import AppointmentStatus, MeetingMode, Role
from app.db.models import Appointment, AppointmentType, AuditLog, Job, Organization, UserIntegration
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, surrogate_service, surrogate_status_service


def _next_weekday_start(days_ahead: int = 7) -> datetime:
    start = (datetime.now(UTC) + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    while start.weekday() > 4:
        start += timedelta(days=1)
    return start


@pytest.fixture(autouse=True)
def suppress_delivery(monkeypatch):
    from app.services import appointment_email_service, notification_service

    for name in ("send_rescheduled", "send_cancelled"):
        monkeypatch.setattr(appointment_email_service, name, Mock())
    monkeypatch.setattr(notification_service, "notify_appointment_cancelled", Mock())


@pytest.fixture
def phone_appointment(db, test_org, test_user):
    from app.db.models import AvailabilityRule

    appointment_type = AppointmentType(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        name="Phone check-in",
        slug=f"phone-check-in-{uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        reminder_hours_before=0,
        is_active=True,
    )
    start = _next_weekday_start()
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
    appointment = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appointment_type.id,
        client_name="Scheduling QA",
        client_email=f"scheduling-{uuid4().hex[:8]}@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
        reschedule_token_expires_at=start + timedelta(days=7),
        cancel_token_expires_at=start + timedelta(days=7),
    )
    db.add(appointment)
    db.commit()
    return appointment


@pytest.fixture
def interview_appointment(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(full_name="Command Boundary Interview", email=f"{uuid4()}@example.com"),
    )
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    scheduled_stage = pipeline_service.get_stage_by_key(db, pipeline.id, "interview_scheduled")
    surrogate_status_service.change_status(
        db,
        surrogate,
        scheduled_stage.id,
        test_user.id,
        Role.DEVELOPER,
        interview_scheduled_at=_next_weekday_start(),
        trigger_workflows=False,
    )
    from app.services import surrogate_interview_appointment_service

    appointment = surrogate_interview_appointment_service.get_latest(db, test_org.id, surrogate.id)
    assert appointment is not None
    return surrogate, appointment


@pytest.fixture
def command_spy(monkeypatch):
    from app.services import appointment_command_service

    original = appointment_command_service.prepare_change
    calls = []

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(appointment_command_service, "prepare_change", record)
    return calls


def _interview_payload(surrogate, appointment, action, *, start=None, move_stage=False):
    return {
        "action": action,
        "move_stage": move_stage,
        "expected_stage_id": str(surrogate.stage_id),
        "expected_appointment_id": str(appointment.id),
        "expected_scheduled_start": appointment.scheduled_start.isoformat(),
        **({"scheduled_start": start.isoformat()} if start else {}),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["staff", "public", "interview"])
async def test_reschedule_http_surfaces_use_shared_command_and_preserve_shape(
    authed_client, client, db, phone_appointment, interview_appointment, command_spy, surface
):
    if surface == "interview":
        surrogate, appointment = interview_appointment
        original_stage_id = surrogate.stage_id
        target = appointment.scheduled_start + timedelta(days=7)
        response = await authed_client.post(
            f"/surrogates/{surrogate.id}/interview-appointment",
            json=_interview_payload(surrogate, appointment, "reschedule", start=target),
        )
        db.refresh(surrogate)
        assert surrogate.stage_id == original_stage_id
    else:
        appointment = phone_appointment
        target = appointment.scheduled_start + timedelta(days=7)
        if surface == "staff":
            response = await authed_client.post(
                f"/appointments/{appointment.id}/reschedule",
                json={"scheduled_start": target.isoformat()},
            )
        else:
            response = await client.post(
                f"/book/self-service/{appointment.organization_id}/reschedule/"
                f"{appointment.reschedule_token}",
                json={"scheduled_start": target.isoformat()},
            )

    assert response.status_code == 200, response.text
    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert appointment.scheduled_start == target
    assert appointment.scheduled_end == target + timedelta(minutes=appointment.duration_minutes)
    assert appointment.duration_minutes == 30
    assert appointment.reschedule_token is not None
    assert appointment.cancel_token is not None
    assert len(command_spy) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["staff", "public", "interview"])
async def test_cancel_http_surfaces_use_shared_command_and_preserve_lifecycle(
    authed_client, client, db, phone_appointment, interview_appointment, command_spy, surface
):
    if surface == "interview":
        surrogate, appointment = interview_appointment
        response = await authed_client.post(
            f"/surrogates/{surrogate.id}/interview-appointment",
            json=_interview_payload(surrogate, appointment, "cancel", move_stage=True),
        )
        db.refresh(surrogate)
        stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
        assert pipeline_service.get_stage_semantic_key(stage) == "reschedule_needed"
    else:
        appointment = phone_appointment
        if surface == "staff":
            response = await authed_client.post(
                f"/appointments/{appointment.id}/cancel", json={"reason": "Staff change"}
            )
        else:
            response = await client.post(
                f"/book/self-service/{appointment.organization_id}/cancel/{appointment.cancel_token}",
                json={"reason": "Client change"},
            )

    assert response.status_code == 200, response.text
    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CANCELLED.value
    assert appointment.cancelled_at is not None
    assert appointment.duration_minutes == 30
    assert appointment.reschedule_token is None
    assert appointment.cancel_token is None
    assert len(command_spy) == 1


@pytest.mark.asyncio
async def test_linked_staff_cancel_persists_one_google_intent_with_local_change(
    authed_client, db, phone_appointment, monkeypatch
):
    from app.services import appointment_google_sync_service

    integration = UserIntegration(
        user_id=phone_appointment.user_id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    phone_appointment.google_event_id = "linked-event"
    phone_appointment.google_calendar_id = "team-calendar"
    phone_appointment.google_account_email = integration.account_email
    phone_appointment.google_event_etag = '"etag-1"'
    db.add(integration)
    db.commit()

    monkeypatch.setattr(
        appointment_google_sync_service,
        "prepare_link",
        lambda _db, appointment: appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email=integration.account_email,
            calendar_id="team-calendar",
            event_id="linked-event",
            etag='"etag-1"',
            start=appointment.scheduled_start,
            end=appointment.scheduled_end,
        ),
    )

    response = await authed_client.post(
        f"/appointments/{phone_appointment.id}/cancel", json={"reason": "Staff change"}
    )

    assert response.status_code == 200, response.text
    db.refresh(phone_appointment)
    jobs = db.query(Job).filter_by(organization_id=phone_appointment.organization_id).all()
    assert phone_appointment.status == AppointmentStatus.CANCELLED.value
    assert phone_appointment.google_sync_state == "pending"
    assert len(jobs) == 1
    assert jobs[0].payload["appointment_id"] == str(phone_appointment.id)
    assert jobs[0].payload["action"] == "cancel"


@pytest.mark.asyncio
async def test_stale_provider_preflight_rejects_before_staff_cancel_local_writes(
    authed_client, db, phone_appointment, monkeypatch
):
    from app.services import appointment_google_sync_service

    integration = UserIntegration(
        user_id=phone_appointment.user_id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    phone_appointment.google_event_id = "linked-event"
    phone_appointment.google_calendar_id = "team-calendar"
    phone_appointment.google_account_email = integration.account_email
    phone_appointment.google_event_etag = '"etag-1"'
    db.add(integration)
    db.commit()
    original_start = phone_appointment.scheduled_start
    original_cancel_token = phone_appointment.cancel_token

    def preflight_that_races(_db, appointment):
        appointment.google_event_etag = '"etag-raced"'
        _db.flush()
        return appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email=integration.account_email,
            calendar_id="team-calendar",
            event_id="linked-event",
            etag='"etag-1"',
            start=original_start,
            end=original_start + timedelta(minutes=appointment.duration_minutes),
        )

    monkeypatch.setattr(appointment_google_sync_service, "prepare_link", preflight_that_races)
    response = await authed_client.post(
        f"/appointments/{phone_appointment.id}/cancel", json={"reason": "Staff change"}
    )

    assert response.status_code == 400
    db.refresh(phone_appointment)
    assert phone_appointment.status == AppointmentStatus.CONFIRMED.value
    assert phone_appointment.scheduled_start == original_start
    assert phone_appointment.cancel_token == original_cancel_token
    assert db.query(AuditLog).filter_by(target_id=phone_appointment.id).count() == 0
    assert db.query(Job).filter_by(organization_id=phone_appointment.organization_id).count() == 0


@pytest.mark.asyncio
async def test_buffer_change_during_preflight_rejects_before_staff_reschedule(
    authed_client, db, phone_appointment, monkeypatch
):
    from app.services import appointment_command_service

    original_prepare = appointment_command_service.prepare_change
    original_start = phone_appointment.scheduled_start
    target = original_start + timedelta(days=7)

    def preflight_that_changes_buffer(*args, **kwargs):
        prepared = original_prepare(*args, **kwargs)
        phone_appointment.buffer_after_minutes += 5
        db.flush()
        return prepared

    monkeypatch.setattr(
        appointment_command_service, "prepare_change", preflight_that_changes_buffer
    )
    response = await authed_client.post(
        f"/appointments/{phone_appointment.id}/reschedule",
        json={"scheduled_start": target.isoformat()},
    )

    assert response.status_code == 400
    db.refresh(phone_appointment)
    assert phone_appointment.scheduled_start == original_start
    assert phone_appointment.status == AppointmentStatus.CONFIRMED.value
    assert db.query(AuditLog).filter_by(target_id=phone_appointment.id).count() == 0


@pytest.mark.asyncio
async def test_interview_exact_retry_succeeds_after_interleaved_shared_preflight(
    authed_client, db, interview_appointment, monkeypatch
):
    from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
    from app.services import appointment_command_service, surrogate_interview_appointment_service

    surrogate, appointment = interview_appointment
    original_start = appointment.scheduled_start
    target = original_start + timedelta(days=7)
    data = SurrogateInterviewAppointmentAction(
        **_interview_payload(surrogate, appointment, "reschedule", start=target)
    )
    original_prepare = appointment_command_service.prepare_change
    interleaved = False

    def prepare_after_first_commit(db_session, preview, **kwargs):
        nonlocal interleaved
        prepared = original_prepare(db_session, preview, **kwargs)
        if not interleaved:
            interleaved = True
            surrogate_interview_appointment_service.manage(
                db_session,
                org_id=surrogate.organization_id,
                surrogate_id=surrogate.id,
                actor_user_id=appointment.user_id,
                actor_role=Role.DEVELOPER,
                data=data,
            )
        return prepared

    monkeypatch.setattr(appointment_command_service, "prepare_change", prepare_after_first_commit)
    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/interview-appointment", json=data.model_dump(mode="json")
    )

    assert response.status_code == 200, response.text
    db.refresh(appointment)
    assert appointment.scheduled_start == target
    assert db.query(AuditLog).filter_by(target_id=appointment.id).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["staff", "public"])
async def test_cross_org_routes_do_not_start_provider_preflight(
    authed_client, client, db, test_user, monkeypatch, surface
):
    from app.services import appointment_command_service

    other_org = Organization(name="Other scheduling org", slug=f"other-{uuid4().hex}")
    appointment = Appointment(
        organization=other_org,
        user_id=test_user.id,
        client_name="Other org appointment",
        client_email=f"other-{uuid4().hex[:8]}@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=_next_weekday_start(),
        scheduled_end=_next_weekday_start() + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_event_id="must-not-preflight",
        cancel_token=f"cancel-{uuid4().hex}",
    )
    db.add(appointment)
    db.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("provider preflight must not run for a denied appointment")

    monkeypatch.setattr(appointment_command_service, "prepare_change", fail_if_called)
    if surface == "staff":
        response = await authed_client.post(f"/appointments/{appointment.id}/cancel", json={})
    else:
        response = await client.post(
            f"/book/self-service/{uuid4()}/cancel/{appointment.cancel_token}", json={}
        )

    assert response.status_code == 404


@pytest.mark.parametrize("surface", ["booking", "interview"])
def test_later_workflow_failure_rolls_back_change_email_invalidation_and_google_intent(
    db, phone_appointment, interview_appointment, monkeypatch, surface
):
    from app.db.models import AppointmentEmailLog, EmailDelivery, EmailLog
    from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
    from app.services import (
        appointment_google_sync_service,
        appointment_service,
        surrogate_interview_appointment_service,
    )

    surrogate, interview = interview_appointment
    appointment = interview if surface == "interview" else phone_appointment
    integration = UserIntegration(
        user_id=appointment.user_id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    appointment.google_event_id = "atomic-event"
    db.add(integration)
    email = EmailLog(
        organization_id=appointment.organization_id,
        recipient_email="qa@example.com",
        subject="Appointment reminder",
        body="Test reminder",
        status="pending",
    )
    db.add(email)
    db.flush()
    delivery = EmailDelivery(
        organization_id=appointment.organization_id,
        email_log_id=email.id,
        provider="resend",
        provider_scope="org",
        provider_account_id=str(appointment.organization_id),
        idempotency_key=f"qa-reminder-{uuid4()}",
        request_fingerprint="a" * 64,
        status="pending",
    )
    appointment_email = AppointmentEmailLog(
        organization_id=appointment.organization_id,
        appointment_id=appointment.id,
        email_log_id=email.id,
        email_type="reminder",
        recipient_email="qa@example.com",
        subject="Appointment reminder",
        occurrence_key=f"qa-reminder-{uuid4()}",
        status="pending",
    )
    db.add_all([delivery, appointment_email])
    db.commit()
    initial_stage = surrogate.stage_id
    initial_token = appointment.cancel_token
    initial_audits = db.query(AuditLog).filter_by(target_id=appointment.id).count()
    monkeypatch.setattr(
        appointment_google_sync_service,
        "prepare_link",
        lambda _db, appt: appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email=integration.account_email,
            calendar_id="atomic-calendar",
            event_id="atomic-event",
            etag='"version-1"',
            start=appt.scheduled_start,
            end=appt.scheduled_end,
        ),
    )

    def fail_later_policy(*_args, **_kwargs):
        db.flush()
        assert appointment.status == "cancelled"
        assert delivery.status == "cancelled"
        assert db.query(Job).filter_by(job_type="appointment_google_sync").count() == 1
        raise RuntimeError("injected later workflow failure")

    if surface == "booking":
        monkeypatch.setattr(appointment_service, "_audit_record_appointment", fail_later_policy)
    else:
        monkeypatch.setattr(surrogate_status_service, "change_status", fail_later_policy)

    savepoint = db.begin_nested()
    with pytest.raises(RuntimeError, match="injected later workflow failure"):
        if surface == "booking":
            appointment_service.cancel_booking(db, appointment)
        else:
            surrogate_interview_appointment_service.manage(
                db,
                org_id=appointment.organization_id,
                surrogate_id=surrogate.id,
                actor_user_id=appointment.user_id,
                actor_role=Role.DEVELOPER,
                data=SurrogateInterviewAppointmentAction(
                    **_interview_payload(surrogate, appointment, "cancel", move_stage=True)
                ),
            )
    savepoint.rollback()
    db.expire_all()

    assert appointment.status == "confirmed"
    assert appointment.cancel_token == initial_token
    assert appointment.google_sync_revision == 0
    assert appointment.google_sync_state is None
    assert surrogate.stage_id == initial_stage
    assert delivery.status == "pending"
    assert email.status == "pending"
    assert appointment_email.status == "pending"
    assert db.query(AuditLog).filter_by(target_id=appointment.id).count() == initial_audits
    assert db.query(Job).filter_by(job_type="appointment_google_sync").count() == 0


@pytest.mark.parametrize("mode", ["zoom", "google_meet"])
def test_legacy_provider_creation_does_not_gain_an_appointment_row_lock(
    db, phone_appointment, monkeypatch, mode
):
    from sqlalchemy import event

    from app.services import appointment_integrations, appointment_service

    appointment = phone_appointment
    appointment.meeting_mode = mode
    db.commit()
    statements = []
    provider_calls = []
    connection = db.connection()

    def observe(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())

    def legacy_provider(_db, appt, *_args):
        assert not any("for update" in sql and "appointments" in sql for sql in statements)
        provider_calls.append(appt.id)
        if mode == "google_meet":
            appt.google_event_id = "new-legacy-event"
            appt.google_meet_url = "https://meet.google.com/abc-defg-hij"

    monkeypatch.setattr(
        appointment_integrations,
        "regenerate_zoom_meeting_on_reschedule" if mode == "zoom" else "create_google_meet_link",
        legacy_provider,
    )
    monkeypatch.setattr(appointment_integrations, "update_google_meet_event", Mock())
    event.listen(connection, "before_cursor_execute", observe)
    try:
        appointment_service.reschedule_booking(
            db, appointment, appointment.scheduled_start + timedelta(days=7)
        )
    finally:
        event.remove(connection, "before_cursor_execute", observe)
    assert provider_calls == [appointment.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("exact_retry", [True, False])
async def test_google_preflight_error_checks_committed_interview_receipt_first(
    authed_client, db, interview_appointment, monkeypatch, exact_retry
):
    from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
    from app.services import (
        appointment_google_sync_service,
        surrogate_interview_appointment_service,
    )

    surrogate, appointment = interview_appointment
    integration = UserIntegration(
        user_id=appointment.user_id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    appointment.google_event_id = "interleaved-event"
    db.add(integration)
    db.commit()
    target = appointment.scheduled_start + timedelta(days=7)
    outer = SurrogateInterviewAppointmentAction(
        **_interview_payload(surrogate, appointment, "reschedule", start=target)
    )
    winner = (
        outer
        if exact_retry
        else outer.model_copy(update={"scheduled_start": target + timedelta(hours=1)})
    )
    interleaved = False

    def race_preflight(db_session, appt):
        nonlocal interleaved
        if not interleaved:
            interleaved = True
            surrogate_interview_appointment_service.manage(
                db_session,
                org_id=surrogate.organization_id,
                surrogate_id=surrogate.id,
                actor_user_id=appointment.user_id,
                actor_role=Role.DEVELOPER,
                data=winner,
            )
            raise appointment_google_sync_service.GoogleLinkError(
                "Google event changed; review before editing", "conflict"
            )
        return appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email=integration.account_email,
            calendar_id="interleaved-calendar",
            event_id="interleaved-event",
            etag='"version-1"',
            start=appt.scheduled_start,
            end=appt.scheduled_end,
        )

    monkeypatch.setattr(appointment_google_sync_service, "prepare_link", race_preflight)
    response = await authed_client.post(
        f"/surrogates/{surrogate.id}/interview-appointment", json=outer.model_dump(mode="json")
    )
    assert response.status_code == (200 if exact_retry else 409), response.text
    if exact_retry:
        db.refresh(appointment)
        assert appointment.scheduled_start == target
        assert db.query(AuditLog).filter_by(target_id=appointment.id).count() == 1
        assert db.query(Job).filter_by(job_type="appointment_google_sync").count() == 1
