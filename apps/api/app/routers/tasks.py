"""Tasks router - API endpoints for task management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_assignee_or_manager,
    is_owner_or_can_manage,
    require_csrf_header,
)
from app.db.enums import TaskType, ROLES_CAN_ARCHIVE
from app.db.models import Case, User
from app.schemas.auth import UserSession
from app.schemas.task import (
    TaskCreate,
    TaskListItem,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)
from app.services import task_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter()


def _task_to_read(task, db: Session) -> TaskRead:
    """Convert Task model to TaskRead schema."""
    assigned_to_name = None
    if task.assigned_to_user_id:
        user = db.query(User).filter(User.id == task.assigned_to_user_id).first()
        assigned_to_name = user.display_name if user else None
    
    created_by_name = None
    if task.created_by_user_id:
        user = db.query(User).filter(User.id == task.created_by_user_id).first()
        created_by_name = user.display_name if user else None
    
    completed_by_name = None
    if task.completed_by_user_id:
        user = db.query(User).filter(User.id == task.completed_by_user_id).first()
        completed_by_name = user.display_name if user else None
    
    case_number = None
    if task.case_id:
        case = db.query(Case).filter(Case.id == task.case_id).first()
        case_number = case.case_number if case else None
    
    return TaskRead(
        id=task.id,
        case_id=task.case_id,
        case_number=case_number,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_to_name=assigned_to_name,
        created_by_user_id=task.created_by_user_id,
        created_by_name=created_by_name,
        title=task.title,
        description=task.description,
        task_type=TaskType(task.task_type),
        due_date=task.due_date,
        due_time=task.due_time,
        is_completed=task.is_completed,
        completed_at=task.completed_at,
        completed_by_name=completed_by_name,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _task_to_list_item(task, db: Session) -> TaskListItem:
    """Convert Task model to TaskListItem schema."""
    assigned_to_name = None
    if task.assigned_to_user_id:
        user = db.query(User).filter(User.id == task.assigned_to_user_id).first()
        assigned_to_name = user.display_name if user else None
    
    case_number = None
    if task.case_id:
        case = db.query(Case).filter(Case.id == task.case_id).first()
        case_number = case.case_number if case else None
    
    return TaskListItem(
        id=task.id,
        case_id=task.case_id,
        case_number=case_number,
        title=task.title,
        task_type=TaskType(task.task_type),
        due_date=task.due_date,
        is_completed=task.is_completed,
        assigned_to_name=assigned_to_name,
        created_at=task.created_at,
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    assigned_to: UUID | None = None,
    case_id: UUID | None = None,
    is_completed: bool | None = None,
    task_type: TaskType | None = None,
    my_tasks: bool = False,
):
    """
    List tasks.
    
    - my_tasks=true: Filter to tasks created by or assigned to current user
    """
    tasks, total = task_service.list_tasks(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
        assigned_to=assigned_to,
        case_id=case_id,
        is_completed=is_completed,
        task_type=task_type,
        my_tasks_user_id=session.user_id if my_tasks else None,
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return TaskListResponse(
        items=[_task_to_list_item(t, db) for t in tasks],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("", response_model=TaskRead, status_code=201, dependencies=[Depends(require_csrf_header)])
def create_task(
    data: TaskCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new task (respects case access control)."""
    from app.db.models import Membership
    from app.core.case_access import check_case_access
    
    # Verify case belongs to org if specified
    if data.case_id:
        from app.services import case_service
        case = case_service.get_case(db, session.org_id, data.case_id)
        if not case:
            raise HTTPException(status_code=400, detail="Case not found")
        # Access control: intake can't access handed-off cases
        check_case_access(case, session.role)
    
    # Verify assignee belongs to org if specified
    if data.assigned_to_user_id:
        membership = db.query(Membership).filter(
            Membership.user_id == data.assigned_to_user_id,
            Membership.organization_id == session.org_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=400, detail="Assigned user not found in organization")
    
    task = task_service.create_task(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        data=data,
    )
    return _task_to_read(task, db)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get task by ID."""
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_read(task, db)


@router.patch("/{task_id}", response_model=TaskRead, dependencies=[Depends(require_csrf_header)])
def update_task(
    task_id: UUID,
    data: TaskUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Update task.
    
    Requires: creator, assignee, or manager+
    """
    from app.db.models import Membership
    
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Permission: creator, assignee, or manager+
    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.assigned_to_user_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this task")
    
    # Verify new assignee belongs to org if changing assignment
    if "assigned_to_user_id" in data.model_dump(exclude_unset=True):
        new_assignee = data.assigned_to_user_id
        if new_assignee is not None:
            membership = db.query(Membership).filter(
                Membership.user_id == new_assignee,
                Membership.organization_id == session.org_id,
            ).first()
            if not membership:
                raise HTTPException(status_code=400, detail="Assigned user not found in organization")
    
    task = task_service.update_task(db, task, data)
    return _task_to_read(task, db)


@router.post("/{task_id}/complete", response_model=TaskRead, dependencies=[Depends(require_csrf_header)])
def complete_task(
    task_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Mark task as completed.
    
    Requires: creator, assignee, or manager+
    """
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.assigned_to_user_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    task = task_service.complete_task(db, task, session.user_id)
    return _task_to_read(task, db)


@router.post("/{task_id}/uncomplete", response_model=TaskRead, dependencies=[Depends(require_csrf_header)])
def uncomplete_task(
    task_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Mark task as not completed."""
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.assigned_to_user_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    task = task_service.uncomplete_task(db, task)
    return _task_to_read(task, db)


@router.delete("/{task_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_task(
    task_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Delete task.
    
    Requires: creator or manager+ (assignee cannot delete)
    """
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Permission: creator or manager+ only (not assignee)
    if not is_owner_or_can_manage(session, task.created_by_user_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")
    
    task_service.delete_task(db, task)
    return None
