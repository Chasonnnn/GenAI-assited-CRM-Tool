from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import Mock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import (
    Appointment,
    AppointmentType,
    AuditLog,
    Job,
    Membership,
    Organization,
    RolePermission,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    User,
    UserIntegration,
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
def interview(db, test_org, test_user, request):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(full_name="Interview QA", email=f"{uuid4()}@example.com"),
    )
    if meeting_mode := getattr(request, "param", None):
        appointment_type = surrogate_status_service._get_or_create_interview_appointment_type(
            db, org_id=test_org.id, user_id=test_user.id
        )
        appointment_type.meeting_mode = meeting_mode
        appointment_type.meeting_modes = [meeting_mode]
        db.flush()
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


@pytest.mark.asyncio
async def test_interview_slot_preview_uses_appointment_owner_and_hides_cross_tenant(
    authed_client, db, interview, monkeypatch
):
    from app.services import appointment_service

    surrogate, _ = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    seen = {}

    def available(_db, query, **kwargs):
        seen["query"] = query
        seen["exclude"] = kwargs.get("exclude_appointment_id")
        return [
            appointment_service.TimeSlot(
                datetime.now(UTC) + timedelta(days=4),
                datetime.now(UTC) + timedelta(days=4, minutes=30),
            )
        ]

    monkeypatch.setattr(appointment_service, "get_available_slots", available)
    path = f"/surrogates/{surrogate.id}/interview-appointment/slots?date=2026-09-25"
    response = await authed_client.get(path)
    assert response.status_code == 200, response.text
    assert response.json()["slots"]
    assert seen["query"].user_id == appointment.user_id
    assert seen["query"].appointment_type_id == appointment.appointment_type_id
    assert seen["exclude"] == appointment.id

    other_org = Organization(id=uuid4(), name="Other Slot Org", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    surrogate.organization_id = other_org.id
    db.commit()
    assert (await authed_client.get(path)).status_code == 404


PREVIEW_ROUTES = ["slots?date=2026-09-28", "open-days?date_start=2026-09-27&date_end=2026-10-31"]


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["unmodifiable", "archived"])
@pytest.mark.parametrize("route", PREVIEW_ROUTES)
async def test_interview_availability_previews_deny_unmodifiable_surrogate(
    authed_client, db, interview, monkeypatch, denial, route
):
    from app.routers import surrogates_interview_appointment as interview_router

    surrogate, _ = interview
    if denial == "archived":
        surrogate.is_archived = True
        db.commit()
    else:
        monkeypatch.setattr(
            interview_router, "can_modify_surrogate", lambda *_args, **_kwargs: False
        )
    response = await authed_client.get(f"/surrogates/{surrogate.id}/interview-appointment/{route}")
    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot manage this interview"


@pytest.mark.asyncio
async def test_initial_stage_interview_preview_does_not_create_appointment_type(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.services import appointment_service

    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(full_name="First Interview QA", email=f"{uuid4()}@example.com"),
    )
    seen = {}

    def available(_db, query, **kwargs):
        seen["query"] = query
        seen["type"] = kwargs.get("appointment_type")
        return []

    monkeypatch.setattr(appointment_service, "get_available_slots", available)
    response = await authed_client.get(
        f"/surrogates/{surrogate.id}/interview-appointment/slots?date=2026-09-25"
    )
    assert response.status_code == 200, response.text
    assert seen["query"].user_id == test_user.id
    assert seen["type"].slug == "initial-interview"
    assert (
        db.query(AppointmentType)
        .filter_by(organization_id=test_org.id, user_id=test_user.id, slug="initial-interview")
        .count()
        == 0
    )


def _open_days_path(surrogate, start, end, timezone="America/New_York"):
    return (
        f"/surrogates/{surrogate.id}/interview-appointment/open-days"
        f"?date_start={start}&date_end={end}&client_timezone={timezone}"
    )


