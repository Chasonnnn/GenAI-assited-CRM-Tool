"""Durable, conditional Google delivery for CRM-owned appointments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.core.config import settings
from app.db.enums import JobStatus, JobType
from app.db.models import Appointment, Job, Membership, User, UserIntegration
from app.db.session import SessionLocal
from app.services import calendar_service, google_scheduling_adapter, job_service


class GoogleLinkError(ValueError):
    def __init__(self, message: str, state: str = "unlinked") -> None:
        super().__init__(message)
        self.state = state


@dataclass(frozen=True)
class PreparedGoogleLink:
    integration_id: UUID
    account_email: str
    calendar_id: str
    event_id: str
    etag: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class _LinkCandidate:
    event_id: str
    calendar_id: str | None
    client_email: str
    start: datetime
    end: datetime
    etag: str | None
    integration_id: UUID
    account_email: str


def _integration(db: Session, appointment: Appointment) -> UserIntegration:
    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == appointment.user_id,
            UserIntegration.integration_type == "google_calendar",
        )
        .one_or_none()
    )
    if integration is None or not integration.account_email:
        raise GoogleLinkError("Reconnect the appointment owner's Google Calendar")
    if appointment.google_integration_id and appointment.google_integration_id != integration.id:
        raise GoogleLinkError("Google account changed; review the appointment link")
    if (
        appointment.google_account_email
        and appointment.google_account_email.casefold() != integration.account_email.casefold()
    ):
        raise GoogleLinkError("Google account changed; reconnect the original account")
    member = (
        db.query(Membership.id)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == appointment.organization_id,
            Membership.user_id == appointment.user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .first()
    )
    if member is None:
        raise GoogleLinkError("Appointment owner is no longer active")
    return integration


async def _resolve_link(token: str, candidate: _LinkCandidate) -> PreparedGoogleLink:
    writable_ids = await calendar_service.list_writable_google_calendar_ids(token)
    if candidate.calendar_id:
        if candidate.calendar_id not in writable_ids:
            raise GoogleLinkError("Google calendar is no longer writable")
        calendar_ids = [candidate.calendar_id]
    else:
        calendar_ids = writable_ids
    matches: list[PreparedGoogleLink] = []
    for calendar_id in calendar_ids:
        event = await calendar_service.get_linked_google_event(
            token, calendar_id, candidate.event_id
        )
        if event is None or event["id"] != candidate.event_id:
            continue
        organizer = event["organizer_email"]
        if (
            event["status"] == "cancelled"
            or not isinstance(organizer, str)
            or not (event["organizer_self"] or organizer.casefold() == calendar_id.casefold())
            or candidate.client_email.casefold()
            not in {email.casefold() for email in event["attendee_emails"]}
        ):
            continue
        matches.append(
            PreparedGoogleLink(
                integration_id=candidate.integration_id,
                account_email=candidate.account_email,
                calendar_id=calendar_id,
                event_id=event["id"],
                etag=event["etag"],
                start=event["start"],
                end=event["end"],
            )
        )
    if len(matches) != 1:
        raise GoogleLinkError("Google appointment link requires review")
    match = matches[0]
    if (match.start, match.end) != (
        candidate.start,
        candidate.end,
    ):
        raise GoogleLinkError("Google event time changed; review before editing", "conflict")
    if candidate.etag and candidate.etag != match.etag:
        raise GoogleLinkError("Google event changed; review before editing", "conflict")
    return match


def prepare_link(db: Session, appointment: Appointment) -> PreparedGoogleLink | None:
    """Verify legacy identity before locking or changing the CRM appointment."""
    if not appointment.google_event_id:
        return None
    current = status(db, appointment)
    if current in {"pending", "failed", "conflict"}:
        raise GoogleLinkError(
            "Review Google synchronization before changing this appointment", "conflict"
        )
    try:
        integration = _integration(db, appointment)
        candidate = _LinkCandidate(
            event_id=appointment.google_event_id,
            calendar_id=appointment.google_calendar_id,
            client_email=appointment.client_email,
            start=appointment.scheduled_start.astimezone(UTC),
            end=appointment.scheduled_end.astimezone(UTC),
            etag=appointment.google_event_etag,
            integration_id=integration.id,
            account_email=integration.account_email,
        )
        with SessionLocal() as credential_db:
            token = run_async(
                calendar_service.get_google_access_token(credential_db, appointment.user_id),
                timeout=30,
            )
        if not token:
            raise GoogleLinkError("Reconnect the appointment owner's Google Calendar")
        return run_async(_resolve_link(token, candidate), timeout=60)
    except GoogleLinkError:
        raise
    except Exception:
        raise GoogleLinkError("Google appointment link could not be verified") from None


def enqueue(db: Session, appointment: Appointment, *, action: str, link: PreparedGoogleLink) -> Job:
    """Persist immutable provider intent in the caller's local transaction."""
    appointment.google_calendar_id = link.calendar_id
    appointment.google_account_email = link.account_email
    appointment.google_integration_id = link.integration_id
    appointment.google_event_etag = link.etag
    appointment.google_sync_revision += 1
    appointment.google_sync_state = "pending"
    revision = appointment.google_sync_revision
    return job_service.enqueue_job(
        db,
        org_id=appointment.organization_id,
        job_type=JobType.APPOINTMENT_GOOGLE_SYNC,
        payload={
            "appointment_id": str(appointment.id),
            "revision": revision,
            "action": action,
            "integration_id": str(link.integration_id),
            "account_email": link.account_email,
            "calendar_id": link.calendar_id,
            "event_id": link.event_id,
            "etag": link.etag,
            "base_start": link.start.isoformat(),
            "base_end": link.end.isoformat(),
            "target_start": appointment.scheduled_start.isoformat(),
            "target_end": appointment.scheduled_end.isoformat(),
        },
        idempotency_key=f"appointment-google:{appointment.id}:{revision}",
        commit=False,
    )


