"""Dashboard service - data for dashboard widgets."""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import asyncio
import logging
import threading

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.db.enums import OwnerType, TaskType
from app.db.models import Surrogate, Task, ZoomMeeting

logger = logging.getLogger(__name__)


def get_upcoming_items(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    days: int,
    include_overdue: bool,
) -> tuple[list[dict], list[dict]]:
    """Get upcoming tasks and meetings for dashboard widgets."""
    now = datetime.now(timezone.utc)
    today = now.date()
    end_date = today + timedelta(days=days)

    task_filters = [
        Task.organization_id == org_id,
        Task.is_completed.is_(False),
        Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        and_(Task.owner_type == OwnerType.USER.value, Task.owner_id == user_id),
    ]

    if include_overdue:
        task_filters.append(
            or_(
                Task.due_date < today,
                and_(Task.due_date >= today, Task.due_date <= end_date),
            )
        )
    else:
        task_filters.append(and_(Task.due_date >= today, Task.due_date <= end_date))

    tasks = (
        db.query(Task)
        .filter(and_(*task_filters))
        .order_by(Task.due_date, Task.due_time)
        .limit(50)
        .all()
    )

    surrogate_ids = {t.surrogate_id for t in tasks if t.surrogate_id}
    surrogates = (
        {}
        if not surrogate_ids
        else {
            s.id: s
            for s in db.query(Surrogate)
            .filter(Surrogate.organization_id == org_id, Surrogate.id.in_(surrogate_ids))
            .all()
        }
    )

    task_items = []
    for task in tasks:
        surrogate = surrogates.get(task.surrogate_id) if task.surrogate_id else None
        is_overdue = task.due_date < today if task.due_date else False
        task_items.append(
            {
                "id": str(task.id),
                "type": "task",
                "title": task.title,
                "time": task.due_time.strftime("%H:%M") if task.due_time else None,
                "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
                "surrogate_number": surrogate.surrogate_number if surrogate else None,
                "date": task.due_date.isoformat() if task.due_date else today.isoformat(),
                "is_overdue": is_overdue,
                "task_type": task.task_type or "general",
            }
        )

    meeting_filters = [
        ZoomMeeting.organization_id == org_id,
        ZoomMeeting.user_id == user_id,
        ZoomMeeting.start_time.isnot(None),
        ZoomMeeting.start_time >= now - timedelta(hours=1),
        ZoomMeeting.start_time <= now + timedelta(days=days),
    ]

    meetings = (
        db.query(ZoomMeeting)
        .filter(and_(*meeting_filters))
        .order_by(ZoomMeeting.start_time)
        .limit(20)
        .all()
    )

    meeting_surrogate_ids = {m.surrogate_id for m in meetings if m.surrogate_id}
    meeting_surrogates = (
        {}
        if not meeting_surrogate_ids
        else {
            s.id: s
            for s in db.query(Surrogate)
            .filter(Surrogate.organization_id == org_id, Surrogate.id.in_(meeting_surrogate_ids))
            .all()
        }
    )

    meeting_items = []
    for meeting in meetings:
        surrogate = meeting_surrogates.get(meeting.surrogate_id) if meeting.surrogate_id else None
        meeting_date = meeting.start_time.date() if meeting.start_time else today
        meeting_items.append(
            {
                "id": str(meeting.id),
                "type": "meeting",
                "title": meeting.topic,
                "time": meeting.start_time.strftime("%H:%M") if meeting.start_time else None,
                "surrogate_id": str(meeting.surrogate_id) if meeting.surrogate_id else None,
                "surrogate_number": surrogate.surrogate_number if surrogate else None,
                "date": meeting_date.isoformat(),
                "is_overdue": False,
                "join_url": meeting.join_url,
            }
        )

    return task_items, meeting_items


# =============================================================================
# Realtime dashboard updates
# =============================================================================


def push_dashboard_stats(db: Session, org_id: UUID) -> None:
    """Compute and push dashboard stats to connected org clients."""
    from app.services import surrogate_service

    try:
        stats = surrogate_service.get_surrogate_stats(db, org_id)
    except Exception:
        logger.exception("Failed to build dashboard stats for websocket push")
        return

    _schedule_ws_send(_send_dashboard_stats(org_id, stats))


def _schedule_ws_send(coro: asyncio.Future) -> None:
    """Schedule websocket sends without blocking the request cycle."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(coro)
        return

    def _runner() -> None:
        try:
            asyncio.run(coro)
        except Exception:
            logger.exception("Failed to push websocket dashboard stats")

    threading.Thread(target=_runner, daemon=True).start()


async def _send_dashboard_stats(org_id: UUID, stats: dict) -> None:
    """Send dashboard stats updates to websocket clients."""
    await manager.send_to_org(
        org_id,
        {
            "type": "stats_update",
            "data": stats,
        },
    )