@pytest.mark.asyncio
async def test_interview_open_days_group_slots_by_viewer_date_and_hide_cross_tenant(
    authed_client, db, interview, monkeypatch
):
    from app.services import appointment_service

    surrogate, _ = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    seen = {}

    def slot(start):
        return appointment_service.TimeSlot(start, start + timedelta(minutes=30))

    def available(_db, query, **kwargs):
        seen["query"] = query
        seen["exclude"] = kwargs.get("exclude_appointment_id")
        return [
            # 11:30 PM on Oct 1 in New York is already Oct 2 in UTC.
            slot(datetime(2026, 10, 2, 3, 30, tzinfo=UTC)),
            slot(datetime(2026, 10, 1, 14, 0, tzinfo=UTC)),
            slot(datetime(2026, 10, 5, 13, 0, tzinfo=UTC)),
        ]

    monkeypatch.setattr(appointment_service, "get_available_slots", available)
    path = _open_days_path(surrogate, "2026-09-27", "2026-10-31")
    response = await authed_client.get(path)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "timezone": "America/New_York",
        "dates": ["2026-10-01", "2026-10-05"],
    }
    assert seen["query"].date_start == date(2026, 9, 27)
    assert seen["query"].date_end == date(2026, 10, 31)
    assert seen["query"].client_timezone == "America/New_York"
    assert seen["query"].user_id == appointment.user_id
    assert seen["query"].appointment_type_id == appointment.appointment_type_id
    assert seen["exclude"] == appointment.id

    other_org = Organization(id=uuid4(), name="Other Open Day Org", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    surrogate.organization_id = other_org.id
    db.commit()
    assert (await authed_client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_interview_open_days_bound_the_range(authed_client, db, interview, monkeypatch):
    from app.services import appointment_service

    surrogate, _ = interview
    monkeypatch.setattr(appointment_service, "get_available_slots", lambda *_a, **_k: [])

    six_weeks = await authed_client.get(_open_days_path(surrogate, "2026-09-27", "2026-11-07"))
    assert six_weeks.status_code == 200, six_weeks.text
    too_long = await authed_client.get(_open_days_path(surrogate, "2026-09-27", "2026-11-08"))
    assert too_long.status_code == 400
    assert too_long.json()["detail"] == "Date range cannot exceed 42 days"
    reversed_range = await authed_client.get(_open_days_path(surrogate, "2026-10-02", "2026-10-01"))
    assert reversed_range.status_code == 400
    missing_end = await authed_client.get(
        f"/surrogates/{surrogate.id}/interview-appointment/open-days?date_start=2026-09-27"
    )
    assert missing_end.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client_timezone", "owner_timezone"),
    [("Etc/GMT+12", "Pacific/Kiritimati"), ("Pacific/Kiritimati", "Etc/GMT+12")],
)
async def test_interview_availability_previews_reject_dates_at_the_calendar_limits(
    authed_client, db, interview, client_timezone, owner_timezone
):
    from app.services import appointment_service

    surrogate, user = interview
    appointment_service.set_availability_rules(
        db,
        user.id,
        surrogate.organization_id,
        [{"day_of_week": day, "start_time": "09:00", "end_time": "17:00"} for day in range(7)],
        owner_timezone,
    )
    db.commit()
    base = f"/surrogates/{surrogate.id}/interview-appointment"
    first, last = service.FIRST_PREVIEW_DATE, service.LAST_PREVIEW_DATE

    async def slots(day):
        return await authed_client.get(
            f"{base}/slots", params={"date": day.isoformat(), "client_timezone": client_timezone}
        )

    async def open_days(start, end):
        return await authed_client.get(
            f"{base}/open-days",
            params={
                "date_start": start.isoformat(),
                "date_end": end.isoformat(),
                "client_timezone": client_timezone,
            },
        )

    # The owner's day furthest from the viewer's day still computes at the supported limits.
    edge_days = await open_days(last - timedelta(days=41), last)
    assert edge_days.status_code == 200, edge_days.text
    assert edge_days.json()["dates"][-1] == last.isoformat()
    for response in (await slots(first), await slots(last)):
        assert response.status_code == 200, response.text

    for response in (
        await slots(first - timedelta(days=1)),
        await slots(last + timedelta(days=1)),
        await slots(date.max),
        await open_days(date.max - timedelta(days=30), date.max),
        await open_days(date.min, date.min + timedelta(days=1)),
    ):
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Date is out of range"


def _open_week_for(db, surrogate, user):
    from app.services import appointment_service

    appointment_service.set_availability_rules(
        db,
        user.id,
        surrogate.organization_id,
        [{"day_of_week": day, "start_time": "09:00", "end_time": "17:00"} for day in range(7)],
        "America/New_York",
    )
    # Start after the fixture's interview so it does not take any of these times.
    start = datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=7)
    return start, start + timedelta(days=41)