def _v2_enabled() -> bool:
    return bool(getattr(settings, "SCHEDULING_V2_ENABLED", False))


def _interval_snapshot(
    start: datetime, end: datetime, status_value: str, timezone_name: str, etag: str | None
) -> dict[str, str | None]:
    return {
        "start": start.astimezone(UTC).isoformat(),
        "end": end.astimezone(UTC).isoformat(),
        "status": status_value,
        "timezone": timezone_name,
        "etag": etag,
    }


def _local_snapshot(appointment: Appointment) -> dict[str, str | None]:
    return _interval_snapshot(
        appointment.scheduled_start,
        appointment.scheduled_end,
        appointment.status,
        appointment.client_timezone,
        appointment.google_event_etag,
    )


def _remote_snapshot(
    remote: google_scheduling_adapter.GoogleEvent, *, timezone_fallback: str
) -> dict[str, str | None]:
    return {
        "start": remote["start"].isoformat() if remote["start"] else None,
        "end": remote["end"].isoformat() if remote["end"] else None,
        "status": "cancelled" if remote["status"] == "cancelled" else "confirmed",
        "timezone": remote["timezone"] or timezone_fallback,
        "etag": remote["etag"] or None,
    }


def _values(snapshot: dict | None) -> tuple[object, object, object, object]:
    if not snapshot:
        return (None, None, None, None)
    return (
        snapshot.get("start"),
        snapshot.get("end"),
        snapshot.get("status"),
        snapshot.get("timezone"),
    )


def _binding_for_link(db: Session, appointment: Appointment):
    from app.db.models import CalendarBinding

    if not (
        appointment.google_integration_id
        and appointment.google_calendar_id
        and appointment.google_account_email
    ):
        raise GoogleLinkError("Google appointment link is incomplete")
    binding = (
        db.query(CalendarBinding)
        .filter(
            CalendarBinding.organization_id == appointment.organization_id,
            CalendarBinding.user_id == appointment.user_id,
            CalendarBinding.integration_id == appointment.google_integration_id,
            CalendarBinding.calendar_id == appointment.google_calendar_id,
            CalendarBinding.account_email == appointment.google_account_email,
        )
        .one_or_none()
    )
    if binding is None:
        raise GoogleLinkError("Google appointment binding requires review")
    return binding


def _enqueue_v2_intent(
    db: Session,
    appointment: Appointment,
    *,
    action: str,
    binding_id: UUID,
    base: dict | None,
) -> Job:
    if action not in {"create", "reschedule", "cancel"}:
        raise ValueError("Unsupported Google appointment action")
    appointment.google_sync_revision += 1
    appointment.google_sync_state = "pending"
    appointment.google_sync_error = None
    appointment.google_conflict = None
    revision = appointment.google_sync_revision
    target = _local_snapshot(appointment)
    job = job_service.enqueue_job(
        db,
        org_id=appointment.organization_id,
        job_type=JobType.APPOINTMENT_GOOGLE_SYNC,
        payload={
            "v2": True,
            "appointment_id": str(appointment.id),
            "domain_revision": appointment.revision,
            "revision": revision,
            "action": action,
            "binding_id": str(binding_id),
            "integration_id": str(appointment.google_integration_id),
            "account_email": appointment.google_account_email,
            "calendar_id": appointment.google_calendar_id,
            "event_id": appointment.google_event_id,
            "base": base,
            "target": target,
            "client_email": appointment.client_email,
            "meeting_mode": appointment.meeting_mode,
        },
        idempotency_key=f"appointment-google:{appointment.id}:{revision}",
        commit=False,
    )
    job.max_attempts = 20
    return job


def enqueue_create(db: Session, appointment: Appointment) -> Job | None:
    """Bind one explicit destination and queue a deterministic Google event."""
    if not _v2_enabled() or appointment.meeting_mode == "zoom":
        return None
    if appointment.origin != "crm":
        raise GoogleLinkError("Legacy appointment ownership requires review")
    if appointment.google_event_id:
        if appointment.google_sync_state == "pending":
            return _job(db, appointment)
        raise GoogleLinkError("Google appointment is already linked")
    from app.services import calendar_binding_service

    binding = calendar_binding_service.get_booking_binding(
        db, appointment.organization_id, appointment.user_id
    )
    if binding is None:
        if appointment.meeting_mode == "google_meet":
            appointment.google_sync_state = "unlinked"
            appointment.google_sync_error = "booking_destination_missing"
        return None
    if binding.access_role not in {"owner", "writer"}:
        appointment.google_sync_state = "unlinked"
        appointment.google_sync_error = "booking_destination_readonly"
        return None
    if appointment.id is None:
        db.flush()
    appointment.google_event_id = google_scheduling_adapter.deterministic_event_id(
        appointment.organization_id, appointment.id
    )
    appointment.google_calendar_id = binding.calendar_id
    appointment.google_integration_id = binding.integration_id
    appointment.google_account_email = binding.account_email
    appointment.google_event_etag = None
    return _enqueue_v2_intent(db, appointment, action="create", binding_id=binding.id, base=None)


