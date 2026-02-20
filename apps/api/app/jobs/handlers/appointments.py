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

    updated_count = appointment_integrations.sync_manual_google_events_for_appointments(
        db=db,
        user_id=user_id,
        org_id=job.organization_id,
        date_start=date_start,
        date_end=date_end,
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

    changed_count = google_tasks_sync_service.sync_google_tasks_for_user(
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
