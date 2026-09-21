"""Durable, conditional Google delivery for CRM-owned appointments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.db.enums import JobStatus, JobType
from app.db.models import Appointment, Job, Membership, User, UserIntegration
from app.db.session import SessionLocal
from app.services import calendar_service, job_service


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
    if appointment is None or not appointment.google_event_id:
        return None
    if appointment.google_sync_state in {"conflict", "unlinked"}:
        return appointment.google_sync_state
    job = _job(db, appointment)
    if job is None:
        return None
    if job.status in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
        return "pending"
    if job.status == JobStatus.FAILED.value:
        return "failed"
    return "completed" if appointment.google_sync_state == "completed" else None


def retry(db: Session, appointment: Appointment) -> None:
    current = status(db, appointment)
    if current in {"pending", "completed"}:
        return
    if current != "failed":
        raise GoogleLinkError("Google sync cannot be retried until the link is reviewed")
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
    db.commit()


def _parse_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(UTC)


async def process_job(db: Session, job: Job) -> None:
    """Reconcile remote result before conditional mutation; never hold a DB lock over I/O."""
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