def enqueue_v2_change(db: Session, appointment: Appointment, *, action: str) -> Job | None:
    """Queue an edit from the persisted common version without provider I/O."""
    if not _v2_enabled() or not appointment.google_event_id:
        return None
    if appointment.origin != "crm":
        raise GoogleLinkError("Legacy appointment ownership requires review")
    if action not in {"reschedule", "cancel"}:
        raise ValueError("Unsupported Google appointment action")
    if appointment.google_sync_state in {"failed", "conflict", "unlinked"}:
        raise GoogleLinkError("Review Google synchronization before changing this appointment")
    binding = _binding_for_link(db, appointment)
    base = dict(appointment.google_last_synced) if appointment.google_last_synced else None
    delivery_action = "create" if action == "reschedule" and base is None else action
    return _enqueue_v2_intent(
        db, appointment, action=delivery_action, binding_id=binding.id, base=base
    )


def observe_remote(
    db: Session, appointment: Appointment, remote: google_scheduling_adapter.GoogleEvent
) -> str:
    """Compare one verified organizer observation with the last common state."""
    if not _v2_enabled() or appointment.origin != "crm":
        return "ignored"
    if (
        not appointment.google_event_id
        or remote.get("calendar_id") != appointment.google_calendar_id
    ):
        return "ignored"
    binding = _binding_for_link(db, appointment)
    if remote["status"] == "cancelled":
        # Deleted-event tombstones can omit all fields except ID and status.
        owned = (
            remote["id"] == appointment.google_event_id
            and appointment.google_event_id
            == google_scheduling_adapter.deterministic_event_id(
                appointment.organization_id, appointment.id
            )
        )
    else:
        owned = google_scheduling_adapter.owns_event(
            remote,
            organization_id=appointment.organization_id,
            appointment_id=appointment.id,
            binding_id=binding.id,
            event_id=appointment.google_event_id,
            calendar_id=appointment.google_calendar_id,
            client_email=appointment.client_email,
        )
    if not owned:
        appointment.google_sync_state = "conflict"
        appointment.google_sync_error = "provider_identity_mismatch"
        return "conflict"
    base = dict(appointment.google_last_synced) if appointment.google_last_synced else None
    local = _local_snapshot(appointment)
    observed = _remote_snapshot(remote, timezone_fallback=appointment.client_timezone)
    base_values = _values(base)
    local_values = _values(local)
    remote_values = _values(observed)
    conference_state_is_safe = (
        (base is None and local_values == remote_values)
        or remote_values == base_values
        or local_values == remote_values
    )
    if (remote["conference_pending"] or remote["conference_failed"]) and conference_state_is_safe:
        appointment.google_event_etag = remote["etag"] or appointment.google_event_etag
        appointment.google_last_synced = observed
        appointment.google_sync_state = "failed" if remote["conference_failed"] else "pending"
        appointment.google_sync_error = "conference_failed" if remote["conference_failed"] else None
        if remote["conference_failed"]:
            pending_job = _job(db, appointment, lock=True)
            if pending_job and pending_job.status in {
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
            }:
                pending_job.status = JobStatus.FAILED.value
                pending_job.last_error = "conference_failed"
                pending_job.claim_token = None
                pending_job.claimed_at = None
        return "conference_pending"
    if base is None:
        if local_values == remote_values:
            appointment.google_last_synced = observed
            appointment.google_event_etag = remote["etag"] or appointment.google_event_etag
            appointment.google_sync_state = "completed"
            appointment.google_sync_error = None
            return "converged"
    elif remote_values == base_values:
        # RSVPs and other non-scheduling edits advance Google's ETag. The
        # interval remains the common version even while a local edit is queued.
        appointment.google_last_synced = observed
        appointment.google_event_etag = remote["etag"] or appointment.google_event_etag
        return "unchanged"
    elif local_values == remote_values:
        appointment.google_last_synced = observed
        appointment.google_event_etag = remote["etag"] or appointment.google_event_etag
        appointment.google_sync_state = "completed"
        appointment.google_sync_error = None
        appointment.google_conflict = None
        return "converged"
    elif local_values == base_values:
        if remote["status"] != "cancelled" and (
            remote["start"] is None or remote["end"] is None or remote["is_all_day"]
        ):
            appointment.google_sync_state = "conflict"
            appointment.google_sync_error = "invalid_provider_interval"
        else:
            from app.services import appointment_command_service

            try:
                appointment_command_service.apply_external_change(
                    db,
                    appointment,
                    scheduled_start=remote["start"],
                    scheduled_end=remote["end"],
                    status="cancelled" if remote["status"] == "cancelled" else "confirmed",
                    actor_user_id=None,
                    timezone=remote["timezone"],
                )
            except ValueError:
                appointment.google_sync_state = "conflict"
                appointment.google_sync_error = "invalid_provider_change"
            else:
                appointment.google_last_synced = observed
                appointment.google_event_etag = remote["etag"] or appointment.google_event_etag
                appointment.google_sync_state = "completed"
                appointment.google_sync_error = None
                appointment.google_conflict = None
                return "applied"
    appointment.google_conflict = {
        "base": base,
        "local": local,
        "remote": observed,
        "observed_revision": appointment.revision,
    }
    appointment.google_sync_state = "conflict"
    appointment.google_sync_error = appointment.google_sync_error or "concurrent_edit"
    return "conflict"


def _job(db: Session, appointment: Appointment, *, lock: bool = False) -> Job | None:
    if appointment.google_sync_revision == 0:
        return None
    query = db.query(Job).filter(
        Job.organization_id == appointment.organization_id,
        Job.idempotency_key
        == f"appointment-google:{appointment.id}:{appointment.google_sync_revision}",
    )
    return (query.with_for_update() if lock else query).populate_existing().one_or_none()


