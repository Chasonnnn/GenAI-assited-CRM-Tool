"""Google Calendar sync orchestration helpers.

Keeps router layers thin by moving model access + job enqueue logic into services.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import JobType
from app.db.models import Job, Membership, Organization, UserIntegration
from app.services import calendar_service, google_tasks_sync_service, job_service

logger = logging.getLogger(__name__)


class GoogleCalendarSyncScheduleCounts(TypedDict):
    connected_users: int
    jobs_created: int
    duplicates_skipped: int
    task_jobs_created: int
    task_duplicates_skipped: int
    watch_jobs_created: int
    watch_duplicates_skipped: int


def _scheduling_v2_enabled() -> bool:
    from app.core.config import settings

    return bool(getattr(settings, "SCHEDULING_V2_ENABLED", False))


def _schedule_v2_binding_jobs(
    db: Session,
    *,
    now: datetime,
) -> GoogleCalendarSyncScheduleCounts:
    """Schedule only explicit binding targets; never select a user's first org."""
    from app.db.models import CalendarBinding
    from app.services import calendar_binding_service

    bindings = (
        db.query(CalendarBinding)
        .join(Membership, Membership.user_id == CalendarBinding.user_id)
        .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
        .join(Organization, Organization.id == CalendarBinding.organization_id)
        .filter(
            CalendarBinding.is_active.is_(True),
            Membership.organization_id == CalendarBinding.organization_id,
            Membership.is_active.is_(True),
            UserIntegration.user_id == CalendarBinding.user_id,
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.account_email == CalendarBinding.account_email,
            Organization.deleted_at.is_(None),
        )
        .all()
    )
    created = 0
    duplicates = 0
    watch_created = 0
    watch_duplicates = 0
    for binding in bindings:
        try:
            with db.begin_nested():
                calendar_binding_service.enqueue_binding_sync(
                    db,
                    binding_id=binding.id,
                    org_id=binding.organization_id,
                    commit=False,
                    now=now,
                )
            created += 1
        except IntegrityError:
            duplicates += 1
        try:
            with db.begin_nested():
                calendar_binding_service.enqueue_binding_watch_refresh(
                    db,
                    binding_id=binding.id,
                    org_id=binding.organization_id,
                    commit=False,
                    now=now,
                )
            watch_created += 1
        except IntegrityError:
            watch_duplicates += 1

    # Tasks remain user-scoped legacy behavior; V2 only retires ambiguous calendar routing.
    task_targets = (
        db.query(
            UserIntegration.user_id, Membership.organization_id, UserIntegration.granted_scopes
        )
        .join(Membership, Membership.user_id == UserIntegration.user_id)
        .join(Organization, Organization.id == Membership.organization_id)
        .filter(
            UserIntegration.integration_type == "google_calendar",
            Membership.is_active.is_(True),
            Organization.deleted_at.is_(None),
        )
        .all()
    )
    sync_bucket = int(now.timestamp()) // (5 * 60)
    seen_task_users: set[UUID] = set()
    task_jobs_created = 0
    task_duplicates_skipped = 0
    for user_id, organization_id, granted_scopes in task_targets:
        if user_id in seen_task_users:
            continue
        seen_task_users.add(user_id)
        if google_tasks_sync_service.scopes_known_to_exclude_google_tasks(granted_scopes):
            task_duplicates_skipped += 1
            continue
        idempotency_key = f"google-tasks-sync:{user_id}:{sync_bucket}"
        try:
            with db.begin_nested():
                job_service.enqueue_job(
                    db,
                    org_id=organization_id,
                    job_type=JobType.GOOGLE_TASKS_SYNC,
                    payload={"user_id": str(user_id)},
                    run_at=now + timedelta(seconds=(user_id.int % 120)),
                    idempotency_key=idempotency_key,
                    commit=False,
                )
            task_jobs_created += 1
        except IntegrityError:
            task_duplicates_skipped += 1
    db.commit()
    return {
        "connected_users": len(bindings),
        "jobs_created": created,
        "duplicates_skipped": duplicates,
        "task_jobs_created": task_jobs_created,
        "task_duplicates_skipped": task_duplicates_skipped,
        "watch_jobs_created": watch_created,
        "watch_duplicates_skipped": watch_duplicates,
    }


