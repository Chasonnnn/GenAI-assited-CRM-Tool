"""Tests for template variable builders."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.models import Appointment, AppointmentType, BookingLink, FormSubmissionToken
from app.db.enums import AppointmentStatus, MeetingMode
from app.services import form_service
from app.services import form_submission_service
from app.services import org_service
from app.services import email_service
from app.services import appointment_service
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service
from app.db.enums import SurrogateSource


def _create_published_form(db, org_id, user_id):
    form = form_service.create_form(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name="Application Form",
        description="Candidate application",
        schema={"pages": [{"title": "Basics", "fields": []}]},
        max_file_size_bytes=None,
        max_file_count=None,
        allowed_mime_types=None,
    )
    return form_service.publish_form(db, form, user_id)


def test_build_surrogate_template_variables_includes_unsubscribe(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Test User",
            email="user@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    assert "unsubscribe_url" in variables
    assert variables["unsubscribe_url"].startswith(
        f"https://{test_org.slug}.surrogacyforce.com/email/unsubscribe/"
    )


def test_build_surrogate_template_variables_includes_form_link(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Form Link User",
            email="form-link@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )
    created_form = _create_published_form(db, test_org.id, test_user.id)

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    assert "form_link" in variables
    base_url = org_service.get_org_portal_base_url(test_org)
    assert variables["form_link"].startswith(f"{base_url}/apply/")

    issued_token = variables["form_link"].removeprefix(f"{base_url}/apply/")
    token_row = (
        db.query(FormSubmissionToken).filter(FormSubmissionToken.token == issued_token).first()
    )
    assert token_row is not None
    assert token_row.form_id == created_form.id
    assert token_row.surrogate_id == surrogate.id


def test_build_surrogate_template_variables_includes_appointment_link(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Appointment Link User",
            email="appointment-link@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    assert "appointment_link" in variables
    base_url = org_service.get_org_portal_base_url(test_org)
    assert variables["appointment_link"].startswith(f"{base_url}/book/")

    issued_slug = variables["appointment_link"].removeprefix(f"{base_url}/book/")
    link_row = db.query(BookingLink).filter(BookingLink.public_slug == issued_slug).first()
    assert link_row is not None
    assert link_row.user_id == test_user.id
    assert link_row.organization_id == test_org.id


def test_build_surrogate_template_variables_reuses_existing_form_link(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Reuse User",
            email="reuse@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )
    form = _create_published_form(db, test_org.id, test_user.id)

    existing_token = form_submission_service.create_submission_token(
        db=db,
        org_id=test_org.id,
        form=form,
        surrogate=surrogate,
        user_id=test_user.id,
        expires_in_days=14,
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    base_url = org_service.get_org_portal_base_url(test_org)
    assert variables["form_link"] == f"{base_url}/apply/{existing_token.token}"
    token_count = (
        db.query(FormSubmissionToken)
        .filter(
            FormSubmissionToken.organization_id == test_org.id,
            FormSubmissionToken.form_id == form.id,
            FormSubmissionToken.surrogate_id == surrogate.id,
        )
        .count()
    )
    assert token_count == 1


def test_build_surrogate_template_variables_form_link_empty_without_published_form(
    db, test_org, test_user
):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="No Form User",
            email="no-form@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    assert variables["form_link"] == ""


def test_build_surrogate_template_variables_reuses_existing_appointment_link(
    db, test_org, test_user
):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Reuse Appointment User",
            email="reuse-appointment@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )
    existing_link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=test_user.id,
        org_id=test_org.id,
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    base_url = org_service.get_org_portal_base_url(test_org)
    assert variables["appointment_link"] == f"{base_url}/book/{existing_link.public_slug}"
    link_count = (
        db.query(BookingLink)
        .filter(
            BookingLink.organization_id == test_org.id,
            BookingLink.user_id == test_user.id,
        )
        .count()
    )
    assert link_count == 1


def test_build_surrogate_template_variables_includes_appointment_self_service_urls(
    db, test_org, test_user
):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Appointment Self-Service User",
            email="appointment-self-service@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    appt_type = AppointmentType(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        slug="self-service-links",
        name="Self Service Links",
        description=None,
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=5,
        meeting_mode=MeetingMode.ZOOM.value,
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appt_type.id,
        surrogate_id=surrogate.id,
        client_name=surrogate.full_name or "Client",
        client_email=surrogate.email or "client@example.com",
        client_phone="555-777-0000",
        client_timezone="America/New_York",
        scheduled_start=now + timedelta(days=2),
        scheduled_end=now + timedelta(days=2, minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=AppointmentStatus.CONFIRMED.value,
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
        reschedule_token_expires_at=now + timedelta(days=9),
        cancel_token_expires_at=now + timedelta(days=9),
    )
    db.add(appt)
    db.flush()

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    base_url = org_service.get_org_portal_base_url(test_org)
    assert variables["appointment_manage_url"] == (
        f"{base_url}/book/self-service/{test_org.id}/manage/{appt.reschedule_token}"
    )
    assert variables["appointment_reschedule_url"] == (
        f"{base_url}/book/self-service/{test_org.id}/reschedule/{appt.reschedule_token}"
    )
    assert variables["appointment_cancel_url"] == (
        f"{base_url}/book/self-service/{test_org.id}/cancel/{appt.cancel_token}"
    )