def status(db: Session, appointment: Appointment | None) -> str | None:
    if appointment is None:
        return None
    if appointment.google_sync_state in {"conflict", "unlinked"} or (
        _v2_enabled() and appointment.google_sync_state in {"completed", "failed"}
    ):
        return appointment.google_sync_state
    if not appointment.google_event_id:
        return None
    job = _job(db, appointment)
    if job is None:
        return None
    if job.status in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
        return "pending"
    if job.status == JobStatus.FAILED.value:
        return "failed"
    return (
        appointment.google_sync_state
        if _v2_enabled()
        else ("completed" if appointment.google_sync_state == "completed" else None)
    )


def retry(db: Session, appointment: Appointment, *, commit: bool = True) -> None:
    current = status(db, appointment)
    if current is None and _v2_enabled():
        current = appointment.google_sync_state
    if current in {"pending", "completed"}:
        return
    if (
        _v2_enabled()
        and current == "unlinked"
        and appointment.origin == "crm"
        and appointment.status == "confirmed"
        and appointment.google_event_id is None
    ):
        if enqueue_create(db, appointment) is None:
            raise GoogleLinkError("Select a writable Google booking calendar first")
        if commit:
            db.commit()
        return
    if current != "failed":
        raise GoogleLinkError("Google sync cannot be retried until the link is reviewed")
    if (
        _v2_enabled()
        and appointment.google_sync_error == "conference_failed"
        and appointment.origin == "crm"
        and appointment.meeting_mode == "google_meet"
        and appointment.status == "confirmed"
    ):
        binding = _binding_for_link(db, appointment)
        if not binding.is_active or not binding.write_bookings:
            raise GoogleLinkError("Google booking destination changed")
        _enqueue_v2_intent(
            db,
            appointment,
            action="create",
            binding_id=binding.id,
            base=dict(appointment.google_last_synced) if appointment.google_last_synced else None,
        )
        if commit:
            db.commit()
        return
    job = _job(db, appointment, lock=True)
    if job is None or job.status != JobStatus.FAILED.value:
        raise GoogleLinkError("Google sync is not ready to retry")
    job.status = JobStatus.PENDING.value
    job.attempts = 0
    job.last_error = None
    job.run_at = datetime.now(UTC)
    job.completed_at = None
    job.claim_token = None
    job.claimed_at = None
    appointment.google_sync_state = "pending"
    if commit:
        db.commit()


def resolve_conflict(
    db: Session,
    appointment: Appointment,
    *,
    resolution: str,
    expected_revision: int,
    expected_etag: str,
    actor_user_id: UUID,
    commit: bool = True,
) -> None:
    """Resolve a freshly observed conflict without writing Google in the request."""
    if not _v2_enabled() or resolution not in {"crm", "google"}:
        raise GoogleLinkError("Google conflict resolution is unavailable")
    if appointment.google_sync_state != "conflict" or appointment.revision != expected_revision:
        raise GoogleLinkError("Appointment changed; refresh and try again")
    conflict = appointment.google_conflict or {}
    observed = conflict.get("remote")
    if (
        conflict.get("observed_revision") != expected_revision
        or ((observed or {}).get("etag") or "") != expected_etag
    ):
        raise GoogleLinkError("Google observation changed; refresh and try again")
    if not appointment.google_event_id or not appointment.google_calendar_id:
        raise GoogleLinkError("Google appointment link requires review")
    if appointment.google_event_id != google_scheduling_adapter.deterministic_event_id(
        appointment.organization_id, appointment.id
    ):
        raise GoogleLinkError("Google appointment ownership requires review")
    _integration(db, appointment)
    binding = _binding_for_link(db, appointment)
    if not binding.is_active or not binding.write_bookings:
        raise GoogleLinkError("Google booking destination changed")
    identity = {
        "event_id": appointment.google_event_id,
        "calendar_id": appointment.google_calendar_id,
        "integration_id": str(appointment.google_integration_id),
        "account_email": appointment.google_account_email,
        "binding_id": str(binding.id),
        "client_email": appointment.client_email,
    }
    appointment_id, org_id, user_id = (
        appointment.id,
        appointment.organization_id,
        appointment.user_id,
    )
    sync_revision = appointment.google_sync_revision
    db.rollback()

    async def fetch_current():
        token = await _v2_token(
            user_id,
            integration_id=UUID(identity["integration_id"]),
            account_email=identity["account_email"],
        )
        if not await google_scheduling_adapter.verify_writable_calendar(
            token, identity["calendar_id"]
        ):
            raise GoogleLinkError("Google appointment calendar is no longer writable")
        return await google_scheduling_adapter.get_event(
            token, identity["calendar_id"], identity["event_id"]
        )

    try:
        remote = run_async(fetch_current())
    except GoogleLinkError:
        raise
    except Exception:
        raise GoogleLinkError("Google appointment could not be verified") from None
    if remote is not None and not _v2_remote_owned(
        remote, identity, organization_id=org_id, appointment_id=appointment_id
    ):
        raise GoogleLinkError("Google appointment identity changed")
    fresh_etag = remote["etag"] if remote else ""
    if fresh_etag != expected_etag:
        raise GoogleLinkError("Google event changed; refresh and try again")

    from app.services import scheduling_v2_service

    scheduling_v2_service._lock_owner(db, org_id, user_id)
    current = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if (
        current is None
        or current.revision != expected_revision
        or current.google_sync_revision != sync_revision
        or current.google_sync_state != "conflict"
        or not _v2_link_matches(current, identity)
        or (current.google_conflict or {}).get("observed_revision") != expected_revision
        or (((current.google_conflict or {}).get("remote") or {}).get("etag") or "")
        != expected_etag
    ):
        db.rollback()
        raise GoogleLinkError("Appointment changed; refresh and try again")
    _integration(db, current)
    binding = _v2_binding(db, current, identity)
    if not binding.is_active or not binding.write_bookings:
        db.rollback()
        raise GoogleLinkError("Google booking destination changed")
    if remote is None:
        remote_snapshot = _interval_snapshot(
            current.scheduled_start,
            current.scheduled_end,
            "cancelled",
            current.client_timezone,
            None,
        )
    else:
        remote_snapshot = _remote_snapshot(remote, timezone_fallback=current.client_timezone)
    if resolution == "google":
        from app.services import appointment_command_service

        try:
            appointment_command_service.apply_external_change(
                db,
                current,
                scheduled_start=remote["start"] if remote else None,
                scheduled_end=remote["end"] if remote else None,
                status="cancelled"
                if remote is None or remote["status"] == "cancelled"
                else "confirmed",
                actor_user_id=actor_user_id,
                timezone=remote["timezone"] if remote else None,
            )
        except ValueError as exc:
            db.rollback()
            raise GoogleLinkError(str(exc)) from exc
        current.google_last_synced = remote_snapshot
        current.google_event_etag = fresh_etag or current.google_event_etag
        current.google_sync_state = "completed"
        current.google_sync_error = None
        current.google_conflict = None
    else:
        if remote is None or remote["status"] == "cancelled":
            db.rollback()
            raise GoogleLinkError("Deleted Google event requires manual review")
        if _values(_local_snapshot(current)) == _values(remote_snapshot):
            current.google_last_synced = remote_snapshot
            current.google_event_etag = fresh_etag
            current.google_sync_state = "completed"
            current.google_sync_error = None
            current.google_conflict = None
        else:
            current.google_last_synced = remote_snapshot
            current.google_event_etag = fresh_etag
            _enqueue_v2_intent(
                db,
                current,
                action="cancel" if current.status == "cancelled" else "reschedule",
                binding_id=binding.id,
                base=remote_snapshot,
            )
    if commit:
        db.commit()


