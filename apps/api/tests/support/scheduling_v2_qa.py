"""Local-only scheduling V2 API/worker harness.

Run this module instead of ``uvicorn`` or the normal worker when exercising
Scheduling V2 locally. It installs a synthetic Google Calendar transport and a
process-wide HTTP guard: loopback requests are allowed, known Google probes are
synthetic, and all other outbound HTTP is blocked. The transport stores its
synthetic remote state in a local JSON file so separately started API and
restricted-worker processes see the same remote calendar.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import UUID

import httpx

DEFAULT_STATE = Path("/private/tmp/crm-scheduling-v2-google.json")
DEFAULT_METADATA = Path("/private/tmp/crm-scheduling-v2-qa.json")
QA_CALENDAR_ID = "scheduling-qa@example.test"
QA_ACCOUNT_EMAIL = "scheduling-admin@example.test"
QA_TOKEN = "scheduling-v2-qa-token"
_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_CLIENT = httpx.Client
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def write_private_environment(path: Path) -> None:
    """Write the complete local test environment without reading repository .env files."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    values = {
        "ENV": "test",
        "TESTING": "1",
        "MATCH_CASE_EXPANSION_ENABLED": "true",
        "DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5553/crm_scheduling_qa",
        "SCHEDULING_V2_ENABLED": "true",
        "JWT_SECRET": "test-jwt-secret-0123456789abcdef",
        "FERNET_KEY": key,
        "META_ENCRYPTION_KEY": key,
        "VERSION_ENCRYPTION_KEY": key,
        "DATA_ENCRYPTION_KEY": key,
        "PII_HASH_KEY": "test-pii-hash-key-0123456789abcdef",
        "DEV_SECRET": "change-me",
        "API_BASE_URL": "http://127.0.0.1:8017",
        "FRONTEND_URL": "http://localhost:3047",
        "CORS_ORIGINS": "http://localhost:3047,http://127.0.0.1:3047",
        "SCHEDULING_V2_QA_STATE": str(DEFAULT_STATE),
        "WORKER_JOB_TYPES": "appointment_google_sync,google_calendar_sync",
        "GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED": "false",
        "GMAIL_SYNC_FALLBACK_ENABLED": "false",
        "SENTRY_DSN": "",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "RESEND_API_KEY": "",
        "PLATFORM_RESEND_API_KEY": "",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{name}={value}\n" for name, value in values.items()), encoding="utf-8"
    )
    os.chmod(path, 0o600)


def _state_path() -> Path:
    return Path(os.environ.get("SCHEDULING_V2_QA_STATE", str(DEFAULT_STATE))).resolve()


