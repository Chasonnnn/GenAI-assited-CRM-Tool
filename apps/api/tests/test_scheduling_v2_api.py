"""HTTP contracts for V2 scheduling commands and calendar-binding boundaries."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.csrf import CSRF_HEADER
from app.db.enums import AppointmentStatus, MeetingMode
from app.db.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    BookingLink,
    CalendarBinding,
    Membership,
    Organization,
    User,
    UserIntegration,
)
from app.schemas.surrogate import SurrogateCreate
from app.services import calendar_binding_service, surrogate_service


@pytest.fixture(autouse=True)
def scheduling_v2(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)


@pytest.fixture
def booking_surface(db, test_org, test_user):
    start = (datetime.now(UTC) + timedelta(days=14)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    appointment_type = AppointmentType(
        organization_id=test_org.id,
        user_id=test_user.id,
        name="HTTP Scheduling",
        slug=f"http-scheduling-{uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        auto_approve=False,
        reminder_hours_before=0,
        is_active=True,
    )
    booking_link = BookingLink(
        organization_id=test_org.id,
        user_id=test_user.id,
        public_slug=f"http-book-{uuid4().hex[:8]}",
        is_active=True,
    )
    db.add_all(
        [
            appointment_type,
            booking_link,
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
    return appointment_type, booking_link, start


def _public_create_payload(appointment_type, start, *, request_id="public-create"):
    return {
        "appointment_type_id": str(appointment_type.id),
        "client_name": "HTTP Client",
        "client_email": "http-scheduling@example.com",
        "client_phone": "555-0100",
        "client_timezone": "UTC",
        "scheduled_start": start.isoformat(),
        "meeting_mode": "phone",
        "expected_revision": 0,
        "request_id": request_id,
    }


async def _public_pending(client, db, booking_surface):
    appointment_type, booking_link, start = booking_surface
    response = await client.post(
        f"/book/{booking_link.public_slug}/book",
        json=_public_create_payload(appointment_type, start),
    )
    assert response.status_code == 200, response.text
    appointment = (
        db.query(Appointment).filter_by(organization_id=booking_link.organization_id).one()
    )
    return appointment, start


@pytest.mark.asyncio
async def test_public_create_staff_approve_and_complete_http_contract(
    client, authed_client, db, booking_surface
):
    appointment, _start = await _public_pending(client, db, booking_surface)
    assert appointment.status == AppointmentStatus.PENDING.value
    assert appointment.revision == 1
    assert appointment.origin == "crm"

    approved = await authed_client.post(
        f"/appointments/{appointment.id}/approve",
        json={"expected_revision": 1, "request_id": "staff-approve"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["scheduling"]["revision"] == 2

    completed = await authed_client.post(
        f"/appointments/{appointment.id}/complete",
        json={"expected_revision": 2, "request_id": "staff-complete", "status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == AppointmentStatus.COMPLETED.value
    assert completed.json()["scheduling"]["revision"] == 3


@pytest.mark.asyncio
async def test_staff_create_reschedule_stale_and_cancel_http_contract(
    authed_client, db, test_org, test_user, booking_surface
):
    appointment_type, _booking_link, start = booking_surface
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="HTTP scheduling surrogate", email=f"http-{uuid4().hex}@example.com"
        ),
    )
    create = await authed_client.post(
        "/appointments",
        json={
            **_public_create_payload(appointment_type, start, request_id="staff-create"),
            "surrogate_id": str(surrogate.id),
        },
    )
    assert create.status_code == 201, create.text
    appointment_id = create.json()["id"]
    assert create.json()["scheduling"]["revision"] == 1

    stale = await authed_client.post(
        f"/appointments/{appointment_id}/reschedule",
        json={
            "scheduled_start": (start + timedelta(days=7)).isoformat(),
            "expected_revision": 0,
            "request_id": "stale-staff-move",
        },
    )
    assert stale.status_code == 409

    moved = await authed_client.post(
        f"/appointments/{appointment_id}/reschedule",
        json={
            "scheduled_start": (start + timedelta(days=7)).isoformat(),
            "expected_revision": 1,
            "request_id": "staff-move",
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["scheduling"]["revision"] == 2

    cancelled = await authed_client.post(
        f"/appointments/{appointment_id}/cancel",
        json={"expected_revision": 2, "request_id": "staff-cancel", "reason": "No longer needed"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == AppointmentStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_public_token_rotation_replay_and_override_rejection(
    client, authed_client, db, booking_surface
):
    appointment, start = await _public_pending(client, db, booking_surface)
    approved = await authed_client.post(
        f"/appointments/{appointment.id}/approve",
        json={"expected_revision": 1, "request_id": "approve-public-flow"},
    )
    assert approved.status_code == 200, approved.text
    db.refresh(appointment)
    old_token = appointment.reschedule_token
    target = start + timedelta(days=7)
    path = f"/book/self-service/{appointment.organization_id}/reschedule/{old_token}"
    payload = {
        "scheduled_start": target.isoformat(),
        "expected_revision": 2,
        "request_id": "move-one",
    }

    moved = await client.post(path, json=payload)
    assert moved.status_code == 200, moved.text
    assert moved.json()["scheduling"]["revision"] == 3
    db.refresh(appointment)
    assert appointment.reschedule_token != old_token

    replay = await client.post(path, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["scheduling"]["revision"] == 3

    divergent = await client.post(
        path,
        json={**payload, "scheduled_start": (target + timedelta(days=7)).isoformat()},
    )
    assert divergent.status_code == 409

    override = await client.post(
        f"/book/self-service/{appointment.organization_id}/reschedule/{appointment.reschedule_token}",
        json={
            "scheduled_start": (target + timedelta(days=7)).isoformat(),
            "expected_revision": 3,
            "request_id": "public-override",
            "override_availability": True,
            "override_reason": "not allowed",
        },
    )
    assert override.status_code == 400

    cancel_token = appointment.cancel_token
    cancel_path = f"/book/self-service/{appointment.organization_id}/cancel/{cancel_token}"
    cancel = await client.post(
        cancel_path,
        json={"expected_revision": 3, "request_id": "public-cancel", "reason": "Client request"},
    )
    assert cancel.status_code == 200, cancel.text
    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CANCELLED.value
    assert cancel.json()["status"] == AppointmentStatus.CANCELLED.value
    replay_cancel = await client.post(
        cancel_path,
        json={"expected_revision": 3, "request_id": "public-cancel", "reason": "Client request"},
    )
    assert replay_cancel.status_code == 200, replay_cancel.text


@pytest.mark.asyncio
async def test_sync_actions_enforce_csrf_and_tenant_scope(authed_client, db, test_org, test_user):
    other_org = Organization(name="Other scheduling tenant", slug=f"other-{uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    foreign = Appointment(
        organization_id=other_org.id,
        user_id=test_user.id,
        client_name="Foreign",
        client_email=f"foreign-{uuid4().hex[:8]}@example.test",
        client_phone="555-0101",
        client_timezone="UTC",
        scheduled_start=datetime.now(UTC) + timedelta(days=30),
        scheduled_end=datetime.now(UTC) + timedelta(days=30, minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
    )
    db.add(foreign)
    db.commit()

    csrf_denied = await authed_client.post(
        f"/appointments/{foreign.id}/sync/retry",
        json={"expected_revision": 1, "request_id": "csrf-denied"},
        headers={CSRF_HEADER: "invalid"},
    )
    assert csrf_denied.status_code == 403
    retry = await authed_client.post(
        f"/appointments/{foreign.id}/sync/retry",
        json={"expected_revision": 1, "request_id": "cross-org-retry"},
    )
    resolve = await authed_client.post(
        f"/appointments/{foreign.id}/sync/resolve",
        json={
            "expected_revision": 1,
            "expected_etag": "etag",
            "request_id": "cross-org-resolve",
            "resolution": "crm",
        },
    )
    assert retry.status_code == 404
    assert resolve.status_code == 404


@pytest.mark.asyncio
async def test_binding_endpoints_are_scoped_and_csrf_protected(
    authed_client, db, test_org, test_user, monkeypatch
):
    integration = UserIntegration(
        user_id=test_user.id,
        integration_type="google_calendar",
        account_email="bindings@example.test",
        access_token_encrypted="local-test-token",
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        organization_id=test_org.id,
        user_id=test_user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="bookings@example.test",
        display_name="Bookings",
        access_role="owner",
        timezone="UTC",
        write_bookings=True,
    )
    db.add(binding)
    db.commit()

    bindings = await authed_client.get("/integrations/google-calendar/bindings")
    assert bindings.status_code == 200, bindings.text
    assert [item["id"] for item in bindings.json()["items"]] == [str(binding.id)]

    csrf_denied = await authed_client.put(
        "/integrations/google-calendar/bindings",
        json={"items": []},
        headers={CSRF_HEADER: "invalid"},
    )
    assert csrf_denied.status_code == 403

    async def discovered(*_args, **_kwargs):
        return [
            {
                "calendar_id": binding.calendar_id,
                "display_name": "Bookings",
                "access_role": "owner",
                "timezone": "UTC",
                "primary": True,
            }
        ]

    monkeypatch.setattr(calendar_binding_service, "discover_calendars", discovered)
    updated = await authed_client.put(
        "/integrations/google-calendar/bindings",
        json={
            "items": [
                {
                    "calendar_id": binding.calendar_id,
                    "check_busy": True,
                    "show_events": True,
                    "write_bookings": True,
                    "is_active": True,
                }
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["items"][0]["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_google_calendar_v2_status_uses_current_tenant_binding_completion(
    authed_client, db, test_auth, test_org, monkeypatch
):
    from app.db.enums import Role
    from app.services import google_tasks_sync_service

    completed_at = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=3)
    foreign_completed_at = completed_at + timedelta(minutes=2)
    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="google_calendar",
        account_email="owner-status@example.test",
        access_token_encrypted="local-test-token",
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        organization_id=test_org.id,
        user_id=test_auth.user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="current-org-calendar",
        display_name="Current org calendar",
        access_role="owner",
        timezone="UTC",
        synced_at=completed_at,
    )
    other_org = Organization(name="Foreign status tenant", slug=f"foreign-{uuid4().hex[:8]}")
    foreign_user = User(
        email=f"foreign-calendar-{uuid4().hex[:8]}@example.test",
        display_name="Foreign calendar owner",
    )
    db.add_all([binding, other_org, foreign_user])
    db.flush()
    db.add(
        Membership(
            user_id=foreign_user.id,
            organization_id=other_org.id,
            role=Role.DEVELOPER.value,
        )
    )
    foreign_integration = UserIntegration(
        user_id=foreign_user.id,
        integration_type="google_calendar",
        account_email="foreign-status@example.test",
        access_token_encrypted="foreign-test-token",
    )
    db.add(foreign_integration)
    db.flush()
    db.add(
        CalendarBinding(
            organization_id=other_org.id,
            user_id=foreign_user.id,
            integration_id=foreign_integration.id,
            account_email=foreign_integration.account_email,
            calendar_id="foreign-org-calendar",
            display_name="Foreign org calendar",
            access_role="owner",
            timezone="UTC",
            synced_at=foreign_completed_at,
        )
    )
    db.commit()
    db.refresh(integration)
    integration_updated_at = integration.updated_at

    monkeypatch.setattr(
        google_tasks_sync_service,
        "check_google_tasks_access",
        lambda *_args, **_kwargs: (True, None),
    )

    async def sync_tasks(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(google_tasks_sync_service, "sync_google_tasks_for_user_async", sync_tasks)
    queued_binding_ids: list[object] = []
    monkeypatch.setattr(
        calendar_binding_service,
        "enqueue_binding_sync",
        lambda _db, *, binding_id, **_kwargs: queued_binding_ids.append(binding_id),
    )

    status_response = await authed_client.get("/integrations/google-calendar/status")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["last_sync_at"] == completed_at.isoformat()

    uninitialized_binding = CalendarBinding(
        organization_id=test_org.id,
        user_id=test_auth.user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="uninitialized-current-org-calendar",
        display_name="Uninitialized current org calendar",
        access_role="owner",
        timezone="UTC",
        synced_at=None,
    )
    db.add(uninitialized_binding)
    db.commit()

    sync_response = await authed_client.post("/integrations/google-calendar/sync")
    assert sync_response.status_code == 200, sync_response.text
    assert sync_response.json()["last_sync_at"] is None
    assert sync_response.json()["appointment_changes"] == 0
    assert sync_response.json()["calendars_queued"] == 2
    assert queued_binding_ids == [binding.id, uninitialized_binding.id]
    db.refresh(integration)
    assert integration.updated_at == integration_updated_at


@pytest.mark.asyncio
async def test_legacy_google_import_marks_synthetic_appointments_external(
    db, test_org, test_user, monkeypatch
):
    from app.services import appointment_integrations

    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", False)
    start = datetime.now(UTC) + timedelta(days=14)

    async def calendar_ids(**_kwargs):
        return ["primary"]

    async def calendar_events(**_kwargs):
        return {
            "connected": True,
            "complete": True,
            "error": None,
            "events": [
                {
                    "id": "legacy-google-event",
                    "summary": "Legacy Google event",
                    "start": start,
                    "end": start + timedelta(minutes=30),
                    "is_all_day": False,
                }
            ],
        }

    monkeypatch.setattr("app.services.calendar_service.list_user_google_calendar_ids", calendar_ids)
    monkeypatch.setattr("app.services.calendar_service.get_user_calendar_events", calendar_events)
    assert (
        await appointment_integrations._sync_manual_google_events_for_appointments_async(
            db, user_id=test_user.id, org_id=test_org.id
        )
        == 1
    )
    imported = db.query(Appointment).filter_by(google_event_id="legacy-google-event").one()
    assert imported.origin == "google_import"