def _parse_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(UTC)


async def process_job(db: Session, job: Job) -> None:
    """Reconcile remote result before conditional mutation; never hold a DB lock over I/O."""
    if (job.payload or {}).get("v2") is True:
        return await _process_v2_job(db, job)
    job_id = job.id
    claim_token = job.claim_token
    org_id = job.organization_id
    payload = dict(job.payload or {})
    appointment_id = UUID(str(payload["appointment_id"]))
    revision = int(payload["revision"])
    integration_id = UUID(str(payload["integration_id"]))
    calendar_id = str(payload["calendar_id"])
    event_id = str(payload["event_id"])
    base_etag = str(payload["etag"])
    base_time = (_parse_time(payload["base_start"]), _parse_time(payload["base_end"]))
    target_time = (_parse_time(payload["target_start"]), _parse_time(payload["target_end"]))
    action = payload["action"]
    if action not in {"reschedule", "cancel"}:
        raise RuntimeError("Unsupported Google appointment sync action")
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .one_or_none()
    )
    if appointment is None or appointment.google_sync_revision != revision:
        db.rollback()
        return
    if (
        appointment.google_sync_state == "completed"
        and appointment.google_event_id == event_id
        and appointment.google_calendar_id == calendar_id
        and appointment.google_integration_id == integration_id
        and (appointment.google_account_email or "").casefold()
        == str(payload["account_email"]).casefold()
    ):
        # The provider result was committed, but the worker may have crashed
        # before it marked this same claimed job complete.
        db.rollback()
        return
    if appointment.google_event_id != event_id or appointment.google_event_etag != base_etag:
        raise RuntimeError("Google appointment binding changed")
    integration = _integration(db, appointment)
    if integration.id != integration_id or appointment.google_calendar_id != calendar_id:
        raise RuntimeError("Google appointment binding changed")
    if integration.account_email.casefold() != str(payload["account_email"]).casefold():
        raise RuntimeError("Google appointment account changed")
    client_email = appointment.client_email.casefold()
    token = await calendar_service.get_google_access_token(db, appointment.user_id)
    if not token:
        raise RuntimeError("Google appointment credentials unavailable")
    db.rollback()

    conflict = False
    success_etag: str | None = None
    try:
        writable_ids = await calendar_service.list_writable_google_calendar_ids(token)
        if calendar_id not in writable_ids:
            raise RuntimeError("Google appointment calendar is no longer writable")
        remote = await calendar_service.get_linked_google_event(token, calendar_id, event_id)
        if remote is not None and remote["id"] != event_id:
            conflict = True
        elif (
            remote is not None
            and remote["status"] != "cancelled"
            and (
                not remote["organizer_self"]
                and str(remote["organizer_email"] or "").casefold() != calendar_id.casefold()
                or client_email not in {email.casefold() for email in remote["attendee_emails"]}
            )
        ):
            conflict = True
        elif action == "cancel" and (remote is None or remote["status"] == "cancelled"):
            success_etag = base_etag
        elif remote is None or remote["status"] == "cancelled":
            conflict = True
        elif (remote["start"], remote["end"]) == target_time and action == "reschedule":
            success_etag = remote["etag"]
        elif remote["etag"] != base_etag or (remote["start"], remote["end"]) != base_time:
            conflict = True
        elif action == "reschedule":
            updated = await calendar_service.update_linked_google_event(
                token,
                calendar_id,
                event_id,
                etag=base_etag,
                start=target_time[0],
                end=target_time[1],
            )
            if (updated["start"], updated["end"]) == target_time:
                success_etag = updated["etag"]
            else:
                conflict = True
        else:
            await calendar_service.delete_linked_google_event(
                token, calendar_id, event_id, etag=base_etag
            )
            success_etag = base_etag
    except calendar_service.GoogleEventConflict:
        conflict = True
    except Exception:
        raise RuntimeError("Google appointment sync failed") from None

    current = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    current_job = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.organization_id == org_id,
            Job.status == JobStatus.RUNNING.value,
            Job.claim_token == claim_token,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if current_job is None or current is None or current.google_sync_revision != revision:
        db.rollback()
        return
    if (
        current.google_calendar_id != calendar_id
        or current.google_integration_id != integration_id
        or current.google_event_id != event_id
        or current.google_event_etag != base_etag
        or (current.google_account_email or "").casefold()
        != str(payload["account_email"]).casefold()
    ):
        db.rollback()
        return
    current.google_sync_state = "conflict" if conflict else "completed"
    if success_etag:
        current.google_event_etag = success_etag
    db.commit()