@contextmanager
def _locked_state(path: Path):
    """Read/update a state file atomically across the API and worker processes."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        try:
            state = json.load(handle)
        except json.JSONDecodeError:
            state = {}
        state.setdefault("calendars", {QA_CALENDAR_ID: {"events": {}, "sync": 0}})
        state.setdefault("mode", "normal")
        yield state
        handle.seek(0)
        handle.truncate()
        json.dump(state, handle, sort_keys=True)
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def reset_google_state(path: Path | None = None, *, mode: str = "normal") -> None:
    path = path or _state_path()
    with _locked_state(path) as state:
        state.clear()
        state.update({"mode": mode, "calendars": {QA_CALENDAR_ID: {"events": {}, "sync": 0}}})


def set_google_mode(mode: str) -> None:
    """Change behavior without discarding remote events or sync history."""
    with _locked_state(_state_path()) as state:
        state["mode"] = mode


def edit_remote_event(event_id: str, *, start: datetime, end: datetime) -> None:
    with _locked_state(_state_path()) as state:
        calendar = state["calendars"][QA_CALENDAR_ID]
        event = calendar["events"].get(event_id)
        if event is None:
            raise ValueError("Synthetic event was not found")
        event["start"] = {"dateTime": start.isoformat(), "timeZone": "America/New_York"}
        event["end"] = {"dateTime": end.isoformat(), "timeZone": "America/New_York"}
        event["etag"] = _next_etag(calendar)


def cancel_remote_event(event_id: str) -> None:
    with _locked_state(_state_path()) as state:
        calendar = state["calendars"][QA_CALENDAR_ID]
        event = calendar["events"].get(event_id)
        if event is None:
            raise ValueError("Synthetic event was not found")
        event["status"] = "cancelled"
        event["etag"] = _next_etag(calendar)


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = dict(event)
    payload.pop("calendar_id", None)
    return payload


def _next_etag(calendar: dict[str, Any]) -> str:
    calendar["sync"] = int(calendar.get("sync", 0)) + 1
    return f'"qa-{calendar["sync"]}"'


class _GoogleQaTransport(httpx.AsyncBaseTransport):
    """Small Google Calendar v3 simulation for the exact scheduling adapter API."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != f"Bearer {QA_TOKEN}":
            return httpx.Response(401, json={"error": {"message": "invalid synthetic token"}})
        if request.url.host != "www.googleapis.com":
            raise RuntimeError("Scheduling QA blocked an unexpected provider host")
        with _locked_state(_state_path()) as state:
            mode = state["mode"]
            if mode == "provider_failure":
                return httpx.Response(503, json={"error": {"message": "synthetic outage"}})
            path = request.url.path
            if path.endswith("/users/me/calendarList") and request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": QA_CALENDAR_ID,
                                "summary": "Scheduling QA",
                                "accessRole": "owner",
                                "timeZone": "America/New_York",
                                "primary": True,
                            }
                        ]
                    },
                )
            if "/users/me/calendarList/" in path and request.method == "GET":
                requested_id = unquote(path.rsplit("/", 1)[-1])
                if requested_id != QA_CALENDAR_ID:
                    return httpx.Response(404)
                return httpx.Response(
                    200,
                    json={
                        "id": QA_CALENDAR_ID,
                        "summary": "Scheduling QA",
                        "accessRole": "owner",
                        "timeZone": "America/New_York",
                        "primary": True,
                    },
                )
            marker = "/calendars/"
            if marker not in path:
                return httpx.Response(404)
            remainder = path.split(marker, 1)[1].split("/events", 1)
            if len(remainder) != 2:
                return httpx.Response(404)
            calendar_id = httpx.URL("https://x/" + remainder[0]).path.lstrip("/")
            calendar = state["calendars"].setdefault(calendar_id, {"events": {}, "sync": 0})
            event_suffix = remainder[1].strip("/")
            if not event_suffix and request.method == "GET":
                if mode == "sync_token_expired" and request.url.params.get("syncToken"):
                    return httpx.Response(410)
                return httpx.Response(
                    200,
                    json={
                        "items": [_event_payload(e) for e in calendar["events"].values()],
                        "nextSyncToken": f"qa-sync-{calendar['sync']}",
                    },
                )
            if not event_suffix and request.method == "POST":
                body = json.loads(request.content)
                event_id = body["id"]
                if mode == "create_collision" or event_id in calendar["events"]:
                    return httpx.Response(409)
                body["etag"] = _next_etag(calendar)
                body["status"] = "confirmed"
                body["organizer"] = {"email": calendar_id, "self": True}
                body["htmlLink"] = f"https://calendar.google.test/event/{event_id}"
                if mode == "conference_pending":
                    body["conferenceData"]["createRequest"]["status"] = {"statusCode": "pending"}
                elif mode == "conference_failure":
                    body["conferenceData"]["createRequest"]["status"] = {"statusCode": "failure"}
                else:
                    body["conferenceData"] = {
                        "entryPoints": [
                            {
                                "entryPointType": "video",
                                "uri": f"https://meet.google.test/{event_id}",
                            }
                        ]
                    }
                calendar["events"][event_id] = body
                return httpx.Response(
                    201, json=_event_payload(body), headers={"ETag": body["etag"]}
                )
            event = calendar["events"].get(event_suffix)
            if request.method == "GET":
                return (
                    httpx.Response(200, json=_event_payload(event), headers={"ETag": event["etag"]})
                    if event
                    else httpx.Response(404)
                )
            if not event:
                return httpx.Response(404)
            if mode == "precondition_conflict" or request.headers.get("if-match") != event["etag"]:
                return httpx.Response(412)
            if request.method == "PATCH":
                body = json.loads(request.content)
                event.update(body)
                event["etag"] = _next_etag(calendar)
                return httpx.Response(
                    200, json=_event_payload(event), headers={"ETag": event["etag"]}
                )
            if request.method == "DELETE":
                del calendar["events"][event_suffix]
                _next_etag(calendar)
                return httpx.Response(204)
            return httpx.Response(405)


class _QaAsyncClient(_REAL_ASYNC_CLIENT):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = _GoogleQaTransport()
        super().__init__(*args, **kwargs)