@pytest.mark.asyncio
async def test_interview_open_days_read_calendar_busy_once_for_the_whole_range(
    authed_client, db, interview, monkeypatch
):
    from app.core.config import settings
    from app.services import calendar_binding_service

    surrogate, user = interview
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    start, end = _open_week_for(db, surrogate, user)
    zone = ZoneInfo("America/New_York")
    blocked = start + timedelta(days=3)
    calls = []

    def busy(_db, org_id, user_id, range_start, range_end, exclude_appointment=None):
        calls.append((org_id, user_id, range_start, range_end))
        blocked_start = datetime.combine(blocked, time.min, tzinfo=zone)
        blocked_end = datetime.combine(blocked + timedelta(days=1), time.min, tzinfo=zone)
        return [(blocked_start, blocked_end)]

    monkeypatch.setattr(calendar_binding_service, "busy_intervals", busy)
    response = await authed_client.get(_open_days_path(surrogate, start, end))

    assert response.status_code == 200, response.text
    assert len(calls) == 1
    org_id, user_id, range_start, range_end = calls[0]
    assert (org_id, user_id) == (surrogate.organization_id, user.id)
    assert range_start.astimezone(zone).date() == start
    assert range_end.astimezone(zone).date() == end
    expected = [start + timedelta(days=offset) for offset in range(42)]
    assert response.json()["dates"] == [day.isoformat() for day in expected if day != blocked]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["slots", "open-days"])
async def test_interview_availability_previews_hide_calendar_failure_detail(
    authed_client, db, interview, monkeypatch, route
):
    from app.core.config import settings
    from app.services import calendar_binding_service

    surrogate, user = interview
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    start, end = _open_week_for(db, surrogate, user)

    def unavailable(*_args, **_kwargs):
        raise calendar_binding_service.CalendarAvailabilityUnavailable(
            "upstream said token=secret-provider-token"
        )

    monkeypatch.setattr(calendar_binding_service, "busy_intervals", unavailable)
    path = (
        f"/surrogates/{surrogate.id}/interview-appointment/slots?date={start}"
        if route == "slots"
        else _open_days_path(surrogate, start, end)
    )
    response = await authed_client.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "Required Google Calendar availability is unavailable"}
    assert "secret-provider-token" not in response.text


