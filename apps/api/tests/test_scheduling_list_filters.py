"""Task and appointment list filters used by the Tasks and Appointments toolbars."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.core.encryption import hash_email
from app.db.enums import AppointmentStatus, MeetingMode, Role, TaskType
from app.db.models import (
    Appointment,
    AppointmentType,
    Donor,
    Membership,
    Organization,
    Task,
    User,
)
from app.services import pipeline_service
from app.utils.normalization import normalize_email


def _other_org(db) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name="Other Scheduling Org",
        slug=f"other-scheduling-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


def _task(db, *, org_id, user_id, title: str, **overrides) -> Task:
    values = {
        "organization_id": org_id,
        "created_by_user_id": user_id,
        "owner_type": "user",
        "owner_id": user_id,
        "title": title,
        "task_type": TaskType.OTHER.value,
    }
    values.update(overrides)
    task = Task(**values)
    db.add(task)
    db.flush()
    return task


def _donor(db, *, org_id) -> Donor:
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, entity_type="egg_donor")
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    email = normalize_email(f"filter-donor-{uuid.uuid4().hex[:8]}@example.com")
    donor = Donor(
        id=uuid.uuid4(),
        organization_id=org_id,
        donor_number=f"D{uuid.uuid4().int % 90000 + 10000:05d}",
        donor_type="egg",
        stage_id=stage.id,
        full_name="Filter Donor",
        email=email,
        email_hash=hash_email(email),
    )
    db.add(donor)
    db.flush()
    return donor


def _appointment_type(db, *, org_id, user_id, name: str) -> AppointmentType:
    appt_type = AppointmentType(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user_id,
        slug=f"type-{uuid.uuid4().hex[:8]}",
        name=name,
        duration_minutes=30,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.ZOOM.value,
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()
    return appt_type


def _appointment(
    db,
    *,
    org_id,
    user_id,
    appointment_type_id,
    client_name: str,
    status: AppointmentStatus = AppointmentStatus.CONFIRMED,
    meeting_mode: MeetingMode = MeetingMode.ZOOM,
    days_ahead: int = 3,
) -> Appointment:
    start = datetime.combine(date.today() + timedelta(days=days_ahead), time(15, 0), tzinfo=UTC)
    appt = Appointment(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appointment_type_id,
        client_name=client_name,
        client_email=f"{uuid.uuid4().hex[:8]}@example.com",
        client_phone="555-123-4567",
        client_timezone="America/New_York",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=meeting_mode.value,
        status=status.value,
    )
    db.add(appt)
    db.flush()
    return appt


# =============================================================================
# Tasks
# =============================================================================


@pytest.mark.asyncio
async def test_same_day_tasks_sort_by_due_time_with_untimed_last(authed_client, db, test_auth):
    due = date.today() + timedelta(days=4)
    now = datetime.now(UTC)
    # Newest first is the order the QA pass saw: untimed, 3 PM, 11 AM, 9 AM.
    for age_minutes, (title, due_time) in enumerate(
        (
            ("untimed", None),
            ("three-pm", time(15, 0)),
            ("eleven-am", time(11, 0)),
            ("nine-am", time(9, 0)),
        )
    ):
        _task(
            db,
            org_id=test_auth.org.id,
            user_id=test_auth.user.id,
            title=f"order-{title}",
            due_date=due,
            due_time=due_time,
            created_at=now - timedelta(minutes=age_minutes),
        )
    db.commit()

    response = await authed_client.get(
        "/tasks", params={"q": "order-", "is_completed": "false", "exclude_approvals": "true"}
    )

    assert response.status_code == 200, response.text
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["order-nine-am", "order-eleven-am", "order-three-pm", "order-untimed"]


@pytest.mark.asyncio
async def test_task_linked_type_filter_stays_in_the_session_org(authed_client, db, test_auth):
    donor = _donor(db, org_id=test_auth.org.id)
    _task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        title="linked-donor",
        donor_id=donor.id,
    )
    _task(db, org_id=test_auth.org.id, user_id=test_auth.user.id, title="linked-none")

    other_org = _other_org(db)
    foreign_donor = _donor(db, org_id=other_org.id)
    _task(
        db,
        org_id=other_org.id,
        user_id=test_auth.user.id,
        title="linked-foreign-donor",
        donor_id=foreign_donor.id,
    )
    _task(db, org_id=other_org.id, user_id=test_auth.user.id, title="linked-foreign-none")
    db.commit()

    donor_only = await authed_client.get("/tasks", params={"q": "linked-", "linked_type": "donor"})
    unlinked = await authed_client.get("/tasks", params={"q": "linked-", "linked_type": "none"})
    everything = await authed_client.get("/tasks", params={"q": "linked-"})

    assert donor_only.status_code == 200, donor_only.text
    assert [item["title"] for item in donor_only.json()["items"]] == ["linked-donor"]
    assert [item["title"] for item in unlinked.json()["items"]] == ["linked-none"]
    assert sorted(item["title"] for item in everything.json()["items"]) == [
        "linked-donor",
        "linked-none",
    ]


@pytest.mark.asyncio
async def test_task_linked_type_rejects_unknown_values(authed_client):
    response = await authed_client.get("/tasks", params={"linked_type": "match"})

    assert response.status_code == 422


# =============================================================================
# Appointments
# =============================================================================


@pytest.mark.asyncio
async def test_appointment_list_filters_by_client_type_and_format(authed_client, db, test_auth):
    consult = _appointment_type(
        db, org_id=test_auth.org.id, user_id=test_auth.user.id, name="Consult"
    )
    screening = _appointment_type(
        db, org_id=test_auth.org.id, user_id=test_auth.user.id, name="Screening"
    )
    _appointment(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=consult.id,
        client_name="Sophia Gonzalez",
    )
    _appointment(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=screening.id,
        client_name="Maya Chen",
        meeting_mode=MeetingMode.PHONE,
    )
    db.commit()

    by_client = await authed_client.get("/appointments", params={"q": "soph"})
    by_type = await authed_client.get(
        "/appointments", params={"appointment_type_id": str(screening.id)}
    )
    by_format = await authed_client.get("/appointments", params={"meeting_mode": "phone"})

    assert by_client.status_code == 200, by_client.text
    assert [item["client_name"] for item in by_client.json()["items"]] == ["Sophia Gonzalez"]
    assert [item["client_name"] for item in by_type.json()["items"]] == ["Maya Chen"]
    assert [item["client_name"] for item in by_format.json()["items"]] == ["Maya Chen"]


@pytest.mark.asyncio
async def test_appointment_type_filter_from_another_org_returns_nothing(
    authed_client, db, test_auth
):
    other_org = _other_org(db)
    foreign_type = _appointment_type(
        db, org_id=other_org.id, user_id=test_auth.user.id, name="Foreign"
    )
    _appointment(
        db,
        org_id=other_org.id,
        user_id=test_auth.user.id,
        appointment_type_id=foreign_type.id,
        client_name="Foreign Client",
    )
    db.commit()

    listed = await authed_client.get(
        "/appointments", params={"appointment_type_id": str(foreign_type.id)}
    )
    counts = await authed_client.get(
        "/appointments/status-counts", params={"appointment_type_id": str(foreign_type.id)}
    )

    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert counts.status_code == 200, counts.text
    assert sum(counts.json().values()) == 0


@pytest.mark.asyncio
async def test_appointment_status_counts_cover_only_the_session_user_and_org(
    authed_client, db, test_auth
):
    appt_type = _appointment_type(
        db, org_id=test_auth.org.id, user_id=test_auth.user.id, name="Consult"
    )
    for status in (
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.PENDING,
        AppointmentStatus.CANCELLED,
    ):
        _appointment(
            db,
            org_id=test_auth.org.id,
            user_id=test_auth.user.id,
            appointment_type_id=appt_type.id,
            client_name="Own Client",
            status=status,
        )

    # Another user in the same org.
    colleague = User(
        id=uuid.uuid4(),
        email=f"colleague-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Colleague",
        token_version=1,
        is_active=True,
    )
    db.add(colleague)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=colleague.id,
            organization_id=test_auth.org.id,
            role=Role.CASE_MANAGER,
        )
    )
    _appointment(
        db,
        org_id=test_auth.org.id,
        user_id=colleague.id,
        appointment_type_id=appt_type.id,
        client_name="Colleague Client",
    )

    # The same user in another org.
    other_org = _other_org(db)
    foreign_type = _appointment_type(
        db, org_id=other_org.id, user_id=test_auth.user.id, name="Foreign"
    )
    _appointment(
        db,
        org_id=other_org.id,
        user_id=test_auth.user.id,
        appointment_type_id=foreign_type.id,
        client_name="Foreign Client",
        status=AppointmentStatus.PENDING,
    )
    db.commit()

    response = await authed_client.get("/appointments/status-counts")
    searched = await authed_client.get("/appointments/status-counts", params={"q": "colleague"})

    assert response.status_code == 200, response.text
    assert response.json() == {
        "pending": 1,
        "confirmed": 2,
        "completed": 0,
        "cancelled": 1,
        "no_show": 0,
        "expired": 0,
    }
    assert sum(searched.json().values()) == 0


@pytest.mark.asyncio
async def test_appointment_filters_reject_unknown_format(authed_client):
    listed = await authed_client.get("/appointments", params={"meeting_mode": "carrier_pigeon"})
    counts = await authed_client.get(
        "/appointments/status-counts", params={"meeting_mode": "carrier_pigeon"}
    )

    assert listed.status_code == 422
    assert counts.status_code == 422


@pytest.mark.asyncio
async def test_appointment_status_counts_require_a_session(client):
    response = await client.get("/appointments/status-counts")

    assert response.status_code == 401
