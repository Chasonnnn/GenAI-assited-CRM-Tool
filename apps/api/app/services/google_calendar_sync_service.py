"""Google Calendar sync orchestration helpers.

Keeps router layers thin by moving model access + job enqueue logic into services.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import JobType
from app.db.models import Job, Membership, Organization, UserIntegration
from app.services import calendar_service, job_service

logger = logging.getLogger(__name__)


class GoogleCalendarSyncScheduleCounts(TypedDict):
    connected_users: int
    jobs_created: int
    duplicates_skipped: int
    task_jobs_created: int
    task_duplicates_skipped: int
    watch_jobs_created: int
    watch_duplicates_skipped: int


def schedule_google_calendar_sync_jobs(
    db: Session,
    *,
    now: datetime | None = None,
) -> GoogleCalendarSyncScheduleCounts:
    """Schedule reconciliation + watch-refresh jobs for connected users."""
    now = now or datetime.now(timezone.utc)
    sync_bucket_seconds = 5 * 60
    sync_bucket = int(now.timestamp()) // sync_bucket_seconds
    watch_bucket_seconds = 60 * 60
    watch_bucket = int(now.timestamp()) // watch_bucket_seconds

    connected = (
        db.query(UserIntegration.user_id, Membership.organization_id)
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
    targets: list[tuple[str, str]] = []
    for user_id, org_id in connected:
        key = str(user_id)
        if key in seen_users:
            continue
        seen_users.add(key)
        targets.append((str(user_id), str(org_id)))

    connected_users = len(targets)
    jobs_created = 0
    duplicates_skipped = 0
    task_jobs_created = 0
    task_duplicates_skipped = 0
    watch_jobs_created = 0
    watch_duplicates_skipped = 0

    for user_id, org_id in targets:
        try:
            idempotency_key = f"google-calendar-sync:{user_id}:{sync_bucket}"
            existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
            if existing:
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

        try:
            task_idempotency_key = f"google-tasks-sync:{user_id}:{sync_bucket}"
            task_existing = (
                db.query(Job).filter(Job.idempotency_key == task_idempotency_key).first()
            )
            if task_existing:
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
            watch_existing = (
                db.query(Job).filter(Job.idempotency_key == watch_idempotency_key).first()
            )
            if watch_existing:
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
            run_at=now or datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
            commit=True,
        )
    except IntegrityError:
        db.rollback()

    return {"status": "accepted"}
