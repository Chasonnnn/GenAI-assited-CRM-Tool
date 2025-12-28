"""Dashboard service - data for dashboard widgets."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.enums import OwnerType
from app.db.models import Case, Task, ZoomMeeting


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

    case_ids = {t.case_id for t in tasks if t.case_id}
    cases = (
        {}
        if not case_ids
        else {
            c.id: c
            for c in db.query(Case)
            .filter(Case.organization_id == org_id, Case.id.in_(case_ids))
            .all()
        }
    )

    task_items = []
    for task in tasks:
        case = cases.get(task.case_id) if task.case_id else None
        is_overdue = task.due_date < today if task.due_date else False
        task_items.append(
            {
                "id": str(task.id),
                "type": "task",
                "title": task.title,
                "time": task.due_time.strftime("%H:%M") if task.due_time else None,
                "case_id": str(task.case_id) if task.case_id else None,
                "case_number": case.case_number if case else None,
                "date": task.due_date.isoformat()
                if task.due_date
                else today.isoformat(),
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

    meeting_case_ids = {m.case_id for m in meetings if m.case_id}
    meeting_cases = (
        {}
        if not meeting_case_ids
        else {
            c.id: c
            for c in db.query(Case)
            .filter(Case.organization_id == org_id, Case.id.in_(meeting_case_ids))
            .all()
        }
    )

    meeting_items = []
    for meeting in meetings:
        case = meeting_cases.get(meeting.case_id) if meeting.case_id else None
        meeting_date = meeting.start_time.date() if meeting.start_time else today
        meeting_items.append(
            {
                "id": str(meeting.id),
                "type": "meeting",
                "title": meeting.topic,
                "time": meeting.start_time.strftime("%H:%M")
                if meeting.start_time
                else None,
                "case_id": str(meeting.case_id) if meeting.case_id else None,
                "case_number": case.case_number if case else None,
                "date": meeting_date.isoformat(),
                "is_overdue": False,
                "join_url": meeting.join_url,
            }
        )

    return task_items, meeting_items