class _LocalOnlyAsyncTransport(httpx.AsyncBaseTransport):
    """Permit loopback traffic and return synthetic provider responses elsewhere."""

    def __init__(self) -> None:
        self._local = httpx.AsyncHTTPTransport()
        self._google = _GoogleQaTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host in _LOCAL_HOSTS:
            return await self._local.handle_async_request(request)
        if request.url.host == "www.googleapis.com":
            return await self._google.handle_async_request(request)
        if request.url.host == "tasks.googleapis.com":
            return httpx.Response(
                403,
                json={"error": {"message": "Google Tasks is not enabled in Scheduling V2 QA"}},
            )
        return httpx.Response(599, text="External HTTP is blocked by Scheduling V2 QA")

    async def aclose(self) -> None:
        await self._local.aclose()


class _LocalOnlyAsyncClient(_REAL_ASYNC_CLIENT):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("transport") is None:
            kwargs["transport"] = _LocalOnlyAsyncTransport()
        super().__init__(*args, **kwargs)


class _LocalOnlySyncTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self._local = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host in _LOCAL_HOSTS:
            return self._local.handle_request(request)
        return httpx.Response(599, text="External HTTP is blocked by Scheduling V2 QA")

    def close(self) -> None:
        self._local.close()


class _LocalOnlyClient(_REAL_CLIENT):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("transport") is None:
            kwargs["transport"] = _LocalOnlySyncTransport()
        super().__init__(*args, **kwargs)


def install_google_transport() -> None:
    """Patch only the V2 adapter module, before routes/jobs import it."""
    from app.services import google_scheduling_adapter

    # Keep every public httpx attribute available for adapter error handling.
    adapter_httpx = dict(vars(httpx))
    adapter_httpx["AsyncClient"] = _QaAsyncClient
    google_scheduling_adapter.httpx = SimpleNamespace(**adapter_httpx)


def install_outbound_guard() -> None:
    """Block all non-loopback HTTP from the local API or restricted worker."""
    httpx.AsyncClient = _LocalOnlyAsyncClient
    httpx.Client = _LocalOnlyClient