@asynccontextmanager
async def _role_client(db, org, role):
    from httpx import ASGITransport, AsyncClient

    from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token
    from app.core.deps import COOKIE_NAME, get_db
    from app.core.security import create_session_token
    from app.main import app
    from app.services import session_service

    user = User(
        id=uuid4(),
        email=f"interview-role-{uuid4().hex[:8]}@test.com",
        display_name="Interview Role User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Membership(id=uuid4(), user_id=user.id, organization_id=org.id, role=role.value))
    db.commit()
    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org.id, token=token, request=None)
    app.dependency_overrides[get_db] = lambda: db
    csrf_token = generate_csrf_token()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as role_client:
            yield role_client, user
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", PREVIEW_ROUTES)
async def test_interview_availability_previews_are_limited_to_the_appointment_owner(
    db, test_org, interview, monkeypatch, route
):
    from app.services import appointment_service

    surrogate, admin = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    assert appointment.user_id == admin.id
    monkeypatch.setattr(appointment_service, "get_available_slots", lambda *_a, **_k: [])

    async with _role_client(db, test_org, Role.INTAKE_SPECIALIST) as (intake_client, intake):
        surrogate.owner_type = "user"
        surrogate.owner_id = intake.id
        db.commit()
        path = f"/surrogates/{surrogate.id}/interview-appointment/{route}"
        denied = await intake_client.get(path)
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Only the appointment owner can manage this interview"

        # The same intake user may preview once the active interview is theirs.
        appointment.user_id = intake.id
        db.commit()
        allowed = await intake_client.get(path)
        assert allowed.status_code == 200, allowed.text


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["manage_appointments", "change_surrogate_status"])
@pytest.mark.parametrize("route", PREVIEW_ROUTES)
async def test_interview_availability_previews_deny_roles_without_permission(
    db, test_org, interview, permission, route
):
    surrogate, _ = interview
    db.add(
        RolePermission(
            id=uuid4(),
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST.value,
            permission=permission,
            is_granted=False,
        )
    )
    db.commit()

    async with _role_client(db, test_org, Role.INTAKE_SPECIALIST) as (intake_client, _intake):
        response = await intake_client.get(
            f"/surrogates/{surrogate.id}/interview-appointment/{route}"
        )

    assert response.status_code == 403
    assert response.json()["detail"] == f"Missing permission: {permission}"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("interview", ["zoom", "google_meet"], indirect=True)
@pytest.mark.parametrize("action", ["reschedule", "cancel"])
@pytest.mark.parametrize("move", [False, True])
async def test_unlinked_video_interview_can_be_managed(
    authed_client, db, interview, action, move, notifications
):
    surrogate, _user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    assert appointment.meeting_mode in {"zoom", "google_meet"}
    assert not any(
        (
            appointment.zoom_meeting_id,
            appointment.zoom_join_url,
            appointment.google_event_id,
            appointment.google_meet_url,
        )
    )
    original_start = appointment.scheduled_start
    start = datetime.now(UTC) + timedelta(days=8) if action == "reschedule" else None
    request = payload(command(db, surrogate, action, move=move, start=start))
    path = f"/surrogates/{surrogate.id}/interview-appointment"

    response = await authed_client.post(path, json=request)
    assert response.status_code == 200, response.text
    retry = await authed_client.post(path, json=request)
    assert retry.status_code == 200, retry.text
    db.refresh(appointment)
    db.refresh(surrogate)
    assert appointment.status == ("cancelled" if action == "cancel" else "confirmed")
    assert appointment.scheduled_start == (start or original_start)
    assert surrogate.status_label == (
        "Reschedule Needed" if action == "cancel" and move else "Interview Scheduled"
    )
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 1
    assert (
        db.query(AuditLog).filter_by(target_type="appointment", target_id=appointment.id).count()
        == 1
    )
    assert (
        db.query(Job)
        .filter_by(organization_id=surrogate.organization_id, job_type="appointment_google_sync")
        .count()
        == 0
    )
    notifications[
        "send_cancelled" if action == "cancel" else "send_rescheduled"
    ].assert_called_once()


@pytest.mark.parametrize("action", ["reschedule", "cancel"])
@pytest.mark.parametrize(
    ("link_field", "link_value"),
    [
        ("zoom_meeting_id", "linked-zoom-meeting"),
        ("zoom_join_url", "https://zoom.us/j/123456789"),
        ("google_meet_url", "https://meet.google.com/abc-defg-hij"),
    ],
)
def test_unsupported_external_link_is_blocked_regardless_of_meeting_mode(
    db, interview, action, link_field, link_value, notifications
):
    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    assert appointment.meeting_mode == "phone"
    setattr(appointment, link_field, link_value)
    db.commit()
    original_start, original_stage = appointment.scheduled_start, surrogate.stage_id

    with pytest.raises(
        service.InterviewAppointmentError, match="linked to an external meeting"
    ) as exc:
        manage(
            db,
            surrogate,
            user,
            command(
                db,
                surrogate,
                action,
                start=datetime.now(UTC) + timedelta(days=8) if action == "reschedule" else None,
            ),
        )

    assert exc.value.status_code == 409
    assert appointment.status == "confirmed"
    assert appointment.scheduled_start == original_start
    assert surrogate.stage_id == original_stage
    assert (
        db.query(AuditLog).filter_by(target_type="appointment", target_id=appointment.id).count()
        == 0
    )
    for notification in notifications.values():
        notification.assert_not_called()


