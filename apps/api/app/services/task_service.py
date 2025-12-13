"""Task service - business logic for task management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.enums import TaskType
from app.db.models import Task
from app.schemas.task import TaskCreate, TaskUpdate


def create_task(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: TaskCreate,
) -> Task:
    """Create a new task."""
    task = Task(
        organization_id=org_id,
        created_by_user_id=user_id,
        case_id=data.case_id,
        assigned_to_user_id=data.assigned_to_user_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type.value,
        due_date=data.due_date,
        due_time=data.due_time,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    task: Task,
    data: TaskUpdate,
) -> Task:
    """
    Update task fields.
    
    Uses exclude_unset=True so only explicitly provided fields are updated.
    None values ARE applied to clear optional fields.
    """
    update_data = data.model_dump(exclude_unset=True)
    
    # Fields that can be cleared (set to None)
    clearable_fields = {"assigned_to_user_id", "due_date", "due_time", "description"}
    
    for field, value in update_data.items():
        # For clearable fields, allow None; for others, skip None
        if value is None and field not in clearable_fields:
            continue
        if field == "task_type" and value is not None:
            value = value.value
        setattr(task, field, value)
    
    db.commit()
    db.refresh(task)
    return task


def complete_task(
    db: Session,
    task: Task,
    user_id: UUID,
) -> Task:
    """Mark task as completed."""
    if task.is_completed:
        return task
    
    task.is_completed = True
    task.completed_at = datetime.now(timezone.utc)
    task.completed_by_user_id = user_id
    db.commit()
    db.refresh(task)
    return task


def uncomplete_task(db: Session, task: Task) -> Task:
    """Mark task as not completed."""
    task.is_completed = False
    task.completed_at = None
    task.completed_by_user_id = None
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: UUID, org_id: UUID) -> Task | None:
    """Get task by ID (org-scoped)."""
    return db.query(Task).filter(
        Task.id == task_id,
        Task.organization_id == org_id,
    ).first()


def delete_task(db: Session, task: Task) -> None:
    """Delete a task."""
    db.delete(task)
    db.commit()


def list_tasks(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
    assigned_to: UUID | None = None,
    case_id: UUID | None = None,
    is_completed: bool | None = None,
    task_type: TaskType | None = None,
    my_tasks_user_id: UUID | None = None,
):
    """
    List tasks with filters and pagination.
    
    Args:
        my_tasks_user_id: If set, returns tasks where user is creator OR assignee
    
    Returns:
        (tasks, total_count)
    """
    query = db.query(Task).filter(Task.organization_id == org_id)
    
    # My tasks (creator or assignee)
    if my_tasks_user_id:
        query = query.filter(
            or_(
                Task.created_by_user_id == my_tasks_user_id,
                Task.assigned_to_user_id == my_tasks_user_id,
            )
        )
    
    # Assigned filter
    if assigned_to:
        query = query.filter(Task.assigned_to_user_id == assigned_to)
    
    # Case filter
    if case_id:
        query = query.filter(Task.case_id == case_id)
    
    # Completion filter
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    
    # Type filter
    if task_type:
        query = query.filter(Task.task_type == task_type.value)
    
    # Order: incomplete first by due date, then by created
    query = query.order_by(
        Task.is_completed.asc(),
        Task.due_date.asc().nullslast(),
        Task.created_at.desc(),
    )
    
    # Count
    total = query.count()
    
    # Paginate
    offset = (page - 1) * per_page
    tasks = query.offset(offset).limit(per_page).all()
    
    return tasks, total
