"""Appointment-related job handlers."""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_google_calendar_sync(db, job) -> None:
    """
    Reconcile Google Calendar events for a single user into CRM appointments.

    Payload:
      - user_id (required): target user UUID
      - date_start (optional): ISO date YYYY-MM-DD
      - date_end (optional): ISO date YYYY-MM-DD
    """
    from app.services import appointment_integrations

    payload = job.payload or {}
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        raise ValueError("Missing user_id in google_calendar_sync payload")

    try:
        user_id = UUID(str(user_id_raw))
    except ValueError as exc:
        raise ValueError("Invalid user_id in google_calendar_sync payload") from exc

    date_start_raw = payload.get("date_start")
    date_end_raw = payload.get("date_end")
    date_start = None
    date_end = None
    if date_start_raw:
        try:
            date_start = date.fromisoformat(str(date_start_raw))
        except ValueError as exc:
            raise ValueError("Invalid date_start format in google_calendar_sync payload") from exc
    if date_end_raw:
        try:
            date_end = date.fromisoformat(str(date_end_raw))
        except ValueError as exc:
            raise ValueError("Invalid date_end format in google_calendar_sync payload") from exc

    updated_count = await appointment_integrations.sync_manual_google_events_for_appointments_async(
        db=db,
        user_id=user_id,
        org_id=job.organization_id,
        date_start=date_start,
        date_end=date_end,
        strict=True,
    )
    db.commit()
    logger.info(
        "Google calendar sync complete for user=%s org=%s updated=%s",
        user_id,
        job.organization_id,
        updated_count,
    )


async def process_google_calendar_watch_refresh(db, job) -> None:
    """
    Ensure a Google Calendar push channel exists and is fresh for a user.

    Payload:
      - user_id (required): target user UUID
    """
    from app.services import calendar_service

    payload = job.payload or {}
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        raise ValueError("Missing user_id in google_calendar_watch_refresh payload")

    try:
        user_id = UUID(str(user_id_raw))
    except ValueError as exc:
        raise ValueError("Invalid user_id in google_calendar_watch_refresh payload") from exc

    refreshed = await calendar_service.ensure_google_calendar_watch(
        db=db,
        user_id=user_id,
        calendar_id="primary",
    )
    logger.info(
        "Google calendar watch ensured for user=%s org=%s refreshed=%s",
        user_id,
        job.organization_id,
        refreshed,
    )


async def process_google_tasks_sync(db, job) -> None:
    """
    Reconcile Google Tasks for a single user into platform tasks.

    Payload:
      - user_id (required): target user UUID
    """
    from app.services import google_tasks_sync_service

    payload = job.payload or {}
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        raise ValueError("Missing user_id in google_tasks_sync payload")

    try:
        user_id = UUID(str(user_id_raw))
    except ValueError as exc:
        raise ValueError("Invalid user_id in google_tasks_sync payload") from exc

    google_tasks_sync_service.require_active_google_tasks_membership(
        db,
        org_id=job.organization_id,
        user_id=user_id,
        lock=True,
    )

    changed_count = await google_tasks_sync_service.sync_google_tasks_for_user_async(
        db=db,
        user_id=user_id,
        org_id=job.organization_id,
    )
    db.commit()
    logger.info(
        "Google tasks sync complete for user=%s org=%s changed=%s",
        user_id,
        job.organization_id,
        changed_count,
    )


async def process_google_task_creation_reconcile(db, job) -> None:
    """Recover or erase one donor task whose Google POST outcome was uncertain."""
    from app.services import google_tasks_sync_service

    await google_tasks_sync_service.reconcile_uncertain_google_donor_task_creation(db, job)
    db.commit()


async def process_google_task_remote_delete(db, job) -> None:
    """Idempotently erase one tombstoned Google task."""
    from app.services import google_tasks_cleanup_service, google_tasks_sync_service

    target = google_tasks_cleanup_service.validate_cleanup_job_target(db, job)
    concrete_task_list_id = await google_tasks_sync_service.delete_google_task_for_cleanup(
        db,
        user_id=target.user_id,
        google_task_list_id=target.google_task_list_id,
        google_task_id=target.google_task_id,
    )
    if concrete_task_list_id != target.google_task_list_id:
        google_tasks_cleanup_service.persist_concrete_cleanup_task_list_identity(
            db,
            job,
            target=target,
            google_task_list_id=concrete_task_list_id,
        )
    google_tasks_cleanup_service.reactivate_creation_recovery_after_cleanup(db, job)
    db.commit()
