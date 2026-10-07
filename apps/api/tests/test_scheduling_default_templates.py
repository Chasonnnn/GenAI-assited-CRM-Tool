"""Scheduling's default client email templates have readable names and are found by system key."""

import uuid

import pytest

from app.db.enums import AppointmentEmailType, Role
from app.db.models import EmailTemplate
from app.services import appointment_email_service, email_service
from tests.test_email_templates_personal_scope import authed_client_for_user, create_user_with_role


def test_default_template_gets_a_readable_name_and_a_system_key(db, test_org, test_user):
    template_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.CONFIRMED
    )

    template = db.get(EmailTemplate, template_id)
    assert template.name == "Booking Confirmed"
    assert template.system_key == "scheduling_confirmed"
    assert template.scope == "org"
    assert not template.name.startswith("appointment_")


def test_a_renamed_default_template_is_still_found(db, test_org, test_user):
    first_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.REMINDER
    )
    db.get(EmailTemplate, first_id).name = "Your visit is coming up"
    db.flush()

    again = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.REMINDER
    )

    assert again == first_id
    assert (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == test_org.id,
            EmailTemplate.system_key == "scheduling_reminder",
        )
        .count()
        == 1
    )


def test_an_org_template_with_the_readable_name_is_left_alone(db, test_org, test_user):
    own = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Booking Cancelled",
        subject="Our own cancellation note",
        body="<p>See you another time.</p>",
    )

    default_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.CANCELLED
    )

    assert default_id != own.id
    assert db.get(EmailTemplate, default_id).name == "Booking Cancelled (Scheduling)"
    assert own.system_key is None


def test_the_fallback_name_skips_names_the_org_already_uses(db, test_org, test_user):
    for name in ("Booking Cancelled", "Booking Cancelled (Scheduling)"):
        email_service.create_template(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            name=name,
            subject="Our own cancellation note",
            body="<p>See you another time.</p>",
        )

    default_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.CANCELLED
    )

    assert db.get(EmailTemplate, default_id).name == "Booking Cancelled (Scheduling 2)"


def test_a_personal_template_does_not_take_the_readable_name(db, test_org, test_user):
    email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Booking Cancelled",
        subject="My own cancellation note",
        body="<p>See you another time.</p>",
        scope="personal",
    )

    default_id = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.CANCELLED
    )

    assert db.get(EmailTemplate, default_id).name == "Booking Cancelled"


def test_default_templates_stay_per_org(db, test_org, test_user):
    from app.db.models import Organization

    other_org = Organization(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    ours = appointment_email_service.get_or_create_template(
        db, test_org.id, test_user.id, AppointmentEmailType.RESCHEDULED
    )
    theirs = appointment_email_service.get_or_create_template(
        db, other_org.id, test_user.id, AppointmentEmailType.RESCHEDULED
    )

    assert ours != theirs
    assert db.get(EmailTemplate, theirs).organization_id == other_org.id


@pytest.mark.asyncio
async def test_template_library_lists_default_templates_but_manual_compose_hides_them(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)
    for email_type in AppointmentEmailType:
        appointment_email_service.get_or_create_template(db, test_org.id, admin.id, email_type)
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        library = await client.get("/email-templates?scope=org")
        manual = await client.get("/email-templates?scope=org&usage_context=manual")

    assert library.status_code == 200
    keys_by_name = {item["name"]: item["system_key"] for item in library.json()}
    assert keys_by_name["Booking Request Received"] == "scheduling_request_received"
    assert keys_by_name["Booking Reminder"] == "scheduling_reminder"
    assert not [name for name in keys_by_name if name.startswith("appointment_")]

    assert manual.status_code == 200
    manual_keys = {item["system_key"] for item in manual.json()}
    assert not {key for key in manual_keys if key and key.startswith("scheduling_")}
