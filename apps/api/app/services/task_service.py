"""Task service - business logic for task management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.enums import TaskType, OwnerType
from app.db.models import Task, User, Queue, Case
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead, TaskListItem
from app.services import membership_service, queue_service


def create_task(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: TaskCreate,
) -> Task:
    """Create a new task."""
    # Determine owner - default to creator if not provided
    owner_type = data.owner_type or "user"
    if owner_type == "queue":
        owner_id = data.owner_id
        if not owner_id:
            raise ValueError("owner_id is required when owner_type is 'queue'")
    else:
        owner_id = data.owner_id or user_id
    
    task = Task(
        organization_id=org_id,
        created_by_user_id=user_id,
        case_id=data.case_id,
        intended_parent_id=data.intended_parent_id,
        owner_type=owner_type,
        owner_id=owner_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type.value,
        due_date=data.due_date,
        due_time=data.due_time,
        duration_minutes=data.duration_minutes,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Notify assignee (if assigned to user different from creator)
    if owner_type == "user" and owner_id != user_id:
        from app.services import notification_service
        from app.db.models import User, Case
        actor = db.query(User).filter(User.id == user_id).first()
        actor_name = actor.display_name if actor else "Someone"
        case_number = None
        if data.case_id:
            case = db.query(Case).filter(Case.id == data.case_id).first()
            case_number = case.case_number if case else None
        notification_service.notify_task_assigned(
            db=db,
            task_id=task.id,
            task_title=task.title,
            org_id=org_id,
            assignee_id=owner_id,
            actor_name=actor_name,
            case_number=case_number,
        )
    
    return task


def update_task(
    db: Session,
    task: Task,
    data: TaskUpdate,
    actor_user_id: UUID | None = None,
) -> Task:
    """
    Update task fields.
    
    Uses exclude_unset=True so only explicitly provided fields are updated.
    None values ARE applied to clear optional fields.
    
    If actor_user_id is provided, sends notification on assignee change.
    """
    update_data = data.model_dump(exclude_unset=True)
    
    # Track owner for notification
    old_owner_type = task.owner_type
    old_owner_id = task.owner_id

    if "owner_type" in update_data or "owner_id" in update_data:
        owner_type = update_data.get("owner_type", task.owner_type)
        owner_id = update_data.get("owner_id", task.owner_id)
        if not owner_type or not owner_id:
            raise ValueError("owner_type and owner_id must both be provided")
        update_data["owner_type"] = owner_type
        update_data["owner_id"] = owner_id
    
    # Fields that can be cleared (set to None)
    clearable_fields = {"due_date", "due_time", "description", "duration_minutes"}
    
    for field, value in update_data.items():
        # For clearable fields, allow None; for others, skip None
        if value is None and field not in clearable_fields:
            continue
        if field == "task_type" and value is not None:
            value = value.value
        setattr(task, field, value)
    
    db.commit()
    db.refresh(task)
    
    # Notify new assignee if reassigned (and not self-assign)
    if (
        actor_user_id
        and (update_data.get("owner_type") or update_data.get("owner_id"))
        and update_data.get("owner_type") == "user"
        and update_data.get("owner_id") != old_owner_id
        and update_data.get("owner_id") != actor_user_id
    ):
        from app.services import notification_service
        from app.db.models import User, Case
        
        actor = db.query(User).filter(User.id == actor_user_id).first()
        actor_name = actor.display_name if actor else "Someone"
        case_number = None
        if task.case_id:
            case = db.query(Case).filter(Case.id == task.case_id).first()
            case_number = case.case_number if case else None
        
        notification_service.notify_task_assigned(
            db=db,
            task_id=task.id,
            task_title=task.title,
            org_id=task.organization_id,
            assignee_id=update_data.get("owner_id"),
            actor_name=actor_name,
            case_number=case_number,
        )
    
    return task


def complete_task(
    db: Session,
    task: Task,
    user_id: UUID,
    commit: bool = True,
) -> Task:
    """
    Mark task as completed.
    
    Args:
        commit: If False, uses flush instead of commit (for batch operations).
                Caller is responsible for committing the transaction.
    """
    if task.is_completed:
        return task
    
    task.is_completed = True
    task.completed_at = datetime.now(timezone.utc)
    task.completed_by_user_id = user_id
    
    if commit:
        db.commit()
        db.refresh(task)
    else:
        db.flush()
    
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


def validate_task_owner(
    db: Session,
    org_id: UUID,
    owner_type: str | None,
    owner_id: UUID | None,
    *,
    allow_none: bool = False,
) -> None:
    """Validate that an owner exists within the organization."""
    if owner_type is None:
        if allow_none:
            return
        raise ValueError("Invalid owner_type")

    if owner_type == OwnerType.USER.value:
        if owner_id is None:
            raise ValueError("Owner user not found in organization")
        membership = membership_service.get_membership_for_org(db, org_id, owner_id)
        if not membership:
            raise ValueError("Owner user not found in organization")
        return

    if owner_type == OwnerType.QUEUE.value:
        if owner_id is None:
            raise ValueError("Queue not found or inactive")
        queue = queue_service.get_queue(db, org_id, owner_id)
        if not queue or not queue.is_active:
            raise ValueError("Queue not found or inactive")
        return

    raise ValueError("Invalid owner_type")


def get_task_context(
    db: Session,
    tasks: list[Task],
) -> dict[str, dict[UUID, str | None]]:
    """Fetch related data for tasks in bulk."""
    if not tasks:
        return {"user_names": {}, "queue_names": {}, "case_numbers": {}}

    user_ids = set()
    queue_ids = set()
    case_ids = set()

    for task in tasks:
        if task.owner_type == OwnerType.USER.value:
            user_ids.add(task.owner_id)
        elif task.owner_type == OwnerType.QUEUE.value:
            queue_ids.add(task.owner_id)
        if task.created_by_user_id:
            user_ids.add(task.created_by_user_id)
        if task.completed_by_user_id:
            user_ids.add(task.completed_by_user_id)
        if task.case_id:
            case_ids.add(task.case_id)

    user_names = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_names = {user.id: user.display_name for user in users}

    queue_names = {}
    if queue_ids:
        queues = db.query(Queue).filter(Queue.id.in_(queue_ids)).all()
        queue_names = {queue.id: queue.name for queue in queues}

    case_numbers = {}
    if case_ids:
        cases = db.query(Case).filter(Case.id.in_(case_ids)).all()
        case_numbers = {case.id: case.case_number for case in cases}

    return {
        "user_names": user_names,
        "queue_names": queue_names,
        "case_numbers": case_numbers,
    }


def to_task_read(task: Task, context: dict[str, dict[UUID, str | None]]) -> TaskRead:
    """Convert Task model to TaskRead schema."""
    owner_name = None
    if task.owner_type == OwnerType.USER.value:
        owner_name = context["user_names"].get(task.owner_id)
    elif task.owner_type == OwnerType.QUEUE.value:
        owner_name = context["queue_names"].get(task.owner_id)

    created_by_name = context["user_names"].get(task.created_by_user_id)
    completed_by_name = context["user_names"].get(task.completed_by_user_id)
    case_number = context["case_numbers"].get(task.case_id)

    return TaskRead(
        id=task.id,
        case_id=task.case_id,
        case_number=case_number,
        owner_type=task.owner_type,
        owner_id=task.owner_id,
        owner_name=owner_name,
        created_by_user_id=task.created_by_user_id,
        created_by_name=created_by_name,
        title=task.title,
        description=task.description,
        task_type=TaskType(task.task_type),
        due_date=task.due_date,
        due_time=task.due_time,
        duration_minutes=task.duration_minutes,
        is_completed=task.is_completed,
        completed_at=task.completed_at,
        completed_by_name=completed_by_name,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def to_task_list_item(
    task: Task,
    context: dict[str, dict[UUID, str | None]],
) -> TaskListItem:
    """Convert Task model to TaskListItem schema."""
    owner_name = None
    if task.owner_type == OwnerType.USER.value:
        owner_name = context["user_names"].get(task.owner_id)
    elif task.owner_type == OwnerType.QUEUE.value:
        owner_name = context["queue_names"].get(task.owner_id)

    case_number = context["case_numbers"].get(task.case_id)

    return TaskListItem(
        id=task.id,
        case_id=task.case_id,
        case_number=case_number,
        title=task.title,
        task_type=TaskType(task.task_type),
        owner_type=task.owner_type,
        owner_id=task.owner_id,
        owner_name=owner_name,
        due_date=task.due_date,
        due_time=task.due_time,
        duration_minutes=task.duration_minutes,
        is_completed=task.is_completed,
        created_at=task.created_at,
    )


def list_tasks(
    db: Session,
    org_id: UUID,
    user_role: str | None = None,
    user_id: UUID | None = None,
    page: int = 1,
    per_page: int = 20,
    q: str | None = None,
    owner_id: UUID | None = None,
    case_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    is_completed: bool | None = None,
    task_type: TaskType | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    my_tasks_user_id: UUID | None = None,
):
    """
    List tasks with filters and pagination.
    
    Args:
        user_role: User's role - used to filter out tasks linked to inaccessible cases
        user_id: User's ID - for owner-based case access filtering
        q: Search query - matches title or description (case-insensitive)
        due_before: Filter tasks with due_date <= this date (YYYY-MM-DD)
        due_after: Filter tasks with due_date >= this date (YYYY-MM-DD)
        my_tasks_user_id: If set, returns tasks where user is creator OR owner (user)
    
    Returns:
        (tasks, total_count)
    """
    from datetime import date
    from app.db.enums import Role, OwnerType
    from app.db.models import Case
    
    query = db.query(Task).filter(Task.organization_id == org_id)
    
    # Role-based case access filtering for intake specialists
    # Filter out tasks linked to cases they can't access
    if user_role == Role.INTAKE_SPECIALIST.value or user_role == Role.INTAKE_SPECIALIST:
        # Subquery: cases intake can access (owner-based)
        if user_id:
            accessible_case_ids = db.query(Case.id).filter(
                Case.organization_id == org_id,
                (Case.owner_type == OwnerType.USER.value) & (Case.owner_id == user_id),
            ).subquery()
            
            query = query.filter(
                or_(
                    Task.case_id.is_(None),  # Tasks without case always visible
                    Task.case_id.in_(accessible_case_ids)
                )
            )
        else:
            # No user_id → tasks without a case only
            query = query.filter(Task.case_id.is_(None))
    
    # Search filter (title or description)
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern),
            )
        )
    
    # My tasks (creator or owner)
    if my_tasks_user_id:
        query = query.filter(
            or_(
                Task.created_by_user_id == my_tasks_user_id,
                (Task.owner_type == OwnerType.USER.value) & (Task.owner_id == my_tasks_user_id),
            )
        )
    
    # Owner filter (user-owned only)
    if owner_id:
        query = query.filter(
            Task.owner_type == OwnerType.USER.value,
            Task.owner_id == owner_id,
        )
    
    # Case filter
    if case_id:
        query = query.filter(Task.case_id == case_id)
    
    # Intended Parent filter
    if intended_parent_id:
        query = query.filter(Task.intended_parent_id == intended_parent_id)
    
    # Completion filter
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    
    # Type filter
    if task_type:
        query = query.filter(Task.task_type == task_type.value)
    
    # Due date filters
    if due_before:
        try:
            before_date = date.fromisoformat(due_before)
            query = query.filter(Task.due_date <= before_date)
        except ValueError:
            pass  # Invalid date format, skip filter
    
    if due_after:
        try:
            after_date = date.fromisoformat(due_after)
            query = query.filter(Task.due_date >= after_date)
        except ValueError:
            pass  # Invalid date format, skip filter
    
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


def count_pending_tasks(db: Session, org_id: UUID) -> int:
    """Count incomplete tasks for dashboard metrics."""
    return db.query(Task).filter(
        Task.organization_id == org_id,
        Task.is_completed.is_(False),
    ).count()


def count_overdue_tasks(db: Session, org_id: UUID, today) -> int:
    """Count overdue tasks for dashboard metrics."""
    return db.query(Task).filter(
        Task.organization_id == org_id,
        Task.is_completed.is_(False),
        Task.due_date < today,
    ).count()


def list_open_tasks_for_case(
    db: Session,
    case_id: UUID,
    limit: int = 10,
    org_id: UUID | None = None,
) -> list[Task]:
    """List open tasks for a case."""
    query = db.query(Task).filter(
        Task.case_id == case_id,
        Task.is_completed.is_(False),
    )
    if org_id:
        query = query.filter(Task.organization_id == org_id)
    return query.order_by(Task.due_date.asc()).limit(limit).all()


def list_user_tasks_due_on(
    db: Session,
    org_id: UUID,
    due_date,
) -> list[Task]:
    """List user-owned tasks due on a specific date."""
    return db.query(Task).filter(
        Task.organization_id == org_id,
        Task.due_date == due_date,
        Task.is_completed.is_(False),
        Task.owner_type == OwnerType.USER.value,
    ).all()


def list_user_tasks_overdue(
    db: Session,
    org_id: UUID,
    today,
) -> list[Task]:
    """List user-owned tasks overdue before a date."""
    return db.query(Task).filter(
        Task.organization_id == org_id,
        Task.due_date < today,
        Task.is_completed.is_(False),
        Task.owner_type == OwnerType.USER.value,
    ).all()