def _v2_link_matches(appointment: Appointment, payload: dict) -> bool:
    return bool(
        appointment.origin == "crm"
        and appointment.google_event_id == payload.get("event_id")
        and appointment.google_calendar_id == payload.get("calendar_id")
        and str(appointment.google_integration_id) == payload.get("integration_id")
        and (appointment.google_account_email or "").casefold()
        == str(payload.get("account_email") or "").casefold()
    )


def _v2_remote_owned(
    remote: google_scheduling_adapter.GoogleEvent,
    payload: dict,
    *,
    organization_id: UUID,
    appointment_id: UUID,
) -> bool:
    if remote["status"] == "cancelled":
        return (
            remote["id"] == payload["event_id"]
            and remote["calendar_id"] == payload["calendar_id"]
            and remote["id"]
            == google_scheduling_adapter.deterministic_event_id(organization_id, appointment_id)
        )
    return google_scheduling_adapter.owns_event(
        remote,
        organization_id=organization_id,
        appointment_id=appointment_id,
        binding_id=UUID(str(payload["binding_id"])),
        event_id=str(payload["event_id"]),
        calendar_id=str(payload["calendar_id"]),
        client_email=str(payload["client_email"]),
    )


def _v2_binding(db: Session, appointment: Appointment, payload: dict, *, lock: bool = False):
    from app.db.models import CalendarBinding

    try:
        binding_id = UUID(str(payload["binding_id"]))
    except (KeyError, ValueError) as exc:
        raise GoogleLinkError("Google appointment binding is invalid") from exc
    query = (
        db.query(CalendarBinding)
        .filter(
            CalendarBinding.id == binding_id,
            CalendarBinding.organization_id == appointment.organization_id,
            CalendarBinding.user_id == appointment.user_id,
            CalendarBinding.integration_id == appointment.google_integration_id,
            CalendarBinding.account_email == appointment.google_account_email,
            CalendarBinding.calendar_id == appointment.google_calendar_id,
        )
        .populate_existing()
    )
    binding = (query.with_for_update() if lock else query).one_or_none()
    if (
        binding is None
        or not binding.is_active
        or not binding.write_bookings
        or binding.access_role not in {"owner", "writer"}
    ):
        raise GoogleLinkError("Google appointment binding changed or was disabled")
    return binding


def _v2_older_unfinished(
    db: Session, appointment: Appointment, revision: int, job_id: UUID
) -> bool:
    jobs = (
        db.query(Job.idempotency_key)
        .filter(
            Job.organization_id == appointment.organization_id,
            Job.id != job_id,
            Job.job_type == JobType.APPOINTMENT_GOOGLE_SYNC.value,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
            Job.idempotency_key.like(f"appointment-google:{appointment.id}:%"),
        )
        .all()
    )
    for (key,) in jobs:
        try:
            if int(key.rsplit(":", 1)[1]) < revision:
                return True
        except IndexError, TypeError, ValueError:
            continue
    return False


def _v2_lock_claim(db: Session, appointment_id: UUID, org_id: UUID, job_id: UUID, claim_token):
    current = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    claimed = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.organization_id == org_id,
            Job.status == JobStatus.RUNNING.value,
            Job.claim_token == claim_token,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    return current, claimed


def _v2_defer(
    db: Session,
    *,
    appointment_id: UUID,
    org_id: UUID,
    job_id: UUID,
    claim_token,
    delay_seconds: int = 15,
) -> bool:
    current, claimed = _v2_lock_claim(db, appointment_id, org_id, job_id, claim_token)
    if current is None or claimed is None:
        db.rollback()
        return False
    claimed.status = JobStatus.PENDING.value
    claimed.run_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    claimed.claim_token = None
    claimed.claimed_at = None
    db.commit()
    return False


def _v2_parse_target(payload: dict) -> tuple[datetime, datetime, str, str]:
    target = payload.get("target")
    if not isinstance(target, dict):
        raise RuntimeError("Google appointment intent is incomplete")
    start = _parse_time(target["start"])
    end = _parse_time(target["end"])
    status_value = str(target["status"])
    timezone_name = str(target.get("timezone") or "UTC")
    if end <= start or status_value not in {"confirmed", "cancelled"}:
        raise RuntimeError("Google appointment intent is invalid")
    return start, end, status_value, timezone_name


def _v2_provider_values(
    remote: google_scheduling_adapter.GoogleEvent | None, timezone_name: str
) -> tuple[datetime | None, datetime | None, str | None, str | None]:
    if remote is None:
        return None, None, None, None
    return (
        remote["start"],
        remote["end"],
        "cancelled" if remote["status"] == "cancelled" else "confirmed",
        remote["timezone"] or timezone_name,
    )