def seed_database(metadata_path: Path) -> dict[str, str]:
    """Create reusable test fixtures without contacting OAuth, email, or Google."""
    from app.core.encryption import hash_email
    from app.db.models import (
        Appointment,
        AppointmentType,
        AvailabilityRule,
        CalendarBinding,
        Donor,
        IntendedParent,
        Organization,
        Surrogate,
        UserIntegration,
    )
    from app.db.session import SessionLocal
    from app.schemas.donor import DonorCreate
    from app.schemas.surrogate import SurrogateCreate
    from app.services import (
        appointment_service,
        dev_service,
        donor_service,
        ip_service,
        oauth_service,
        org_service,
        surrogate_service,
    )

    with SessionLocal() as db:
        seeded = dev_service.seed_test_data(db)
        admin_id = UUID(
            next(user["user_id"] for user in seeded["users"] if user["email"] == "admin@test.com")
        )
        org_id = UUID(seeded["org_id"])
        org = db.get(Organization, org_id)
        org.timezone = "America/New_York"
        org_service.seed_org_defaults(db, org_id, admin_id)
        integration = (
            db.query(UserIntegration)
            .filter_by(user_id=admin_id, integration_type="google_calendar")
            .one_or_none()
        )
        if integration is None:
            integration = UserIntegration(
                user_id=admin_id,
                integration_type="google_calendar",
                access_token_encrypted=oauth_service.encrypt_token(QA_TOKEN),
                account_email=QA_ACCOUNT_EMAIL,
                token_expires_at=datetime.now(UTC) + timedelta(days=1),
                granted_scopes=["https://www.googleapis.com/auth/calendar"],
            )
            db.add(integration)
            db.flush()
        phone = db.query(AppointmentType).filter_by(user_id=admin_id, slug="qa-phone").one_or_none()
        if phone is None:
            phone = AppointmentType(
                organization_id=org_id,
                user_id=admin_id,
                name="QA phone",
                slug="qa-phone",
                meeting_mode="phone",
                meeting_modes=["phone"],
                dial_in_number="+15550100",
                auto_approve=True,
            )
            db.add(phone)
        meet = (
            db.query(AppointmentType)
            .filter_by(user_id=admin_id, slug="qa-google-meet")
            .one_or_none()
        )
        if meet is None:
            meet = AppointmentType(
                organization_id=org_id,
                user_id=admin_id,
                name="QA Google Meet",
                slug="qa-google-meet",
                meeting_mode="google_meet",
                meeting_modes=["google_meet"],
                auto_approve=True,
            )
            db.add(meet)
        if (
            not db.query(AvailabilityRule)
            .filter_by(organization_id=org_id, user_id=admin_id)
            .first()
        ):
            for day in range(5):
                db.add(
                    AvailabilityRule(
                        organization_id=org_id,
                        user_id=admin_id,
                        day_of_week=day,
                        start_time=datetime.strptime("09:00", "%H:%M").time(),
                        end_time=datetime.strptime("17:00", "%H:%M").time(),
                        timezone="America/New_York",
                    )
                )
        binding = (
            db.query(CalendarBinding)
            .filter_by(organization_id=org_id, user_id=admin_id, calendar_id=QA_CALENDAR_ID)
            .one_or_none()
        )
        if binding is None:
            db.add(
                CalendarBinding(
                    organization_id=org_id,
                    user_id=admin_id,
                    integration_id=integration.id,
                    account_email=QA_ACCOUNT_EMAIL,
                    calendar_id=QA_CALENDAR_ID,
                    display_name="Scheduling QA",
                    access_role="owner",
                    timezone="America/New_York",
                    check_busy=True,
                    show_events=True,
                    write_bookings=True,
                    is_active=True,
                )
            )
        elif binding.timezone != "America/New_York":
            binding.timezone = "America/New_York"
        surrogate = (
            db.query(Surrogate)
            .filter_by(organization_id=org_id, email_hash=hash_email("qa-surrogate@example.com"))
            .one_or_none()
        )
        if surrogate is None:
            surrogate = surrogate_service.create_surrogate(
                db,
                org_id,
                admin_id,
                SurrogateCreate(
                    full_name="QA Surrogate",
                    email="qa-surrogate@example.com",
                    phone="2125550101",
                    state="NY",
                ),
                emit_events=False,
            )
        donor = (
            db.query(Donor)
            .filter_by(organization_id=org_id, email_hash=hash_email("qa-donor@example.com"))
            .one_or_none()
        )
        if donor is None:
            donor = donor_service.create_donor(
                db,
                org_id,
                admin_id,
                DonorCreate(
                    donor_type="egg",
                    full_name="QA Donor",
                    email="qa-donor@example.com",
                    phone="2125550102",
                    state="NY",
                    owner_type="user",
                    owner_id=admin_id,
                ),
                commit=False,
                emit_workflow_events=False,
            )
        intended_parent = (
            db.query(IntendedParent)
            .filter_by(organization_id=org_id, email_hash=hash_email("qa-intended-parent@example.com"))
            .one_or_none()
        )
        if intended_parent is None:
            intended_parent = ip_service.create_intended_parent(
                db,
                org_id,
                admin_id,
                full_name="QA Intended Parent",
                email="qa-intended-parent@example.com",
                phone="2125550104",
                state="NY",
                owner_type="user",
                owner_id=admin_id,
            )
        db.flush()
        starts = [
            datetime.combine(date.today() + timedelta(days=7), time(10), tzinfo=UTC),
            datetime.combine(date.today() + timedelta(days=8), time(11), tzinfo=UTC),
            datetime.combine(date.today() + timedelta(days=9), time(13), tzinfo=UTC),
        ]
        if (
            not db.query(Appointment)
            .filter_by(organization_id=org_id, idempotency_key=f"qa-surrogate-{org_id}")
            .first()
        ):
            appointment_service.create_booking(
                db,
                org_id,
                admin_id,
                phone.id,
                "QA Client",
                "qa-client@example.com",
                "2125550103",
                "America/New_York",
                starts[0],
                idempotency_key=f"qa-surrogate-{org_id}",
                record_links={"surrogate_id": surrogate.id},
                actor_user_id=admin_id,
                request_id="qa-surrogate-create",
                override_availability=True,
                override_reason="Scheduling V2 QA seed",
            )
        if (
            not db.query(Appointment)
            .filter_by(organization_id=org_id, idempotency_key=f"qa-donor-{org_id}")
            .first()
        ):
            appointment_service.create_booking(
                db,
                org_id,
                admin_id,
                meet.id,
                "QA Client",
                "qa-client@example.com",
                "2125550103",
                "America/New_York",
                starts[1],
                idempotency_key=f"qa-donor-{org_id}",
                record_links={"donor_id": donor.id},
                actor_user_id=admin_id,
                request_id="qa-donor-create",
                override_availability=True,
                override_reason="Scheduling V2 QA seed",
            )
        if (
            not db.query(Appointment)
            .filter_by(organization_id=org_id, idempotency_key=f"qa-intended-parent-{org_id}")
            .first()
        ):
            appointment_service.create_booking(
                db,
                org_id,
                admin_id,
                phone.id,
                "QA Client",
                "qa-client@example.com",
                "2125550103",
                "America/New_York",
                starts[2],
                idempotency_key=f"qa-intended-parent-{org_id}",
                record_links={"intended_parent_id": intended_parent.id},
                actor_user_id=admin_id,
                request_id="qa-intended-parent-create",
                override_availability=True,
                override_reason="Scheduling V2 QA seed",
            )
        db.commit()
        surrogate_id = surrogate.id
        donor_id = donor.id
        intended_parent_id = intended_parent.id
    metadata = {
        "organization_id": str(org_id),
        "admin_user_id": str(admin_id),
        "admin_email": "admin@test.com",
        "phone_type_slug": "qa-phone",
        "google_meet_type_slug": "qa-google-meet",
        "calendar_id": QA_CALENDAR_ID,
        "timezone": "America/New_York",
        "surrogate_url": f"http://127.0.0.1:3047/surrogates/{surrogate_id}",
        "donor_url": f"http://127.0.0.1:3047/donors/{donor_id}",
        "intended_parent_url": f"http://127.0.0.1:3047/intended-parents/{intended_parent_id}",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    os.chmod(metadata_path, 0o600)
    return metadata


async def drain_scheduling_jobs(
    limit: int,
    *,
    job_types: list[str] | None = None,
    continue_after_failure: bool = False,
) -> int:
    """Run only scheduling jobs through the production job dispatcher in-process."""
    from app.db.enums import JobType
    from app.db.session import SessionLocal
    from app.services import job_service
    from app.worker import process_job

    count = 0
    allowed = job_types or [
        JobType.APPOINTMENT_GOOGLE_SYNC.value,
        JobType.GOOGLE_CALENDAR_SYNC.value,
    ]
    with SessionLocal() as db:
        while count < limit:
            jobs = job_service.claim_pending_jobs(db, limit=1, job_types=allowed)
            if not jobs:
                break
            job = jobs[0]
            try:
                if await process_job(db, job):
                    job_service.complete_claimed_job(db, job_id=job.id, claim_token=job.claim_token)
                count += 1
            except Exception as exc:
                db.rollback()
                job_service.fail_claimed_job(
                    db,
                    job_id=job.id,
                    claim_token=job.claim_token,
                    error=str(exc),
                    retry_run_at=job.run_at,
                )
                count += 1
                if not continue_after_failure:
                    raise
    return count


async def exhaust_appointment_sync_failures(
    appointment_id: UUID, limit: int
) -> dict[str, int | str]:
    """Exhaust one appointment's sync retries through the production job service."""
    from app.db.enums import JobStatus, JobType
    from app.db.session import SessionLocal
    from app.services import job_service
    from app.worker import process_job

    metadata = json.loads(DEFAULT_METADATA.read_text(encoding="utf-8"))
    org_id = UUID(metadata["organization_id"])
    with SessionLocal() as db:
        candidates = [
            job
            for job in job_service.list_jobs(
                db, org_id, job_type=JobType.APPOINTMENT_GOOGLE_SYNC, limit=100
            )
            if str(job.payload.get("appointment_id")) == str(appointment_id)
        ]
        if not candidates:
            raise SystemExit("No appointment Google-sync job exists for the requested appointment")
        job_id = candidates[0].id
        processed = 0
        while processed < limit:
            job = job_service.claim_job_for_dispatch(db, job_id)
            if job is None:
                break
            try:
                if await process_job(db, job):
                    job_service.complete_claimed_job(db, job_id=job.id, claim_token=job.claim_token)
            except Exception as exc:
                db.rollback()
                job_service.fail_claimed_job(
                    db,
                    job_id=job.id,
                    claim_token=job.claim_token,
                    error=str(exc),
                    retry_run_at=job.run_at,
                )
            processed += 1
        result = job_service.get_job(db, job_id, org_id)
        if result is None:
            raise SystemExit("Appointment Google-sync job disappeared")
        if result.status != JobStatus.FAILED.value:
            raise SystemExit(
                f"Appointment Google-sync job remains {result.status} after {processed} attempts"
            )
        return {"job_id": str(result.id), "status": result.status, "attempts": result.attempts}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Scheduling V2 QA harness")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup")
    setup.add_argument(
        "--env-file", type=Path, default=Path("/private/tmp/crm-scheduling-v2-qa.env")
    )
    reset = sub.add_parser("reset-google")
    reset.add_argument(
        "--mode",
        choices=[
            "normal",
            "conference_pending",
            "conference_failure",
            "create_collision",
            "precondition_conflict",
            "provider_failure",
            "sync_token_expired",
        ],
        default="normal",
    )
    mode = sub.add_parser("mode")
    mode.add_argument(
        "value",
        choices=[
            "normal",
            "conference_pending",
            "conference_failure",
            "create_collision",
            "precondition_conflict",
            "provider_failure",
            "sync_token_expired",
        ],
    )
    edit = sub.add_parser("remote-edit")
    edit.add_argument("event_id")
    edit.add_argument("--start", required=True, type=datetime.fromisoformat)
    edit.add_argument("--end", required=True, type=datetime.fromisoformat)
    cancel = sub.add_parser("remote-cancel")
    cancel.add_argument("event_id")
    seed = sub.add_parser("seed")
    seed.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    api = sub.add_parser("api")
    api.add_argument("--port", type=int, default=8017)
    drain = sub.add_parser("drain")
    drain.add_argument("--limit", type=int, default=50)
    exhaust = sub.add_parser("exhaust-appointment-failures")
    exhaust.add_argument("appointment_id", type=UUID)
    exhaust.add_argument("--limit", type=int, default=50)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "setup":
        write_private_environment(args.env_file)
        return
    if os.environ.get("ENV", "").lower() != "test" or os.environ.get(
        "SCHEDULING_V2_ENABLED", ""
    ).lower() not in {"1", "true"}:
        raise SystemExit("Set ENV=test and SCHEDULING_V2_ENABLED=true before using this harness")
    database = urlsplit(os.environ.get("DATABASE_URL", ""))
    if database.hostname not in {"127.0.0.1", "localhost"} or not database.path.startswith(
        "/crm_scheduling_"
    ):
        raise SystemExit("Scheduling QA requires a local disposable crm_scheduling_ database")
    if args.command == "reset-google":
        reset_google_state(mode=args.mode)
        return
    if args.command == "mode":
        set_google_mode(args.value)
        return
    if args.command == "remote-edit":
        edit_remote_event(
            args.event_id, start=args.start.astimezone(UTC), end=args.end.astimezone(UTC)
        )
        return
    if args.command == "remote-cancel":
        cancel_remote_event(args.event_id)
        return
    install_google_transport()
    install_outbound_guard()
    if args.command == "seed":
        seed_database(args.metadata)
        return
    if args.command == "drain":
        asyncio.run(drain_scheduling_jobs(args.limit))
        return
    if args.command == "exhaust-appointment-failures":
        asyncio.run(exhaust_appointment_sync_failures(args.appointment_id, args.limit))
        return
    import uvicorn
    from fastapi import HTTPException, Request
    from fastapi.responses import RedirectResponse

    from app.db.session import SessionLocal
    from app.main import app
    from app.routers.dev import login_as
    from app.services import appointment_service

    def local_login(request: Request):
        metadata = json.loads(DEFAULT_METADATA.read_text())
        response = RedirectResponse(f"http://{request.url.hostname}:3047/appointments")
        with SessionLocal() as db:
            login_as(UUID(metadata["admin_user_id"]), request, response, db)
        return response

    def local_manage(appointment_id: UUID, request: Request):
        if request.client is None or request.client.host not in _LOCAL_HOSTS:
            raise HTTPException(
                status_code=403, detail="QA manage links accept loopback requests only"
            )
        metadata = json.loads(DEFAULT_METADATA.read_text(encoding="utf-8"))
        with SessionLocal() as db:
            appointment = appointment_service.get_appointment(
                db, appointment_id, UUID(metadata["organization_id"])
            )
            if appointment is None or not appointment.reschedule_token:
                raise HTTPException(status_code=404, detail="QA appointment is not manageable")
            return RedirectResponse(
                "http://localhost:3047/book/self-service/"
                f"{metadata['organization_id']}/manage/{appointment.reschedule_token}"
            )

    # This route exists only in this loopback test harness, never in the deployed app.
    local_login.__annotations__["request"] = Request
    local_manage.__annotations__["appointment_id"] = UUID
    local_manage.__annotations__["request"] = Request
    app.add_api_route("/__qa/login", local_login, methods=["GET"], include_in_schema=False)
    app.add_api_route(
        "/__qa/manage/{appointment_id}",
        local_manage,
        methods=["GET"],
        include_in_schema=False,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