@pytest.mark.parametrize("meeting_mode", ["google_meet", "zoom"])
@pytest.mark.parametrize("action", ["reschedule", "cancel"])
def test_google_linked_interview_change_commits_with_sync_intent(
    db, interview, action, meeting_mode, monkeypatch
):
    from app.services import appointment_google_sync_service

    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "linked-google-event"
    appointment.meeting_mode = meeting_mode
    integration = UserIntegration(
        user_id=user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    monkeypatch.setattr(
        appointment_google_sync_service,
        "prepare_link",
        lambda _db, _appointment: appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email="owner@example.com",
            calendar_id="qa-interviews@group.calendar.google.com",
            event_id="linked-google-event",
            etag='"etag-1"',
            start=appointment.scheduled_start,
            end=appointment.scheduled_end,
        ),
    )

    requested = command(
        db,
        surrogate,
        action,
        move=False,
        start=datetime.now(UTC) + timedelta(days=8) if action == "reschedule" else None,
    )
    manage(db, surrogate, user, requested)

    assert appointment.status == ("cancelled" if action == "cancel" else "confirmed")
    assert (
        db.query(Job)
        .filter_by(organization_id=surrogate.organization_id, job_type="appointment_google_sync")
        .count()
        == 1
    )


def test_cancelled_google_interview_cannot_be_rebooked_until_sync_completes(
    db, interview, monkeypatch
):
    from app.services import appointment_google_sync_service

    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "linked-google-event"
    appointment.meeting_mode = "google_meet"
    integration = UserIntegration(
        user_id=user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    monkeypatch.setattr(
        appointment_google_sync_service,
        "prepare_link",
        lambda _db, _appointment: appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email="owner@example.com",
            calendar_id="qa-interviews@group.calendar.google.com",
            event_id="linked-google-event",
            etag='"etag-1"',
            start=appointment.scheduled_start,
            end=appointment.scheduled_end,
        ),
    )
    manage(db, surrogate, user, command(db, surrogate, "cancel", move=False))
    job = db.query(Job).filter_by(job_type="appointment_google_sync").one()
    book = command(
        db,
        surrogate,
        "schedule",
        move=False,
        start=datetime.now(UTC) + timedelta(days=4),
    )

    for job_state in ("pending", "failed"):
        job.status = job_state
        db.commit()
        with pytest.raises(service.InterviewAppointmentError, match="Google synchronization"):
            manage(db, surrogate, user, book)
        assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 1

    job.status = "completed"
    appointment.google_sync_state = "completed"
    db.commit()
    manage(db, surrogate, user, book)
    assert db.query(Appointment).filter_by(surrogate_id=surrogate.id).count() == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "remote_case"),
    [
        ("reschedule", "base"),
        ("reschedule", "target"),
        ("reschedule", "claim_lost"),
        ("reschedule", "divergent"),
        ("cancel", "base"),
        ("cancel", "tombstone"),
        ("cancel", "missing"),
        ("cancel", "calendar_missing"),
    ],
)
async def test_google_sync_worker_reconciles_immutable_intent(
    db, interview, monkeypatch, action, remote_case
):
    from app.services import appointment_google_sync_service, calendar_service

    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "linked-google-event"
    appointment.meeting_mode = "google_meet"
    integration = UserIntegration(
        user_id=user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    base_start, base_end = appointment.scheduled_start, appointment.scheduled_end
    calendar_id = "qa-interviews@group.calendar.google.com"
    monkeypatch.setattr(
        appointment_google_sync_service,
        "prepare_link",
        lambda _db, _appointment: appointment_google_sync_service.PreparedGoogleLink(
            integration_id=integration.id,
            account_email="owner@example.com",
            calendar_id=calendar_id,
            event_id="linked-google-event",
            etag='"etag-1"',
            start=base_start,
            end=base_end,
        ),
    )
    manage(
        db,
        surrogate,
        user,
        command(
            db,
            surrogate,
            action,
            move=False,
            start=datetime.now(UTC) + timedelta(days=8) if action == "reschedule" else None,
        ),
    )
    job = db.query(Job).filter_by(job_type="appointment_google_sync").one()
    job.status = "running"
    job.claim_token = uuid4()
    db.commit()
    target_start, target_end = appointment.scheduled_start, appointment.scheduled_end
    client_email = appointment.client_email

    async def token(*_args):
        return "token"

    async def writable(_token):
        return [] if remote_case == "calendar_missing" else [calendar_id]

    async def event(*_args):
        if remote_case == "claim_lost":
            job.claim_token = uuid4()
            db.commit()
        if remote_case == "missing":
            return None
        if remote_case == "tombstone":
            return {
                "id": "linked-google-event",
                "status": "cancelled",
                "etag": '"etag-2"',
                "start": None,
                "end": None,
                "organizer_email": None,
                "organizer_self": False,
                "attendee_emails": [],
            }
        event_start, event_end = {
            "base": (base_start, base_end),
            "target": (target_start, target_end),
            "claim_lost": (target_start, target_end),
            "divergent": (base_start + timedelta(hours=1), base_end + timedelta(hours=1)),
            "calendar_missing": (base_start, base_end),
        }[remote_case]
        return {
            "id": "linked-google-event",
            "status": "confirmed",
            "etag": '"etag-1"' if remote_case == "base" else '"etag-2"',
            "start": event_start,
            "end": event_end,
            "organizer_email": calendar_id,
            "organizer_self": False,
            "attendee_emails": [client_email],
        }

    writes = []

    async def update(*_args, **kwargs):
        writes.append(kwargs)
        return {
            "etag": '"etag-2"',
            "start": target_start,
            "end": target_end,
        }

    async def delete(*_args, **kwargs):
        writes.append(kwargs)

    monkeypatch.setattr(calendar_service, "get_google_access_token", token)
    monkeypatch.setattr(calendar_service, "list_writable_google_calendar_ids", writable)
    monkeypatch.setattr(calendar_service, "get_linked_google_event", event)
    monkeypatch.setattr(calendar_service, "update_linked_google_event", update)
    monkeypatch.setattr(calendar_service, "delete_linked_google_event", delete)
    # The fixture owns an outer rollback-only transaction; the production worker
    # uses a standalone session and rolls its read transaction back before I/O.
    monkeypatch.setattr(db, "rollback", db.expire_all)

    if remote_case == "calendar_missing":
        with pytest.raises(RuntimeError, match="Google appointment sync failed"):
            await appointment_google_sync_service.process_job(db, job)
    else:
        await appointment_google_sync_service.process_job(db, job)
    db.refresh(appointment)
    assert len(writes) == (1 if remote_case == "base" else 0)
    assert appointment.google_sync_state == (
        "conflict"
        if remote_case == "divergent"
        else "pending"
        if remote_case in {"calendar_missing", "claim_lost"}
        else "completed"
    )
    if writes:
        assert writes[0]["etag"] == '"etag-1"'


@pytest.mark.asyncio
async def test_google_worker_rejects_stale_exact_event_binding_before_provider_io(
    db, interview, monkeypatch
):
    from app.services import appointment_google_sync_service, calendar_service

    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "original-event"
    integration = UserIntegration(
        user_id=user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    link = appointment_google_sync_service.PreparedGoogleLink(
        integration_id=integration.id,
        account_email="owner@example.com",
        calendar_id="qa-interviews@group.calendar.google.com",
        event_id="original-event",
        etag='"etag-1"',
        start=appointment.scheduled_start,
        end=appointment.scheduled_end,
    )
    appointment_google_sync_service.enqueue(db, appointment, action="cancel", link=link)
    db.commit()
    job = db.query(Job).filter_by(job_type="appointment_google_sync").one()
    job.status = "running"
    job.claim_token = uuid4()
    appointment.google_event_id = "replacement-event"
    db.commit()

    async def forbidden_token(*_args):
        pytest.fail("Stale intent must not reach Google")

    monkeypatch.setattr(calendar_service, "get_google_access_token", forbidden_token)
    with pytest.raises(RuntimeError, match="binding changed"):
        await appointment_google_sync_service.process_job(db, job)
    db.refresh(appointment)
    assert appointment.google_event_id == "replacement-event"
    assert appointment.google_sync_state == "pending"


@pytest.mark.asyncio
async def test_google_worker_acknowledges_committed_result_after_job_completion_crash(
    db, interview, monkeypatch
):
    from app.services import appointment_google_sync_service, calendar_service

    surrogate, user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "linked-event"
    integration = UserIntegration(
        user_id=user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    db.add(integration)
    db.commit()
    link = appointment_google_sync_service.PreparedGoogleLink(
        integration_id=integration.id,
        account_email="owner@example.com",
        calendar_id="qa-interviews@group.calendar.google.com",
        event_id="linked-event",
        etag='"etag-1"',
        start=appointment.scheduled_start,
        end=appointment.scheduled_end,
    )
    appointment_google_sync_service.enqueue(db, appointment, action="reschedule", link=link)
    appointment.google_event_etag = '"etag-2"'
    appointment.google_sync_state = "completed"
    db.commit()
    job = db.query(Job).filter_by(job_type="appointment_google_sync").one()
    job.status = "running"
    job.claim_token = uuid4()
    db.commit()

    async def forbidden_token(*_args):
        pytest.fail("Completed intent must not contact Google again")

    monkeypatch.setattr(calendar_service, "get_google_access_token", forbidden_token)
    monkeypatch.setattr(db, "rollback", db.expire_all)
    await appointment_google_sync_service.process_job(db, job)
    db.refresh(appointment)
    assert appointment.google_sync_state == "completed"
    assert appointment.google_event_etag == '"etag-2"'


@pytest.mark.asyncio
async def test_google_retry_requires_csrf_tenant_and_exact_failed_appointment(
    client, authed_client, db, interview, monkeypatch
):
    surrogate, _user = interview
    appointment = service.get_latest(db, surrogate.organization_id, surrogate.id)
    appointment.google_event_id = "linked-event"
    appointment.google_sync_revision = 1
    appointment.google_sync_state = "pending"
    job = Job(
        organization_id=surrogate.organization_id,
        job_type="appointment_google_sync",
        idempotency_key=f"appointment-google:{appointment.id}:1",
        payload={"appointment_id": str(appointment.id)},
        status="failed",
    )
    db.add(job)
    db.commit()
    path = f"/surrogates/{surrogate.id}/interview-appointment/sync/retry"
    body = {"expected_appointment_id": str(appointment.id)}

    assert (await client.post(path, json=body)).status_code == 401
    csrf = authed_client.headers.pop(CSRF_HEADER)
    assert (await authed_client.post(path, json=body)).status_code == 403
    authed_client.headers[CSRF_HEADER] = csrf
    assert (
        await authed_client.post(path, json={"expected_appointment_id": str(uuid4())})
    ).status_code == 409
    response = await authed_client.post(path, json=body)
    assert response.status_code == 200
    assert response.json()["external_sync_status"] == "pending"
    db.refresh(job)
    assert job.status == "pending"
    assert job.payload == {"appointment_id": str(appointment.id)}

    from app.routers import surrogates_interview_appointment as interview_router

    with monkeypatch.context() as patcher:
        patcher.setattr(interview_router, "can_modify_surrogate", lambda *_args, **_kwargs: False)
        assert (await authed_client.post(path, json=body)).status_code == 403

    other_org = Organization(id=uuid4(), name="Other Retry Org", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    surrogate.organization_id = other_org.id
    db.commit()
    assert (await authed_client.post(path, json=body)).status_code == 404


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
