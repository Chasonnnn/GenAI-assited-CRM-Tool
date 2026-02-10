"""Dashboard service - data for dashboard widgets."""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import asyncio
import logging
import threading

import anyio

from sqlalchemy import and_, or_, func, exists, select
from sqlalchemy.orm import Session

from app.core.websocket import send_ws_to_org
from app.db.enums import OwnerType, Role, TaskType
from app.db.models import Surrogate, SurrogateStatusHistory, Task, ZoomMeeting, PipelineStage

logger = logging.getLogger(__name__)


def _is_admin_role(role: Role | str | None) -> bool:
    return role in (Role.ADMIN, Role.ADMIN.value, Role.DEVELOPER, Role.DEVELOPER.value)


def _should_scope_attention_to_owner(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    user_role: Role | str | None,
) -> bool:
    if _is_admin_role(user_role):
        return False
    if user_role in (Role.INTAKE_SPECIALIST, Role.INTAKE_SPECIALIST.value):
        return True
    if not user_id:
        return False
    has_owned = (
        db.query(Surrogate.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == user_id,
        )
        .limit(1)
        .first()
    )
    return has_owned is not None


def get_upcoming_items(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    days: int,
    include_overdue: bool,
    pipeline_id: UUID | None = None,
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

    task_query = db.query(Task)
    if pipeline_id:
        task_query = task_query.join(Surrogate, Task.surrogate_id == Surrogate.id).join(
            PipelineStage, Surrogate.stage_id == PipelineStage.id
        )
        task_filters.extend(
            [
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
                PipelineStage.pipeline_id == pipeline_id,
            ]
        )

    tasks = (
        task_query.filter(and_(*task_filters))
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

    meeting_query = db.query(ZoomMeeting)
    if pipeline_id:
        meeting_query = meeting_query.join(
            Surrogate, ZoomMeeting.surrogate_id == Surrogate.id
        ).join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        meeting_filters.extend(
            [
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
                PipelineStage.pipeline_id == pipeline_id,
            ]
        )

    meetings = (
        meeting_query.filter(and_(*meeting_filters))
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
# Attention Items (Dashboard KPI)
# =============================================================================


def get_attention_items(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    user_role: Role | str | None = None,
    days_unreached: int = 7,
    days_stuck: int = 14,
    pipeline_id: UUID | None = None,
    assignee_id: UUID | None = None,
    limit: int = 5,
) -> dict:
    """
    Get items needing attention for dashboard.

    Returns:
        - unreached_leads: Surrogates in early intake stages with no contact in X days
        - overdue_tasks: User's tasks past due date
        - stuck_surrogates: Surrogates that haven't moved stages in X days
        - total_count: Sum of all attention items
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    owner_only = _should_scope_attention_to_owner(db, org_id, user_id, user_role)
    effective_owner_id = assignee_id or (user_id if owner_only else None)
    owner_filters = []
    if effective_owner_id:
        owner_filters = [
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == effective_owner_id,
        ]
    elif owner_only:
        owner_filters = [Surrogate.id.is_(None)]

    # -------------------------------------------------------------------------
    # 1. Unreached Leads
    # Surrogates in early intake stages (order <= 2) with no contact or updates in X days
    # -------------------------------------------------------------------------
    unreached_cutoff = now - timedelta(days=days_unreached)

    unreached_query = (
        db.query(Surrogate, PipelineStage.label.label("stage_label"))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            PipelineStage.order <= 2,  # Only first 2 intake stages
            Surrogate.created_at < unreached_cutoff,
            Surrogate.updated_at < unreached_cutoff,
            or_(
                Surrogate.last_contacted_at.is_(None),
                Surrogate.last_contacted_at < unreached_cutoff,
            ),
            *owner_filters,
        )
    )

    if pipeline_id:
        unreached_query = unreached_query.filter(PipelineStage.pipeline_id == pipeline_id)

    unreached_results = unreached_query.order_by(Surrogate.created_at.asc()).limit(limit).all()

    unreached_leads = []
    for surrogate, stage_label in unreached_results:
        days_since_contact = None
        if surrogate.last_contacted_at:
            days_since_contact = (now - surrogate.last_contacted_at).days
        else:
            days_since_contact = (now.date() - surrogate.created_at.date()).days

        unreached_leads.append(
            {
                "id": str(surrogate.id),
                "surrogate_number": surrogate.surrogate_number,
                "stage_label": stage_label,
                "days_since_contact": days_since_contact,
                "created_at": surrogate.created_at.isoformat(),
            }
        )

    # Total count for unreached (without limit)
    unreached_total = (
        db.query(func.count(Surrogate.id))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            PipelineStage.order <= 2,
            Surrogate.created_at < unreached_cutoff,
            Surrogate.updated_at < unreached_cutoff,
            or_(
                Surrogate.last_contacted_at.is_(None),
                Surrogate.last_contacted_at < unreached_cutoff,
            ),
            *owner_filters,
        )
    )
    if pipeline_id:
        unreached_total = unreached_total.filter(PipelineStage.pipeline_id == pipeline_id)
    unreached_count = unreached_total.scalar() or 0

    # -------------------------------------------------------------------------
    # 2. Overdue Tasks
    # User's incomplete tasks past due date
    # -------------------------------------------------------------------------
    task_filters = [
        Task.organization_id == org_id,
        Task.due_date < today,
        Task.is_completed.is_(False),
        Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
    ]
    if effective_owner_id:
        task_filters.extend(
            [
                Task.owner_type == OwnerType.USER.value,
                Task.owner_id == effective_owner_id,
            ]
        )
    elif owner_only:
        task_filters.append(Task.id.is_(None))

    overdue_tasks_query = db.query(Task)
    if pipeline_id:
        overdue_tasks_query = overdue_tasks_query.join(
            Surrogate, Task.surrogate_id == Surrogate.id
        ).join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        task_filters.extend(
            [
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
                PipelineStage.pipeline_id == pipeline_id,
            ]
        )

    overdue_tasks_query = (
        overdue_tasks_query.filter(and_(*task_filters))
        .order_by(Task.due_date.asc())
        .limit(limit)
        .all()
    )

    overdue_tasks = []
    for task in overdue_tasks_query:
        days_overdue = (today - task.due_date).days if task.due_date else 0
        overdue_tasks.append(
            {
                "id": str(task.id),
                "title": task.title,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "days_overdue": days_overdue,
                "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
            }
        )

    # Total count for overdue tasks (without limit)
    overdue_count_query = db.query(func.count(Task.id))
    if pipeline_id:
        overdue_count_query = overdue_count_query.join(
            Surrogate, Task.surrogate_id == Surrogate.id
        ).join(PipelineStage, Surrogate.stage_id == PipelineStage.id)

    overdue_count = overdue_count_query.filter(and_(*task_filters)).scalar() or 0

    # -------------------------------------------------------------------------
    # 3. Stuck Surrogates
    # Surrogates that haven't moved stages in X days (using status history)
    # -------------------------------------------------------------------------
    stuck_cutoff = now - timedelta(days=days_stuck)

    # Optimization: Instead of aggregating all history (slow), use NOT EXISTS
    # to efficiently filter surrogates with no recent status change.

    # Base filter for "stuckness":
    # 1. No status change since stuck_cutoff
    # 2. AND created before stuck_cutoff (to avoid new surrogates being marked stuck)
    has_recent_change = exists().where(
        SurrogateStatusHistory.surrogate_id == Surrogate.id,
        SurrogateStatusHistory.organization_id == org_id,
        SurrogateStatusHistory.changed_at >= stuck_cutoff,
        SurrogateStatusHistory.to_stage_id.isnot(None),
    )

    stuck_filter = and_(
        Surrogate.created_at < stuck_cutoff,
        ~has_recent_change,
        Surrogate.organization_id == org_id,
        Surrogate.is_archived.is_(False),
        *owner_filters,
    )

    # Correlated subquery to fetch the last change date ONLY for the result set.
    # This avoids calculating MAX(changed_at) for thousands of non-stuck surrogates.
    last_change_subq = (
        select(func.max(SurrogateStatusHistory.changed_at))
        .where(
            SurrogateStatusHistory.surrogate_id == Surrogate.id,
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.to_stage_id.isnot(None),
        )
        .correlate(Surrogate)
        .scalar_subquery()
    )
    last_change_col = func.coalesce(last_change_subq, Surrogate.created_at)

    stuck_query = (
        db.query(
            Surrogate,
            PipelineStage.label.label("stage_label"),
            last_change_col.label("last_change"),
        )
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(stuck_filter)
    )

    if pipeline_id:
        stuck_query = stuck_query.filter(PipelineStage.pipeline_id == pipeline_id)

    stuck_results = stuck_query.order_by(last_change_col.asc()).limit(limit).all()

    stuck_surrogates = []
    for surrogate, stage_label, last_change in stuck_results:
        days_in_stage = (now - last_change).days if last_change else 0
        stuck_surrogates.append(
            {
                "id": str(surrogate.id),
                "surrogate_number": surrogate.surrogate_number,
                "stage_label": stage_label,
                "days_in_stage": days_in_stage,
                "last_stage_change": last_change.isoformat() if last_change else None,
            }
        )

    # Total count for stuck (without limit) - much faster without the join/aggregation
    stuck_total_query = (
        db.query(func.count(Surrogate.id))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(stuck_filter)
    )
    if pipeline_id:
        stuck_total_query = stuck_total_query.filter(PipelineStage.pipeline_id == pipeline_id)
    stuck_count = stuck_total_query.scalar() or 0

    return {
        "unreached_leads": unreached_leads,
        "unreached_count": unreached_count,
        "overdue_tasks": overdue_tasks,
        "overdue_count": overdue_count,
        "stuck_surrogates": stuck_surrogates,
        "stuck_count": stuck_count,
        "total_count": unreached_count + overdue_count + stuck_count,
    }


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

    async def _runner() -> None:
        try:
            await coro
        except Exception:
            logger.exception("Failed to push websocket dashboard stats")

    async def _spawn() -> None:
        asyncio.create_task(_runner())

    try:
        anyio.from_thread.run(_spawn)
    except RuntimeError:
        threading.Thread(target=lambda: anyio.run(_runner), daemon=True).start()


async def _send_dashboard_stats(org_id: UUID, stats: dict) -> None:
    """Send dashboard stats updates to websocket clients."""
    await send_ws_to_org(
        org_id,
        {
            "type": "stats_update",
            "data": stats,
        },
    )