def schedule_google_calendar_sync_jobs(
    db: Session,
    *,
    now: datetime | None = None,
) -> GoogleCalendarSyncScheduleCounts:
    """Schedule reconciliation + watch-refresh jobs for connected users."""
    now = now or datetime.now(UTC)
    if _scheduling_v2_enabled():
        return _schedule_v2_binding_jobs(db, now=now)
    sync_bucket_seconds = 5 * 60
    sync_bucket = int(now.timestamp()) // sync_bucket_seconds
    watch_bucket_seconds = 60 * 60
    watch_bucket = int(now.timestamp()) // watch_bucket_seconds

    connected = (
        db.query(
            UserIntegration.user_id,
            Membership.organization_id,
            UserIntegration.granted_scopes,
        )
        .join(Membership, Membership.user_id == UserIntegration.user_id)
        .join(Organization, Organization.id == Membership.organization_id)
        .filter(
            UserIntegration.integration_type == "google_calendar",
            Membership.is_active.is_(True),
            Organization.deleted_at.is_(None),
        )
        .all()
    )

    # De-dupe by user to guard against accidental duplicate rows.
    seen_users = set()
    targets: list[tuple[str, str, object]] = []
    for user_id, org_id, granted_scopes in connected:
        key = str(user_id)
        if key in seen_users:
            continue
        seen_users.add(key)
        targets.append((str(user_id), str(org_id), granted_scopes))

    connected_users = len(targets)
    jobs_created = 0
    duplicates_skipped = 0
    task_jobs_created = 0
    task_duplicates_skipped = 0
    watch_jobs_created = 0
    watch_duplicates_skipped = 0

    candidate_idempotency_keys: set[str] = set()
    for user_id, _org_id, granted_scopes in targets:
        candidate_idempotency_keys.add(f"google-calendar-sync:{user_id}:{sync_bucket}")
        candidate_idempotency_keys.add(f"google-calendar-watch-refresh:{user_id}:{watch_bucket}")
        if not google_tasks_sync_service.scopes_known_to_exclude_google_tasks(granted_scopes):
            candidate_idempotency_keys.add(f"google-tasks-sync:{user_id}:{sync_bucket}")
    existing_idempotency_keys: set[str] = set()
    if candidate_idempotency_keys:
        existing_idempotency_keys = {
            key
            for (key,) in db.query(Job.idempotency_key)
            .filter(Job.idempotency_key.in_(candidate_idempotency_keys))
            .all()
        }

    for user_id, org_id, granted_scopes in targets:
        try:
            idempotency_key = f"google-calendar-sync:{user_id}:{sync_bucket}"
            if idempotency_key in existing_idempotency_keys:
                duplicates_skipped += 1
            else:
                run_at = now + timedelta(seconds=(UUID(user_id).int % 120))
                job_service.schedule_job(
                    db=db,
                    job_type=JobType.GOOGLE_CALENDAR_SYNC,
                    org_id=UUID(org_id),
                    payload={"user_id": user_id},
                    run_at=run_at,
                    idempotency_key=idempotency_key,
                )
                existing_idempotency_keys.add(idempotency_key)
                jobs_created += 1
        except IntegrityError:
            db.rollback()
            duplicates_skipped += 1
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to enqueue google calendar sync job for user=%s org=%s",
                user_id,
                org_id,
            )
            raise

        if google_tasks_sync_service.scopes_known_to_exclude_google_tasks(granted_scopes):
            task_duplicates_skipped += 1
        else:
            try:
                task_idempotency_key = f"google-tasks-sync:{user_id}:{sync_bucket}"
                if task_idempotency_key in existing_idempotency_keys:
                    task_duplicates_skipped += 1
                else:
                    task_run_at = now + timedelta(seconds=(UUID(user_id).int % 120))
                    job_service.schedule_job(
                        db=db,
                        job_type=JobType.GOOGLE_TASKS_SYNC,
                        org_id=UUID(org_id),
                        payload={"user_id": user_id},
                        run_at=task_run_at,
                        idempotency_key=task_idempotency_key,
                    )
                    existing_idempotency_keys.add(task_idempotency_key)
                    task_jobs_created += 1
            except IntegrityError:
                db.rollback()
                task_duplicates_skipped += 1
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to enqueue google tasks sync job for user=%s org=%s",
                    user_id,
                    org_id,
                )
                raise

        try:
            watch_idempotency_key = f"google-calendar-watch-refresh:{user_id}:{watch_bucket}"
            if watch_idempotency_key in existing_idempotency_keys:
                watch_duplicates_skipped += 1
                continue

            watch_run_at = now + timedelta(seconds=(UUID(user_id).int % 300))
            job_service.schedule_job(
                db=db,
                job_type=JobType.GOOGLE_CALENDAR_WATCH_REFRESH,
                org_id=UUID(org_id),
                payload={"user_id": user_id},
                run_at=watch_run_at,
                idempotency_key=watch_idempotency_key,
            )
            existing_idempotency_keys.add(watch_idempotency_key)
            watch_jobs_created += 1
        except IntegrityError:
            db.rollback()
            watch_duplicates_skipped += 1
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to enqueue google calendar watch refresh job for user=%s org=%s",
                user_id,
                org_id,
            )
            raise

    return {
        "connected_users": connected_users,
        "jobs_created": jobs_created,
        "duplicates_skipped": duplicates_skipped,
        "task_jobs_created": task_jobs_created,
        "task_duplicates_skipped": task_duplicates_skipped,
        "watch_jobs_created": watch_jobs_created,
        "watch_duplicates_skipped": watch_duplicates_skipped,
    }


