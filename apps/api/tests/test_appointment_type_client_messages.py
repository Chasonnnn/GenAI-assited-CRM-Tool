"""Per-appointment-type client message switches and templates."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


def _template(db, org_id, user_id, *, name, scope="org"):
    from app.services import email_service

    template = email_service.create_template(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=name,
        subject=f"{name} subject",
        body="<p>Hello {{full_name}}</p>",
        scope=scope,
        commit=False,
    )
    db.flush()
    return template


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


def _confirmed_appointment(db, org_id, user_id, *, client_messages=None):
    from app.db.enums import AppointmentStatus, MeetingMode
    from app.db.models import Appointment, AppointmentType

    appointment_type = AppointmentType(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        slug=f"consultation-{uuid4().hex[:8]}",
        name="Consultation",
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        reminder_hours_before=24,
        client_messages=client_messages or {},
        is_active=True,
    )
    scheduled_start = datetime.now(UTC) + timedelta(days=3)
    appointment = Appointment(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appointment_type.id,
        client_name="Appointment Client",
        client_email="client@example.com",
        client_phone="555-123-4567",
        client_timezone="America/New_York",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
        approved_at=datetime.now(UTC),
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
    )
    db.add_all([appointment_type, appointment])
    db.flush()
    return appointment


@pytest.mark.asyncio
async def test_owner_saves_switches_and_templates_per_message(authed_client, db, test_auth):
    template = _template(db, test_auth.org.id, test_auth.user.id, name="Consult confirmed")

    created = await authed_client.post(
        "/appointments/types",
        json={
            "name": "Consultation",
            "meeting_mode": "phone",
            "reminder_hours_before": 48,
            "client_messages": {
                "confirmed": {"enabled": True, "template_id": str(template.id)},
                "reminder": {"enabled": False, "template_id": None},
            },
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["reminder_hours_before"] == 48
    assert body["client_messages"] == {
        "request_received": {"enabled": True, "template_id": None},
        "confirmed": {"enabled": True, "template_id": str(template.id)},
        "reminder": {"enabled": False, "template_id": None},
        "rescheduled": {"enabled": True, "template_id": None},
        "cancelled": {"enabled": True, "template_id": None},
    }

    updated = await authed_client.patch(
        f"/appointments/types/{body['id']}",
        json={"client_messages": {"cancelled": {"enabled": False}}},
    )

    assert updated.status_code == 200, updated.text
    messages = updated.json()["client_messages"]
    assert messages["cancelled"] == {"enabled": False, "template_id": None}
    # A patch replaces the whole settings object.
    assert messages["confirmed"] == {"enabled": True, "template_id": None}

    listed = await authed_client.get("/appointments/types")
    assert listed.json()[0]["client_messages"]["cancelled"]["enabled"] is False


@pytest.mark.asyncio
async def test_rejects_templates_from_another_org_or_another_users_personal_library(
    authed_client, db, test_auth
):
    from app.db.enums import Role
    from app.db.models import Membership, Organization, User

    other_org = Organization(id=uuid4(), name="Other Org", slug=f"other-{uuid4().hex[:8]}")
    other_user = User(
        id=uuid4(),
        email=f"other-{uuid4().hex[:8]}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add_all([other_org, other_user])
    db.flush()
    db.add(
        Membership(
            id=uuid4(), user_id=other_user.id, organization_id=test_auth.org.id, role=Role.ADMIN
        )
    )
    db.flush()
    foreign = _template(db, other_org.id, other_user.id, name="Other org template")
    colleague_personal = _template(
        db, test_auth.org.id, other_user.id, name="Colleague template", scope="personal"
    )
    own_personal = _template(
        db, test_auth.org.id, test_auth.user.id, name="My template", scope="personal"
    )

    for template_id in (foreign.id, colleague_personal.id):
        response = await authed_client.post(
            "/appointments/types",
            json={
                "name": f"Rejected {template_id}",
                "meeting_mode": "phone",
                "client_messages": {"confirmed": {"template_id": str(template_id)}},
            },
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Email template not found"

    created = await authed_client.post(
        "/appointments/types",
        json={
            "name": "Personal template type",
            "meeting_mode": "phone",
            "client_messages": {"confirmed": {"template_id": str(own_personal.id)}},
        },
    )
    assert created.status_code == 201, created.text

    patched = await authed_client.patch(
        f"/appointments/types/{created.json()['id']}",
        json={"client_messages": {"reminder": {"template_id": str(foreign.id)}}},
    )
    assert patched.status_code == 400, patched.text


@pytest.mark.asyncio
async def test_rejects_unknown_message_keys_and_reminder_hours_of_zero(authed_client):
    unknown = await authed_client.post(
        "/appointments/types",
        json={
            "name": "Unknown message",
            "meeting_mode": "phone",
            "client_messages": {"follow_up": {"enabled": False}},
        },
    )
    zero_hours = await authed_client.post(
        "/appointments/types",
        json={"name": "No reminder", "meeting_mode": "phone", "reminder_hours_before": 0},
    )

    assert unknown.status_code == 422
    assert zero_hours.status_code == 422


def test_disabled_message_is_not_queued(db, test_org, test_user):
    from app.db.enums import AppointmentEmailType
    from app.db.models import AppointmentEmailLog
    from app.services import appointment_email_service

    _configure_resend(db, test_org.id)
    appointment = _confirmed_appointment(
        db,
        test_org.id,
        test_user.id,
        client_messages={"confirmed": {"enabled": False, "template_id": None}},
    )

    result = appointment_email_service.send_appointment_email(
        db, appointment, AppointmentEmailType.CONFIRMED, "https://portal.example.com"
    )
    cancelled = appointment_email_service.send_appointment_email(
        db, appointment, AppointmentEmailType.CANCELLED, "https://portal.example.com"
    )

    assert result is None
    assert cancelled is not None
    assert (
        db.query(AppointmentEmailLog)
        .filter(AppointmentEmailLog.appointment_id == appointment.id)
        .one()
        .email_type
        == AppointmentEmailType.CANCELLED.value
    )


def test_chosen_template_is_used_and_falls_back_to_default_when_inactive(db, test_org, test_user):
    from app.db.enums import AppointmentEmailType
    from app.db.models import EmailLog
    from app.services import appointment_email_service

    _configure_resend(db, test_org.id)
    chosen = _template(db, test_org.id, test_user.id, name="Consult confirmed")
    appointment = _confirmed_appointment(
        db,
        test_org.id,
        test_user.id,
        client_messages={"confirmed": {"enabled": True, "template_id": str(chosen.id)}},
    )

    first = appointment_email_service.send_appointment_email(
        db, appointment, AppointmentEmailType.CONFIRMED, "https://portal.example.com"
    )
    assert first is not None
    assert db.get(EmailLog, first.email_log_id).template_id == chosen.id
    assert first.subject == "Consult confirmed subject"

    chosen.is_active = False
    db.flush()
    later = _confirmed_appointment(
        db,
        test_org.id,
        test_user.id,
        client_messages={"confirmed": {"enabled": True, "template_id": str(chosen.id)}},
    )
    default_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.CONFIRMED
    )
    second = appointment_email_service.send_appointment_email(
        db, later, AppointmentEmailType.CONFIRMED, "https://portal.example.com"
    )
    assert second is not None
    assert db.get(EmailLog, second.email_log_id).template_id == default_id


def test_queued_reminder_is_not_delivered_after_the_reminder_is_turned_off(db, test_org, test_user):
    from app.db.models import AppointmentType
    from app.services import appointment_email_service

    _configure_resend(db, test_org.id)
    appointment = _confirmed_appointment(db, test_org.id, test_user.id)
    reminder = appointment_email_service.schedule_reminder_email(
        db, appointment, "https://portal.example.com", hours_before=24
    )
    assert reminder is not None
    assert appointment_email_service.is_appointment_email_delivery_eligible(
        db, test_org.id, reminder.id
    )

    appointment_type = db.get(AppointmentType, appointment.appointment_type_id)
    appointment_type.client_messages = {"reminder": {"enabled": False, "template_id": None}}
    db.flush()

    assert not appointment_email_service.is_appointment_email_delivery_eligible(
        db, test_org.id, reminder.id
    )
