"""Dashboard router - API endpoints for dashboard widgets."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.db.enums import OwnerType, Role
from app.db.models import Case, Task, ZoomMeeting
from app.schemas.auth import UserSession

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# =============================================================================
# Schemas
# =============================================================================

class UpcomingTask(BaseModel):
    """Task item for upcoming widget."""
    id: str
    type: str = "task"
    title: str
    time: str | None  # HH:MM format or None for all-day
    case_id: str | None
    case_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool
    task_type: str


class UpcomingMeeting(BaseModel):
    """Meeting item for upcoming widget."""
    id: str
    type: str = "meeting"
    title: str
    time: str | None  # HH:MM format
    case_id: str | None
    case_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool = False
    join_url: str


class UpcomingResponse(BaseModel):
    """Response for upcoming widget."""
    tasks: list[UpcomingTask]
    meetings: list[UpcomingMeeting]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/upcoming", response_model=UpcomingResponse)
def get_upcoming(
    days: int = Query(7, ge=1, le=14, description="Number of days to look ahead"),
    include_overdue: bool = Query(True, description="Include overdue tasks"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> UpcomingResponse:
    """
    Get user's upcoming tasks and meetings for dashboard.
    
    Returns tasks where user is assignee/owner and meetings user created.
    Scoped to cases the user has access to.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    end_date = today + timedelta(days=days)
    
    # -------------------------------------------------------------------------
    # Fetch Tasks
    # -------------------------------------------------------------------------
    # Filter: user's tasks (assignee or owner)
    task_filters = [
        Task.organization_id == session.org_id,
        Task.completed_at.is_(None),  # Not completed
        or_(
            # User is owner
            and_(Task.owner_type == OwnerType.USER.value, Task.owner_id == session.user_id),
            # User is assignee
            Task.assignee_id == session.user_id,
        ),
    ]
    
    # Date filters
    if include_overdue:
        # Include overdue (due_date < today) OR due soon
        task_filters.append(
            or_(
                Task.due_date < today,  # Overdue
                and_(Task.due_date >= today, Task.due_date <= end_date),  # Upcoming
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
    
    # Build case lookup for numbers
    case_ids = {t.case_id for t in tasks if t.case_id}
    cases = {} if not case_ids else {
        c.id: c for c in db.query(Case).filter(Case.id.in_(case_ids)).all()
    }
    
    task_items = []
    for task in tasks:
        case = cases.get(task.case_id) if task.case_id else None
        is_overdue = task.due_date < today if task.due_date else False
        
        task_items.append(UpcomingTask(
            id=str(task.id),
            title=task.title,
            time=task.due_time.strftime("%H:%M") if task.due_time else None,
            case_id=str(task.case_id) if task.case_id else None,
            case_number=case.case_number if case else None,
            date=task.due_date.isoformat() if task.due_date else today.isoformat(),
            is_overdue=is_overdue,
            task_type=task.task_type or "general",
        ))
    
    # -------------------------------------------------------------------------
    # Fetch Zoom Meetings
    # -------------------------------------------------------------------------
    meeting_filters = [
        ZoomMeeting.user_id == session.user_id,
        ZoomMeeting.start_time.isnot(None),  # Only scheduled meetings
    ]
    
    # Future meetings only (or recent past)
    meeting_filters.append(
        or_(
            ZoomMeeting.start_time >= now - timedelta(hours=1),  # Started recently
            ZoomMeeting.start_time <= now + timedelta(days=days),  # Within range
        )
    )
    
    meetings = (
        db.query(ZoomMeeting)
        .filter(and_(*meeting_filters))
        .order_by(ZoomMeeting.start_time)
        .limit(20)
        .all()
    )
    
    # Build case lookup for meeting cases
    meeting_case_ids = {m.case_id for m in meetings if m.case_id}
    meeting_cases = {} if not meeting_case_ids else {
        c.id: c for c in db.query(Case).filter(Case.id.in_(meeting_case_ids)).all()
    }
    
    meeting_items = []
    for meeting in meetings:
        case = meeting_cases.get(meeting.case_id) if meeting.case_id else None
        meeting_date = meeting.start_time.date() if meeting.start_time else today
        
        meeting_items.append(UpcomingMeeting(
            id=str(meeting.id),
            title=meeting.topic,
            time=meeting.start_time.strftime("%H:%M") if meeting.start_time else None,
            case_id=str(meeting.case_id) if meeting.case_id else None,
            case_number=case.case_number if case else None,
            date=meeting_date.isoformat(),
            join_url=meeting.join_url,
        ))
    
    return UpcomingResponse(tasks=task_items, meetings=meeting_items)
