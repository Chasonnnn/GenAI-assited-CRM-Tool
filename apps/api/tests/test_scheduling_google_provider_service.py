"""Provider reconciliation keeps explicit identity and common-version fences."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.enums import JobStatus
from app.db.models import Appointment, CalendarBinding, Job, UserIntegration
from app.services import appointment_google_sync_service as service
from app.services import google_scheduling_adapter as adapter


@pytest.fixture
def linked(db, test_org, test_user, monkeypatch):
    monkeypatch.setattr(service.settings, "SCHEDULING_V2_ENABLED", True)
    integration = UserIntegration(
        id=uuid4(),
        user_id=test_user.id,
        integration_type="google_calendar",
        account_email="scheduler@example.com",
        access_token_encrypted="synthetic-token",
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        integration_id=integration.id,
        account_email="scheduler@example.com",
        calendar_id="team@group.calendar.google.com",
        display_name="Interviews",
        access_role="owner",
        timezone="UTC",
        write_bookings=True,
        is_active=True,
    )
    db.add(binding)
    db.flush()
    start = datetime(2026, 10, 12, 12, tzinfo=UTC)
    appointment_id = uuid4()
    appointment = Appointment(
        id=appointment_id,
        organization_id=test_org.id,
        user_id=test_user.id,
        client_name="Provider Test",
        client_email="client@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode="phone",
        status="confirmed",
        origin="crm",
        google_event_id=adapter.deterministic_event_id(test_org.id, appointment_id),
        google_calendar_id=binding.calendar_id,
        google_integration_id=integration.id,
        google_account_email=integration.account_email,
        google_event_etag='"v1"',
        google_sync_revision=1,
        google_sync_state="pending",
        google_last_synced=service._interval_snapshot(
            start, start + timedelta(minutes=30), "confirmed", "UTC", '"v1"'
        ),
    )
    db.add(appointment)
    db.commit()
    return appointment, binding


def _remote(appointment, binding, *, start=None, etag='"v2"'):
    start = start or appointment.scheduled_start
    event = adapter.parse_event(
        {
            "id": appointment.google_event_id,
            "etag": etag,
            "status": "confirmed",
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": (start + timedelta(minutes=30)).isoformat()},
            "organizer": {"email": binding.calendar_id, "self": True},
            "attendees": [{"email": appointment.client_email}],
            "extendedProperties": {
                "private": adapter.ownership_properties(
                    appointment.organization_id, appointment.id, binding.id
                )
            },
        }
    )
    event["calendar_id"] = binding.calendar_id
    return event


def test_metadata_only_google_change_advances_common_etag_without_clearing_pending(db, linked):
    appointment, binding = linked
    remote = _remote(appointment, binding)

    assert service.observe_remote(db, appointment, remote) == "unchanged"
    assert appointment.google_last_synced["etag"] == '"v2"'
    assert appointment.google_event_etag == '"v2"'
    assert appointment.google_sync_state == "pending"
    assert appointment.revision == 0


def test_concurrent_interval_changes_keep_safe_three_way_conflict(db, linked):
    appointment, binding = linked
    appointment.scheduled_start += timedelta(days=1)
    appointment.scheduled_end += timedelta(days=1)
    appointment.revision = 1
    remote = _remote(appointment, binding, start=appointment.scheduled_start + timedelta(days=1))

    assert service.observe_remote(db, appointment, remote) == "conflict"
    assert appointment.google_sync_state == "conflict"
    assert appointment.google_conflict["observed_revision"] == 1
    assert appointment.google_conflict["base"]["etag"] == '"v1"'
    assert appointment.google_conflict["remote"]["etag"] == '"v2"'


def test_crm_resolution_requires_fresh_exact_google_etag(db, linked, monkeypatch):
    appointment, binding = linked
    appointment.scheduled_start += timedelta(days=1)
    appointment.scheduled_end += timedelta(days=1)
    appointment.revision = 1
    remote = _remote(appointment, binding, start=appointment.scheduled_start + timedelta(days=1))
    service.observe_remote(db, appointment, remote)
    db.commit()
    remote_after_drift = _remote(appointment, binding, etag='"v3"')

    async def token(_user_id, **_kwargs):
        return "synthetic-token"

    async def writable(_token, _calendar_id):
        return True

    async def drifted(_token, _calendar_id, _event_id):
        return remote_after_drift

    monkeypatch.setattr(service, "_v2_token", token)
    monkeypatch.setattr(adapter, "verify_writable_calendar", writable)
    monkeypatch.setattr(adapter, "get_event", drifted)
    with pytest.raises(service.GoogleLinkError, match="Google event changed"):
        service.resolve_conflict(
            db,
            appointment,
            resolution="crm",
            expected_revision=1,
            expected_etag='"v2"',
            actor_user_id=appointment.user_id,
        )


def test_unlinked_meet_retry_binds_explicit_destination_once(db, linked):
    appointment, binding = linked
    appointment.meeting_mode = "google_meet"
    appointment.google_event_id = None
    appointment.google_calendar_id = None
    appointment.google_account_email = None
    appointment.google_integration_id = None
    appointment.google_event_etag = None
    appointment.google_last_synced = None
    appointment.google_sync_revision = 0
    appointment.google_sync_state = "unlinked"
    db.commit()

    service.retry(db, appointment)

    assert appointment.google_calendar_id == binding.calendar_id
    assert appointment.google_event_id == adapter.deterministic_event_id(
        appointment.organization_id, appointment.id
    )
    assert appointment.google_sync_state == "pending"
    assert appointment.google_sync_revision == 1
    assert appointment.revision == 0
    assert db.query(Job).filter_by(organization_id=appointment.organization_id).count() == 1
    service.retry(db, appointment)
    assert db.query(Job).filter_by(organization_id=appointment.organization_id).count() == 1


def test_failed_meet_retry_queues_new_conference_attempt_without_domain_replay(db, linked):
    appointment, _binding = linked
    appointment.meeting_mode = "google_meet"
    appointment.google_sync_state = "failed"
    appointment.google_sync_error = "conference_failed"
    db.commit()

    service.retry(db, appointment)

    assert appointment.revision == 0
    assert appointment.google_sync_revision == 2
    assert appointment.google_sync_state == "pending"
    job = db.query(Job).filter_by(organization_id=appointment.organization_id).one()
    assert job.payload["action"] == "create"
    assert job.payload["event_id"] == appointment.google_event_id


def test_failed_conference_observation_fences_running_job(db, linked):
    appointment, binding = linked
    appointment.meeting_mode = "google_meet"
    job = service._enqueue_v2_intent(
        db,
        appointment,
        action="create",
        binding_id=binding.id,
        base=dict(appointment.google_last_synced),
    )
    job.status = JobStatus.RUNNING.value
    job.claim_token = uuid4()
    db.commit()
    remote = _remote(appointment, binding)
    remote["conference_failed"] = True

    assert service.observe_remote(db, appointment, remote) == "conference_pending"
    assert appointment.google_sync_state == "failed"
    assert service.status(db, appointment) == "failed"
    assert job.status == JobStatus.FAILED.value
    assert job.claim_token is None


@pytest.mark.asyncio
async def test_revoked_booking_binding_prevents_provider_io(db, linked, monkeypatch):
    appointment, binding = linked
    base = dict(appointment.google_last_synced)
    job = service._enqueue_v2_intent(
        db, appointment, action="reschedule", binding_id=binding.id, base=base
    )
    job.status = JobStatus.RUNNING.value
    job.claim_token = uuid4()
    binding.write_bookings = False
    db.commit()

    async def forbidden_token(_user_id, **_kwargs):
        pytest.fail("revoked binding reached provider I/O")

    monkeypatch.setattr(service, "_v2_token", forbidden_token)
    with pytest.raises(service.GoogleLinkError):
        await service.process_job(db, job)
    assert binding.write_bookings is False


@pytest.mark.asyncio
async def test_lost_create_response_adopts_only_same_deterministic_event(db, linked, monkeypatch):
    appointment, binding = linked
    appointment.google_last_synced = None
    appointment.google_event_etag = None
    appointment.google_sync_revision = 0
    job = service._enqueue_v2_intent(
        db, appointment, action="create", binding_id=binding.id, base=None
    )
    job.status = JobStatus.RUNNING.value
    job.claim_token = uuid4()
    db.commit()
    provider_event = _remote(appointment, binding, etag='"created"')
    reads = []
    inserts = []

    async def token(_user_id, **_kwargs):
        return "synthetic-token"

    async def writable(_token, _calendar_id):
        return True

    async def get_event(_token, _calendar_id, _event_id):
        reads.append(True)
        return None if len(reads) == 1 else provider_event

    async def insert_event(_token, _calendar_id, **_kwargs):
        inserts.append(True)
        raise adapter.GoogleProviderError("response lost")

    monkeypatch.setattr(service, "_v2_token", token)
    monkeypatch.setattr(adapter, "verify_writable_calendar", writable)
    monkeypatch.setattr(adapter, "get_event", get_event)
    monkeypatch.setattr(adapter, "insert_event", insert_event)
    # The test fixture owns an outer rollback transaction; preserve its rows
    # while exercising worker replay, which normally releases its own session.
    monkeypatch.setattr(db, "rollback", db.expire_all)

    await service.process_job(db, job)

    assert len(inserts) == 1
    assert len(reads) == 2
    db.refresh(appointment)
    assert appointment.google_sync_state == "completed"
    assert appointment.google_event_etag == '"created"'


@pytest.mark.asyncio
async def test_cancel_after_queued_create_deletes_same_deterministic_resource(
    db, linked, monkeypatch
):
    appointment, binding = linked
    appointment.google_last_synced = None
    appointment.google_event_etag = None
    appointment.google_sync_revision = 0
    create_job = service._enqueue_v2_intent(
        db, appointment, action="create", binding_id=binding.id, base=None
    )
    create_job.status = JobStatus.RUNNING.value
    create_job.claim_token = uuid4()
    appointment.status = "cancelled"
    appointment.revision = 1
    cancel_job = service._enqueue_v2_intent(
        db, appointment, action="cancel", binding_id=binding.id, base=None
    )
    cancel_job.status = JobStatus.RUNNING.value
    cancel_job.claim_token = uuid4()
    db.commit()
    provider_event = _remote(appointment, binding, etag='"created"')
    deleted = []
    tokens = []

    async def token(_user_id, **_kwargs):
        tokens.append(True)
        return "synthetic-token"

    async def writable(_token, _calendar_id):
        return True

    async def get_event(_token, _calendar_id, _event_id):
        return provider_event

    async def delete_event(_token, calendar_id, event_id, *, etag):
        deleted.append((calendar_id, event_id, etag))

    monkeypatch.setattr(service, "_v2_token", token)
    monkeypatch.setattr(adapter, "verify_writable_calendar", writable)
    monkeypatch.setattr(adapter, "get_event", get_event)
    monkeypatch.setattr(adapter, "delete_event", delete_event)
    monkeypatch.setattr(db, "rollback", db.expire_all)

    await service.process_job(db, create_job)
    assert tokens == []
    create_job.status = JobStatus.COMPLETED.value
    db.commit()
    await service.process_job(db, cancel_job)

    assert deleted == [(binding.calendar_id, appointment.google_event_id, '"created"')]
    db.refresh(appointment)
    assert appointment.google_sync_state == "completed"
    assert appointment.google_last_synced["status"] == "cancelled"
