"""Durable delivery contract for appointment notifications."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def _configure_resend(db, organization_id):
    from app.db.models import ResendSettings
    from app.services import resend_settings_service

    db.add(
        ResendSettings(
            organization_id=organization_id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="appointments@example.com",
            from_name="Appointments",
            verified_domain="example.com",
        )
    )
    db.flush()


def _create_confirmed_appointment(db, test_org, test_user):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType

    appointment_type = AppointmentType(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        slug=f"consultation-{uuid4().hex[:8]}",
        name="Consultation",
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        is_active=True,
    )
    approved_at = datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)
    scheduled_start = approved_at + timedelta(days=2)
    appointment = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appointment_type.id,
        client_name="Appointment Client",
        client_email="client@example.com",
        client_phone="555-123-4567",
        client_timezone="America/New_York",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=AppointmentStatus.CONFIRMED.value,
        approved_at=approved_at,
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
    )
    db.add_all([appointment_type, appointment])
    db.flush()
    return appointment


def _prepare_future_reminder_schedule(db, appointment):
    from datetime import time
    from zoneinfo import ZoneInfo

    from app.db.enums import MeetingMode
    from app.db.models import AvailabilityRule

    client_tz = ZoneInfo(appointment.client_timezone)
    local_today = datetime.now(client_tz).date()
    days_until_monday = (7 - local_today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    old_date = local_today + timedelta(days=days_until_monday + 7)
    new_date = old_date + timedelta(days=7)
    old_start = datetime.combine(old_date, time(10, 0), tzinfo=client_tz).astimezone(timezone.utc)
    new_start = datetime.combine(new_date, time(10, 0), tzinfo=client_tz).astimezone(timezone.utc)

    appointment.scheduled_start = old_start
    appointment.scheduled_end = old_start + timedelta(minutes=appointment.duration_minutes)
    appointment.meeting_mode = MeetingMode.PHONE.value
    appointment.appointment_type.meeting_mode = MeetingMode.PHONE.value
    appointment.appointment_type.meeting_modes = [MeetingMode.PHONE.value]
    appointment.appointment_type.reminder_hours_before = 24
    db.add(
        AvailabilityRule(
            id=uuid4(),
            organization_id=appointment.organization_id,
            user_id=appointment.user_id,
            day_of_week=new_date.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone=appointment.client_timezone,
        )
    )
    db.commit()
    db.refresh(appointment)
    return old_start, new_start


def test_confirmed_email_reuses_one_pending_delivery_occurrence(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailDeliveryStatus, EmailStatus
    from app.db.models import AppointmentEmailLog, EmailDelivery, EmailLog
    from app.services import appointment_email_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)

    first = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    repeated = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )

    assert first is not None
    assert repeated is not None
    assert repeated.id == first.id
    assert first.status == EmailStatus.PENDING.value
    assert first.sent_at is None
    assert first.external_message_id is None
    assert first.occurrence_key.startswith(f"appointment-email/{appointment.id}/confirmed/")
    assert first.email_log_id is not None

    email_log = db.get(EmailLog, first.email_log_id)
    assert email_log is not None
    assert email_log.source_type == "appointment_email"
    assert email_log.source_id == first.id
    assert email_log.idempotency_key == first.occurrence_key
    assert email_log.status == EmailStatus.PENDING.value

    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == email_log.id,
        )
        .one()
    )
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert (
        db.query(AppointmentEmailLog)
        .filter(
            AppointmentEmailLog.organization_id == test_org.id,
            AppointmentEmailLog.occurrence_key == first.occurrence_key,
        )
        .count()
        == 1
    )


def test_provider_acceptance_marks_appointment_email_sent_with_resend_id(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None

    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        lease_for=timedelta(minutes=1),
    )
    claim = next(claim for claim in claims if claim.email_log_id == appointment_log.email_log_id)
    accepted_at = datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc)

    email_delivery_service.record_delivery_success(
        db,
        claim=claim,
        provider_message_id="resend-message-123",
        now=accepted_at,
    )

    db.refresh(appointment_log)
    assert appointment_log.status == EmailStatus.SENT.value
    assert appointment_log.sent_at == accepted_at
    assert appointment_log.external_message_id == "resend-message-123"
    assert appointment_log.error is None


def test_terminal_delivery_failure_marks_appointment_email_failed(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None

    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        lease_for=timedelta(minutes=1),
    )
    claim = next(claim for claim in claims if claim.email_log_id == appointment_log.email_log_id)

    email_delivery_service.record_delivery_failure(
        db,
        claim=claim,
        retryable=False,
        error_type="validation_error",
        error_message="Provider rejected the sender",
        provider_http_status=422,
        now=datetime(2026, 7, 23, 15, 5, tzinfo=timezone.utc),
    )

    db.refresh(appointment_log)
    assert appointment_log.status == EmailStatus.FAILED.value
    assert appointment_log.sent_at is None
    assert appointment_log.external_message_id is None
    assert appointment_log.error == "Provider rejected the sender"


def test_final_expired_lease_marks_appointment_email_for_reconciliation(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailDeliveryStatus, EmailStatus
    from app.db.models import EmailDelivery
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == appointment_log.email_log_id,
        )
        .one()
    )
    delivery.max_attempts = 1
    db.commit()

    claimed_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=claimed_at,
        lease_for=timedelta(seconds=1),
    )
    assert any(claim.email_log_id == appointment_log.email_log_id for claim in claims)

    email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-recovery-worker",
        now=claimed_at + timedelta(seconds=2),
        lease_for=timedelta(minutes=1),
    )

    db.refresh(delivery)
    db.refresh(appointment_log)
    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert appointment_log.status == EmailStatus.PENDING.value
    assert appointment_log.sent_at is None
    assert appointment_log.external_message_id is None
    assert appointment_log.error == (
        "Delivery lease expired after the final attempt; provider outcome is unknown "
        "and operator reconciliation is required"
    )


def test_suppressed_appointment_email_is_atomically_recorded_as_skipped(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.db.models import EmailDelivery, EmailSuppression
    from app.services import appointment_email_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email=appointment.client_email,
            reason="complaint",
        )
    )
    db.flush()

    first = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    repeated = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )

    assert first is not None
    assert repeated is not None
    assert repeated.id == first.id
    assert first.status == EmailStatus.SKIPPED.value
    assert first.error == "suppressed"
    assert first.sent_at is None
    assert first.external_message_id is None
    assert (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == first.email_log_id,
        )
        .count()
        == 0
    )


def test_dispatch_time_suppression_marks_appointment_email_skipped(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None

    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        lease_for=timedelta(minutes=1),
    )
    claim = next(claim for claim in claims if claim.email_log_id == appointment_log.email_log_id)

    email_delivery_service.record_delivery_suppressed(
        db,
        claim=claim,
        now=datetime(2026, 7, 23, 15, 10, tzinfo=timezone.utc),
    )

    db.refresh(appointment_log)
    assert appointment_log.status == EmailStatus.SKIPPED.value
    assert appointment_log.sent_at is None
    assert appointment_log.external_message_id is None
    assert appointment_log.error == "suppressed"


def test_cancelled_delivery_projects_the_canonical_reason_message(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None
    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        lease_for=timedelta(minutes=1),
    )
    claim = next(claim for claim in claims if claim.email_log_id == appointment_log.email_log_id)

    email_delivery_service.record_delivery_cancelled(
        db,
        claim=claim,
        reason_type="credential_revoked",
        reason_message="The configured Resend credential was revoked",
        now=datetime(2026, 7, 23, 15, 15, tzinfo=timezone.utc),
    )

    db.refresh(appointment_log)
    assert appointment_log.status == EmailStatus.SKIPPED.value
    assert appointment_log.error == "The configured Resend credential was revoked"


def test_reconciliation_required_projects_operator_diagnostic(
    db,
    test_org,
    test_user,
):
    from app.db.enums import AppointmentEmailType, EmailStatus
    from app.services import appointment_email_service, email_delivery_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    appointment_log = appointment_email_service.send_appointment_email(
        db,
        appointment,
        AppointmentEmailType.CONFIRMED,
        "https://portal.example.com",
    )
    assert appointment_log is not None
    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-test-worker",
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        lease_for=timedelta(minutes=1),
    )
    claim = next(claim for claim in claims if claim.email_log_id == appointment_log.email_log_id)

    email_delivery_service.record_delivery_reconciliation_required(
        db,
        claim=claim,
        error_type="ambiguous_provider_response",
        error_message="Provider acceptance could not be confirmed; reconcile before retrying",
        provider_http_status=202,
        now=datetime(2026, 7, 23, 15, 20, tzinfo=timezone.utc),
    )

    db.refresh(appointment_log)
    assert appointment_log.status == EmailStatus.PENDING.value
    assert (
        appointment_log.error
        == "Provider acceptance could not be confirmed; reconcile before retrying"
    )
    assert appointment_log.sent_at is None
    assert appointment_log.external_message_id is None


@pytest.mark.parametrize("queued_status", ["pending", "retry_scheduled"])
def test_confirmed_reschedule_replaces_pending_or_retry_reminder_occurrence(
    db,
    test_org,
    test_user,
    queued_status,
):
    from app.db.enums import EmailDeliveryStatus, EmailStatus
    from app.db.models import AppointmentEmailLog, EmailDelivery, EmailLog
    from app.services import appointment_email_service, appointment_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    old_start, new_start = _prepare_future_reminder_schedule(db, appointment)
    old_reminder = appointment_email_service.schedule_reminder_email(
        db,
        appointment,
        "https://portal.example.com",
        hours_before=24,
    )
    assert old_reminder is not None
    old_delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == old_reminder.email_log_id,
        )
        .one()
    )
    old_delivery.status = queued_status
    db.commit()

    appointment_service.reschedule_booking(
        db,
        appointment,
        new_start,
        by_client=False,
    )

    db.refresh(old_delivery)
    db.refresh(old_reminder)
    old_email_log = db.get(EmailLog, old_reminder.email_log_id)
    assert old_delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert old_delivery.last_error_type == "appointment_rescheduled"
    assert old_reminder.status == EmailStatus.SKIPPED.value
    assert old_reminder.error == "Appointment was rescheduled"
    assert old_email_log is not None
    assert old_email_log.status == EmailStatus.SKIPPED.value
    assert old_email_log.error == "Appointment was rescheduled"

    reminders = (
        db.query(AppointmentEmailLog)
        .filter(
            AppointmentEmailLog.organization_id == test_org.id,
            AppointmentEmailLog.appointment_id == appointment.id,
            AppointmentEmailLog.email_type == "reminder",
        )
        .order_by(AppointmentEmailLog.created_at, AppointmentEmailLog.id)
        .all()
    )
    assert len(reminders) == 2
    replacement = next(reminder for reminder in reminders if reminder.id != old_reminder.id)
    replacement_delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == replacement.email_log_id,
        )
        .one()
    )
    assert replacement.status == EmailStatus.PENDING.value
    assert replacement_delivery.status == EmailDeliveryStatus.PENDING.value
    assert replacement_delivery.run_at == new_start - timedelta(hours=24)
    assert replacement.occurrence_key != old_reminder.occurrence_key
    assert old_start != new_start


@pytest.mark.parametrize("queued_status", ["pending", "retry_scheduled"])
def test_appointment_cancellation_cancels_pending_or_retry_reminder(
    db,
    test_org,
    test_user,
    queued_status,
):
    from app.db.enums import EmailDeliveryStatus, EmailStatus
    from app.db.models import EmailDelivery, EmailLog
    from app.services import appointment_email_service, appointment_service

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    _prepare_future_reminder_schedule(db, appointment)
    reminder = appointment_email_service.schedule_reminder_email(
        db,
        appointment,
        "https://portal.example.com",
        hours_before=24,
    )
    assert reminder is not None
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == reminder.email_log_id,
        )
        .one()
    )
    delivery.status = queued_status
    db.commit()

    appointment_service.cancel_booking(
        db,
        appointment,
        reason="Client cancelled",
        by_client=False,
    )

    db.refresh(delivery)
    db.refresh(reminder)
    email_log = db.get(EmailLog, reminder.email_log_id)
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "appointment_cancelled"
    assert reminder.status == EmailStatus.SKIPPED.value
    assert reminder.error == "Appointment was cancelled"
    assert email_log is not None
    assert email_log.status == EmailStatus.SKIPPED.value
    assert email_log.error == "Appointment was cancelled"


@pytest.mark.parametrize("transition", ["cancelled", "rescheduled"])
def test_leased_stale_reminder_fails_final_tenant_scoped_eligibility(
    db,
    test_org,
    test_user,
    transition,
):
    from app.db.enums import EmailDeliveryStatus
    from app.db.models import EmailDelivery
    from app.services import (
        appointment_email_service,
        appointment_service,
        email_delivery_service,
    )

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    _old_start, new_start = _prepare_future_reminder_schedule(db, appointment)
    reminder = appointment_email_service.schedule_reminder_email(
        db,
        appointment,
        "https://portal.example.com",
        hours_before=24,
    )
    assert reminder is not None
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == reminder.email_log_id,
        )
        .one()
    )
    claims = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="leased-reminder-worker",
        now=delivery.run_at + timedelta(seconds=1),
        lease_for=timedelta(minutes=5),
    )
    assert any(claim.delivery_id == delivery.id for claim in claims)
    assert appointment_email_service.is_appointment_email_delivery_eligible(
        db,
        test_org.id,
        reminder.id,
    )

    if transition == "cancelled":
        appointment_service.cancel_booking(
            db,
            appointment,
            reason="Client cancelled",
            by_client=False,
        )
    else:
        appointment_service.reschedule_booking(
            db,
            appointment,
            new_start,
            by_client=False,
        )

    db.refresh(delivery)
    assert delivery.status == EmailDeliveryStatus.LEASED.value
    assert not appointment_email_service.is_appointment_email_delivery_eligible(
        db,
        test_org.id,
        reminder.id,
    )
    assert not appointment_email_service.is_appointment_email_delivery_eligible(
        db,
        uuid4(),
        reminder.id,
    )


@pytest.mark.asyncio
async def test_dispatcher_rechecks_appointment_reminder_after_provider_admission_wait(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from types import SimpleNamespace

    from app.db.enums import EmailDeliveryStatus, EmailStatus
    from app.db.models import EmailDelivery, EmailLog
    from app.services import (
        appointment_email_service,
        appointment_service,
        email_delivery_dispatch,
        email_delivery_service,
    )
    from app.services.resend_transport import ResendSendResult

    _configure_resend(db, test_org.id)
    appointment = _create_confirmed_appointment(db, test_org, test_user)
    _prepare_future_reminder_schedule(db, appointment)
    reminder = appointment_email_service.schedule_reminder_email(
        db,
        appointment,
        "https://portal.example.com",
        hours_before=24,
    )
    assert reminder is not None
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == reminder.email_log_id,
        )
        .one()
    )
    claim = email_delivery_service.claim_due_deliveries(
        db,
        worker_id="appointment-dispatch-worker",
        now=delivery.run_at + timedelta(seconds=1),
        lease_for=timedelta(minutes=5),
        limit=1,
    )[0]
    provider_called = False

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(
            send_at=datetime.now(timezone.utc) + timedelta(seconds=1)
        ),
    )

    async def cancel_during_wait(_delay_seconds: float) -> None:
        appointment_service.cancel_booking(
            db,
            appointment,
            reason="Client cancelled",
            by_client=False,
        )

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    result = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=cancel_during_wait,
    )

    assert provider_called is False
    assert result.status == EmailDeliveryStatus.CANCELLED.value
    assert result.last_error_type == "appointment_ineligible"
    db.expire_all()
    email_log = db.get(EmailLog, reminder.email_log_id)
    assert email_log is not None
    assert email_log.status == EmailStatus.SKIPPED.value