def process_google_calendar_push_notification(
    db: Session,
    *,
    channel_id: str | None,
    resource_id: str | None,
    channel_token: str | None,
    message_number: str,
    resource_state: str,
    now: datetime | None = None,
) -> dict[str, str]:
    """
    Validate push headers and enqueue immediate reconciliation when authorized.

    Returns a short status payload for 202 responses.
    """
    if not channel_id or not resource_id or not channel_token:
        return {"status": "ignored", "reason": "missing_headers"}

    if _scheduling_v2_enabled():
        from app.db.models import CalendarBinding
        from app.services import calendar_binding_service

        bindings = (
            db.query(CalendarBinding)
            .join(Membership, Membership.user_id == CalendarBinding.user_id)
            .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
            .filter(
                CalendarBinding.is_active.is_(True),
                CalendarBinding.channel_id == channel_id,
                CalendarBinding.resource_id == resource_id,
                Membership.organization_id == CalendarBinding.organization_id,
                Membership.is_active.is_(True),
                UserIntegration.user_id == CalendarBinding.user_id,
                UserIntegration.integration_type == "google_calendar",
                UserIntegration.account_email == CalendarBinding.account_email,
            )
            .all()
        )
        if not bindings:
            return {"status": "ignored", "reason": "unknown_channel"}
        accepted = False
        for binding in bindings:
            if not calendar_service.verify_watch_channel_token(
                binding.channel_token_encrypted, channel_token
            ):
                continue
            try:
                calendar_binding_service.enqueue_binding_sync(
                    db,
                    binding_id=binding.id,
                    org_id=binding.organization_id,
                    commit=True,
                )
                accepted = True
            except IntegrityError:
                db.rollback()
                accepted = True
        return (
            {"status": "accepted"} if accepted else {"status": "ignored", "reason": "invalid_token"}
        )

    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.google_calendar_channel_id == channel_id,
            UserIntegration.google_calendar_resource_id == resource_id,
        )
        .first()
    )
    if not integration:
        return {"status": "ignored", "reason": "unknown_channel"}

    if not calendar_service.verify_watch_channel_token(
        integration.google_calendar_channel_token_encrypted,
        channel_token,
    ):
        logger.warning(
            "Ignored Google Calendar push with invalid channel token user=%s channel=%s",
            integration.user_id,
            channel_id,
        )
        return {"status": "ignored", "reason": "invalid_token"}

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == integration.user_id, Membership.is_active.is_(True))
        .first()
    )
    if not membership:
        return {"status": "ignored", "reason": "inactive_membership"}

    idempotency_key = f"google-calendar-push:{channel_id}:{message_number}"
    existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    if existing:
        return {"status": "accepted"}

    try:
        job_service.enqueue_job(
            db=db,
            org_id=membership.organization_id,
            job_type=JobType.GOOGLE_CALENDAR_SYNC,
            payload={
                "user_id": str(integration.user_id),
                "source": "google_push",
                "resource_state": resource_state,
            },
            run_at=now or datetime.now(UTC),
            idempotency_key=idempotency_key,
            commit=True,
        )
    except IntegrityError:
        db.rollback()

    return {"status": "accepted"}