def _v2_base_values(
    base: dict | None,
) -> tuple[datetime | None, datetime | None, str | None, str | None]:
    if not base:
        return None, None, None, None
    return (
        _parse_time(base["start"]) if base.get("start") else None,
        _parse_time(base["end"]) if base.get("end") else None,
        base.get("status"),
        base.get("timezone") or "UTC",
    )


def _v2_previous_create_target(db: Session, appointment: Appointment, revision: int):
    jobs = (
        db.query(Job.payload)
        .filter(
            Job.organization_id == appointment.organization_id,
            Job.job_type == JobType.APPOINTMENT_GOOGLE_SYNC.value,
            Job.idempotency_key.like(f"appointment-google:{appointment.id}:%"),
        )
        .all()
    )
    candidates = []
    for (payload,) in jobs:
        if payload.get("v2") is True and payload.get("action") == "create":
            try:
                old_revision = int(payload["revision"])
            except KeyError, TypeError, ValueError:
                continue
            if old_revision < revision:
                candidates.append((old_revision, payload.get("target")))
    return max(candidates, default=(None, None))[1]


async def _v2_token(user_id: UUID, *, integration_id: UUID, account_email: str) -> str:
    with SessionLocal() as credential_db:
        integration = (
            credential_db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.integration_type == "google_calendar",
            )
            .one_or_none()
        )
        if (
            integration is None
            or integration.id != integration_id
            or (integration.account_email or "").casefold() != account_email.casefold()
        ):
            raise GoogleLinkError("Google account changed; review the appointment link")
        token = await calendar_service.get_google_access_token(credential_db, user_id)
        credential_db.expire_all()
        integration = (
            credential_db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.integration_type == "google_calendar",
            )
            .one_or_none()
        )
        if (
            integration is None
            or integration.id != integration_id
            or (integration.account_email or "").casefold() != account_email.casefold()
        ):
            raise GoogleLinkError("Google account changed; review the appointment link")
    if not token:
        raise GoogleLinkError("Reconnect the appointment owner's Google Calendar")
    return token


async def _process_v2_job(db: Session, job: Job) -> bool | None:
    """Deliver one immutable v2 intent with no row lock held during HTTP."""
    payload = dict(job.payload or {})
    action = payload.get("action")
    if action not in {"create", "reschedule", "cancel"}:
        raise RuntimeError("Unsupported Google appointment sync action")
    job_id, claim_token, org_id = job.id, job.claim_token, job.organization_id
    appointment_id = UUID(str(payload["appointment_id"]))
    revision = int(payload["revision"])
    if not _v2_enabled():
        db.rollback()
        return _v2_defer(
            db,
            appointment_id=appointment_id,
            org_id=org_id,
            job_id=job_id,
            claim_token=claim_token,
            delay_seconds=3600,
        )
    target_start, target_end, target_status, target_timezone = _v2_parse_target(payload)
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .one_or_none()
    )
    if appointment is None or not _v2_link_matches(appointment, payload):
        db.rollback()
        raise GoogleLinkError("Google appointment binding changed")
    if appointment.google_sync_revision != revision:
        db.rollback()
        return None
    if (
        appointment.google_sync_state == "completed"
        and appointment.google_sync_revision == revision
    ):
        db.rollback()
        return None
    if appointment.google_sync_state != "pending":
        db.rollback()
        return None
    _integration(db, appointment)
    _v2_binding(db, appointment, payload)
    if _v2_older_unfinished(db, appointment, revision, job_id):
        db.rollback()
        return _v2_defer(
            db,
            appointment_id=appointment_id,
            org_id=org_id,
            job_id=job_id,
            claim_token=claim_token,
        )
    base = (
        dict(appointment.google_last_synced)
        if appointment.google_last_synced
        else payload.get("base")
    )
    prior_create_target = (
        _v2_previous_create_target(db, appointment, revision)
        if action == "cancel" and base is None
        else None
    )
    user_id = appointment.user_id
    db.rollback()

    token = await _v2_token(
        user_id,
        integration_id=UUID(payload["integration_id"]),
        account_email=payload["account_email"],
    )
    try:
        if not await google_scheduling_adapter.verify_writable_calendar(
            token, payload["calendar_id"]
        ):
            raise GoogleLinkError("Google appointment calendar is no longer writable")
        remote = await google_scheduling_adapter.get_event(
            token, payload["calendar_id"], payload["event_id"]
        )
        identity_conflict = remote is not None and not _v2_remote_owned(
            remote, payload, organization_id=org_id, appointment_id=appointment_id
        )
        provider_values = _v2_provider_values(remote, target_timezone)
        target_values = (target_start, target_end, target_status, target_timezone)
        base_values = _v2_base_values(base)
        conflict_code: str | None = "provider_identity_mismatch" if identity_conflict else None
        if identity_conflict:
            pass
        elif action == "create":
            if remote is None:
                try:
                    remote = await google_scheduling_adapter.insert_event(
                        token,
                        payload["calendar_id"],
                        event_id=payload["event_id"],
                        organization_id=org_id,
                        appointment_id=appointment_id,
                        binding_id=UUID(str(payload["binding_id"])),
                        start=target_start,
                        end=target_end,
                        timezone_name=target_timezone,
                        client_email=payload["client_email"],
                        create_meet=payload.get("meeting_mode") == "google_meet",
                    )
                except google_scheduling_adapter.GoogleResourceCollision:
                    remote = await google_scheduling_adapter.get_event(
                        token, payload["calendar_id"], payload["event_id"]
                    )
                    if remote is None:
                        raise GoogleLinkError("Google event ID collision requires review") from None
                except Exception:
                    # An insert response can be lost after Google created the event.
                    remote = await google_scheduling_adapter.get_event(
                        token, payload["calendar_id"], payload["event_id"]
                    )
                    if remote is None:
                        raise RuntimeError("Google appointment creation outcome unknown") from None
                if remote is not None and not _v2_remote_owned(
                    remote, payload, organization_id=org_id, appointment_id=appointment_id
                ):
                    conflict_code = "provider_identity_mismatch"
            elif provider_values != target_values:
                if base and provider_values == base_values and remote["etag"] == base.get("etag"):
                    remote = await google_scheduling_adapter.patch_interval(
                        token,
                        payload["calendar_id"],
                        payload["event_id"],
                        etag=remote["etag"],
                        start=target_start,
                        end=target_end,
                        timezone_name=target_timezone,
                    )
                else:
                    conflict_code = "concurrent_edit"
            elif payload.get("meeting_mode") == "google_meet" and remote["conference_failed"]:
                remote = await google_scheduling_adapter.request_meet_conference(
                    token,
                    payload["calendar_id"],
                    payload["event_id"],
                    etag=remote["etag"],
                    request_id=f"{payload['event_id']}meet{revision}",
                )
        elif action == "reschedule":
            if remote is None or remote["status"] == "cancelled":
                conflict_code = "provider_event_missing"
            elif provider_values == target_values:
                pass
            elif base and provider_values == base_values and remote["etag"] == base.get("etag"):
                remote = await google_scheduling_adapter.patch_interval(
                    token,
                    payload["calendar_id"],
                    payload["event_id"],
                    etag=remote["etag"],
                    start=target_start,
                    end=target_end,
                    timezone_name=target_timezone,
                )
            else:
                conflict_code = "concurrent_edit"
        else:
            if remote is None or remote["status"] == "cancelled":
                pass
            elif base and provider_values == base_values and remote["etag"] == base.get("etag"):
                await google_scheduling_adapter.delete_event(
                    token, payload["calendar_id"], payload["event_id"], etag=remote["etag"]
                )
                remote = None
            elif prior_create_target and provider_values == _v2_base_values(prior_create_target):
                await google_scheduling_adapter.delete_event(
                    token, payload["calendar_id"], payload["event_id"], etag=remote["etag"]
                )
                remote = None
            else:
                conflict_code = "concurrent_edit"
    except google_scheduling_adapter.GooglePreconditionFailed:
        conflict_code = "provider_version_changed"
        try:
            remote = await google_scheduling_adapter.get_event(
                token, payload["calendar_id"], payload["event_id"]
            )
        except Exception:
            remote = None
    except GoogleLinkError:
        raise
    except Exception:
        raise RuntimeError("Google appointment sync failed") from None

    if action == "cancel" and conflict_code is None:
        result_snapshot = _interval_snapshot(
            target_start,
            target_end,
            "cancelled",
            target_timezone,
            remote["etag"] if remote else None,
        )
    elif remote is not None:
        result_snapshot = _remote_snapshot(remote, timezone_fallback=target_timezone)
    else:
        result_snapshot = None

    current, claimed = _v2_lock_claim(db, appointment_id, org_id, job_id, claim_token)
    if current is None or claimed is None or not _v2_link_matches(current, payload):
        db.rollback()
        return None
    if current.google_sync_revision != revision:
        if (
            conflict_code is None
            and result_snapshot is not None
            and current.google_sync_state == "pending"
            and _values(current.google_last_synced) == _values(base)
        ):
            current.google_last_synced = result_snapshot
            current.google_event_etag = result_snapshot["etag"]
            db.commit()
        else:
            db.rollback()
        return None
    if current.google_sync_state != "pending":
        db.rollback()
        return None
    try:
        _integration(db, current)
        _v2_binding(db, current, payload, lock=True)
    except GoogleLinkError:
        current.google_sync_state = "unlinked"
        current.google_sync_error = "booking_binding_changed"
        db.commit()
        return None
    if conflict_code:
        current.google_sync_state = "conflict"
        current.google_sync_error = conflict_code
        current.google_conflict = {
            "base": base,
            "local": _local_snapshot(current),
            "remote": result_snapshot,
            "observed_revision": current.revision,
        }
        db.commit()
        return None
    if result_snapshot is not None:
        current.google_last_synced = result_snapshot
        if result_snapshot["etag"]:
            current.google_event_etag = result_snapshot["etag"]
    if remote is not None and remote["conference_url"]:
        current.google_meet_url = remote["conference_url"]
    if (
        action == "create"
        and payload.get("meeting_mode") == "google_meet"
        and remote is not None
        and (remote["conference_failed"] or not remote["conference_url"])
    ):
        if remote["conference_failed"] or datetime.now(UTC) - claimed.created_at > timedelta(
            minutes=10
        ):
            current.google_sync_state = "failed"
            current.google_sync_error = (
                "conference_failed" if remote["conference_failed"] else "conference_missing"
            )
            claimed.status = JobStatus.FAILED.value
            claimed.claim_token = None
            claimed.claimed_at = None
            db.commit()
            return False
        current.google_sync_state = "pending"
        claimed.status = JobStatus.PENDING.value
        claimed.run_at = datetime.now(UTC) + timedelta(seconds=15)
        claimed.claim_token = None
        claimed.claimed_at = None
        db.commit()
        return False
    current.google_sync_state = "completed"
    current.google_sync_error = None
    current.google_conflict = None
    db.commit()
    return None
