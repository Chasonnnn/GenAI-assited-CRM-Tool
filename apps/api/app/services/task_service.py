"""Task service - business logic for task management."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.enums import TaskType, TaskStatus, OwnerType
from app.db.models import (
    Surrogate,
    Membership,
    Queue,
    Task,
    User,
    WorkflowExecution,
    WorkflowResumeJob,
)
from app.schemas.auth import UserSession
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead, TaskListItem, BulkCompleteResponse
from app.services import membership_service, queue_service
from app.utils.normalization import escape_like_string


logger = logging.getLogger(__name__)


def _sync_task_to_google_best_effort(db: Session, task: Task) -> None:
    """Best-effort outbound Google Tasks sync."""
    try:
        from app.services import google_tasks_sync_service

        google_tasks_sync_service.sync_platform_task_to_google(db, task)
    except Exception as exc:
        logger.warning("Task Google sync failed task=%s error=%s", task.id, exc)


def _delete_task_from_google_best_effort(db: Session, task: Task) -> None:
    """Best-effort deletion from Google Tasks."""
    try:
        from app.services import google_tasks_sync_service

        google_tasks_sync_service.delete_platform_task_from_google(db, task)
    except Exception as exc:
        logger.warning("Task Google delete sync failed task=%s error=%s", task.id, exc)


def _pull_google_tasks_for_user_best_effort(db: Session, user_id: UUID, org_id: UUID) -> None:
    """Best-effort inbound Google Tasks pull for a user."""
    try:
        from app.services import google_tasks_sync_service

        google_tasks_sync_service.sync_google_tasks_for_user(db, user_id=user_id, org_id=org_id)
    except Exception as exc:
        logger.warning("Task Google pull failed user=%s org=%s error=%s", user_id, org_id, exc)


def create_task(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: TaskCreate,
    *,
    emit_events: bool = False,
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
        surrogate_id=data.surrogate_id,
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

    _sync_task_to_google_best_effort(db, task)

    # Notify assignee (if assigned to user different from creator)
    if owner_type == "user" and owner_id != user_id:
        from app.services import task_events

        task_events.notify_task_assigned(
            db=db,
            task=task,
            actor_user_id=user_id,
            assignee_id=owner_id,
        )

    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, org_id)

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

    _sync_task_to_google_best_effort(db, task)

    # Notify new assignee if reassigned (and not self-assign)
    if (
        actor_user_id
        and (update_data.get("owner_type") or update_data.get("owner_id"))
        and update_data.get("owner_type") == "user"
        and update_data.get("owner_id") != old_owner_id
        and update_data.get("owner_id") != actor_user_id
    ):
        from app.services import task_events

        task_events.notify_task_assigned(
            db=db,
            task=task,
            actor_user_id=actor_user_id,
            assignee_id=update_data.get("owner_id"),
        )

    return task


def complete_task(
    db: Session,
    task: Task,
    user_id: UUID,
    commit: bool = True,
    *,
    emit_events: bool = False,
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
        _sync_task_to_google_best_effort(db, task)
    else:
        db.flush()

    if commit and emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, task.organization_id)

    return task


def uncomplete_task(
    db: Session,
    task: Task,
    *,
    emit_events: bool = False,
) -> Task:
    """Mark task as not completed."""
    task.is_completed = False
    task.completed_at = None
    task.completed_by_user_id = None
    db.commit()
    db.refresh(task)
    _sync_task_to_google_best_effort(db, task)
    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, task.organization_id)
    return task


def bulk_complete_tasks(
    db: Session,
    session: UserSession,
    task_ids: list[UUID],
) -> BulkCompleteResponse:
    """
    Mark multiple tasks as completed with access and permission checks.

    Returns counts + failures for per-task errors.
    """
    from fastapi import HTTPException

    from app.core.deps import is_owner_or_assignee_or_admin
    from app.core.surrogate_access import check_surrogate_access
    from app.services import surrogate_service, dashboard_events

    results: dict = {"completed": 0, "failed": []}
    completed_tasks_to_sync: list[Task] = []

    for task_id in task_ids:
        try:
            task = get_task(db, task_id, session.org_id)
            if not task:
                results["failed"].append({"task_id": str(task_id), "reason": "Task not found"})
                continue

            if task.surrogate_id:
                surrogate = surrogate_service.get_surrogate(db, session.org_id, task.surrogate_id)
                if surrogate:
                    check_surrogate_access(
                        surrogate,
                        session.role,
                        session.user_id,
                        db=db,
                        org_id=session.org_id,
                    )

            if not is_owner_or_assignee_or_admin(
                session, task.created_by_user_id, task.owner_type, task.owner_id
            ):
                results["failed"].append({"task_id": str(task_id), "reason": "Not authorized"})
                continue

            if task.task_type == TaskType.WORKFLOW_APPROVAL.value:
                results["failed"].append(
                    {
                        "task_id": str(task_id),
                        "reason": "Workflow approvals must be resolved via /tasks/{id}/resolve",
                    }
                )
                continue

            if task.is_completed:
                results["completed"] += 1
                continue

            complete_task(db, task, session.user_id, commit=False)
            completed_tasks_to_sync.append(task)
            results["completed"] += 1

        except HTTPException as exc:
            results["failed"].append({"task_id": str(task_id), "reason": exc.detail})
        except Exception as exc:
            logger.error("Bulk complete failed for task %s: %s", task_id, exc)
            results["failed"].append(
                {"task_id": str(task_id), "reason": "An unexpected error occurred"}
            )

    db.commit()
    for completed_task in completed_tasks_to_sync:
        _sync_task_to_google_best_effort(db, completed_task)
    dashboard_events.push_dashboard_stats(db, session.org_id)

    return BulkCompleteResponse(completed=results["completed"], failed=results["failed"])


def get_task(db: Session, task_id: UUID, org_id: UUID) -> Task | None:
    """Get task by ID (org-scoped)."""
    return (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == org_id,
        )
        .first()
    )


def delete_task(
    db: Session,
    task: Task,
    *,
    emit_events: bool = False,
) -> None:
    """Delete a task."""
    _delete_task_from_google_best_effort(db, task)
    db.delete(task)
    db.commit()
    if emit_events:
        from app.services import dashboard_events

        dashboard_events.push_dashboard_stats(db, task.organization_id)


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
    org_id: UUID,
    tasks: list[Task],
) -> dict[str, dict[UUID, str | None]]:
    """Fetch related data for tasks in bulk."""
    if not tasks:
        return {"user_names": {}, "queue_names": {}, "surrogate_numbers": {}}

    user_ids = set()
    queue_ids = set()
    surrogate_ids = set()

    for task in tasks:
        if task.owner_type == OwnerType.USER.value:
            user_ids.add(task.owner_id)
        elif task.owner_type == OwnerType.QUEUE.value:
            queue_ids.add(task.owner_id)
        if task.created_by_user_id:
            user_ids.add(task.created_by_user_id)
        if task.completed_by_user_id:
            user_ids.add(task.completed_by_user_id)
        if task.workflow_triggered_by_user_id:
            user_ids.add(task.workflow_triggered_by_user_id)
        if task.surrogate_id:
            surrogate_ids.add(task.surrogate_id)

    user_names = {}
    if user_ids:
        # Include inactive memberships so historical tasks keep user names.
        users = (
            db.query(User)
            .join(Membership, Membership.user_id == User.id)
            .filter(Membership.organization_id == org_id, User.id.in_(user_ids))
            .all()
        )
        user_names = {user.id: user.display_name for user in users}

    queue_names = {}
    if queue_ids:
        queues = (
            db.query(Queue)
            .filter(
                Queue.organization_id == org_id,
                Queue.id.in_(queue_ids),
            )
            .all()
        )
        queue_names = {queue.id: queue.name for queue in queues}

    surrogate_numbers = {}
    if surrogate_ids:
        surrogates = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == org_id,
                Surrogate.id.in_(surrogate_ids),
            )
            .all()
        )
        surrogate_numbers = {surrogate.id: surrogate.surrogate_number for surrogate in surrogates}

    return {
        "user_names": user_names,
        "queue_names": queue_names,
        "surrogate_numbers": surrogate_numbers,
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
    triggered_by_name = context["user_names"].get(task.workflow_triggered_by_user_id)
    surrogate_number = context["surrogate_numbers"].get(task.surrogate_id)

    return TaskRead(
        id=task.id,
        surrogate_id=task.surrogate_id,
        surrogate_number=surrogate_number,
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
        status=task.status,
        workflow_execution_id=task.workflow_execution_id,
        workflow_action_type=task.workflow_action_type,
        workflow_action_preview=task.workflow_action_preview,
        workflow_denial_reason=task.workflow_denial_reason,
        workflow_triggered_by_user_id=task.workflow_triggered_by_user_id,
        workflow_triggered_by_name=triggered_by_name,
        due_at=task.due_at,
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

    surrogate_number = context["surrogate_numbers"].get(task.surrogate_id)

    return TaskListItem(
        id=task.id,
        surrogate_id=task.surrogate_id,
        surrogate_number=surrogate_number,
        title=task.title,
        task_type=TaskType(task.task_type),
        owner_type=task.owner_type,
        owner_id=task.owner_id,
        owner_name=owner_name,
        due_date=task.due_date,
        due_time=task.due_time,
        duration_minutes=task.duration_minutes,
        is_completed=task.is_completed,
        status=task.status,
        workflow_action_type=task.workflow_action_type,
        due_at=task.due_at,
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
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    pipeline_id: UUID | None = None,
    is_completed: bool | None = None,
    task_type: TaskType | None = None,
    status: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    my_tasks_user_id: UUID | None = None,
    exclude_approvals: bool = False,
):
    """
    List tasks with filters and pagination.

    Args:
        user_role: User's role - used to filter out tasks linked to inaccessible surrogates
        user_id: User's ID - for owner-based surrogate access filtering
        q: Search query - matches title or description (case-insensitive)
        due_before: Filter tasks with due_date <= this date (YYYY-MM-DD)
        due_after: Filter tasks with due_date >= this date (YYYY-MM-DD)
        my_tasks_user_id: If set, returns tasks where user is creator OR owner (user)

    Returns:
        (tasks, total_count)
    """
    from datetime import date
    from app.db.enums import Role, OwnerType
    from app.db.models import Surrogate

    if user_id:
        _pull_google_tasks_for_user_best_effort(db, user_id, org_id)

    query = db.query(Task).filter(Task.organization_id == org_id)

    # Role-based surrogate access filtering for intake specialists
    # Filter out tasks linked to surrogates they can't access
    if user_role == Role.INTAKE_SPECIALIST.value or user_role == Role.INTAKE_SPECIALIST:
        # Subquery: surrogates intake can access (owner-based)
        if user_id:
            default_queue = queue_service.get_or_create_default_queue(db, org_id)
            accessible_surrogate_ids = (
                db.query(Surrogate.id)
                .filter(
                    Surrogate.organization_id == org_id,
                    or_(
                        (Surrogate.owner_type == OwnerType.USER.value)
                        & (Surrogate.owner_id == user_id),
                        (Surrogate.owner_type == OwnerType.QUEUE.value)
                        & (Surrogate.owner_id == default_queue.id),
                    ),
                )
                .subquery()
            )

            query = query.filter(
                or_(
                    Task.surrogate_id.is_(None),  # Tasks without surrogate always visible
                    Task.surrogate_id.in_(accessible_surrogate_ids),
                )
            )
        else:
            # No user_id → tasks without a surrogate only
            query = query.filter(Task.surrogate_id.is_(None))

    # Search filter (title or description)
    if q:
        search_pattern = f"%{escape_like_string(q)}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_pattern, escape="\\"),
                Task.description.ilike(search_pattern, escape="\\"),
            )
        )

    # Optionally exclude workflow approvals from standard task views
    if exclude_approvals:
        query = query.filter(Task.task_type != TaskType.WORKFLOW_APPROVAL.value)

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

    # Surrogate filter
    if surrogate_id:
        query = query.filter(Task.surrogate_id == surrogate_id)

    # Pipeline filter (only tasks tied to surrogates in pipeline)
    if pipeline_id:
        from app.db.models import PipelineStage

        query = (
            query.join(Surrogate, Task.surrogate_id == Surrogate.id)
            .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
            .filter(
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
                PipelineStage.pipeline_id == pipeline_id,
            )
        )

    # Intended Parent filter
    if intended_parent_id:
        query = query.filter(Task.intended_parent_id == intended_parent_id)

    # Completion filter
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)

    # Type filter
    if task_type:
        query = query.filter(Task.task_type == task_type.value)

    # Status filter (primarily for workflow approvals)
    status_values: list[str] = []
    if status:
        status_values = [s.strip() for s in status.split(",") if s.strip()]
        if status_values:
            query = query.filter(Task.status.in_(status_values))

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

    # Order approvals by due_at; standard tasks by completion/due date
    if task_type == TaskType.WORKFLOW_APPROVAL or status_values:
        query = query.order_by(
            Task.due_at.asc().nullslast(),
            Task.created_at.desc(),
        )
    else:
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
    return (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .count()
    )


def count_overdue_tasks(db: Session, org_id: UUID, today) -> int:
    """Count overdue tasks for dashboard metrics."""
    return (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
            Task.due_date < today,
        )
        .count()
    )


def list_open_tasks_for_surrogate(
    db: Session,
    surrogate_id: UUID,
    limit: int = 10,
    org_id: UUID | None = None,
) -> list[Task]:
    """List open tasks for a surrogate."""
    query = db.query(Task).filter(
        Task.surrogate_id == surrogate_id,
        Task.is_completed.is_(False),
        Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
    )
    if org_id:
        query = query.filter(Task.organization_id == org_id)
    return query.order_by(Task.due_date.asc()).limit(limit).all()


def iter_tasks_due_in_window(
    db: Session,
    org_id: UUID,
    window_start,
    window_end,
    batch_size: int = 1000,
):
    """Yield tasks due within a time window (org-scoped)."""
    from datetime import datetime as dt
    from app.db.models import Surrogate

    start_date = window_start.date()
    end_date = window_end.date()
    tzinfo = window_start.tzinfo

    query = (
        db.query(Task)
        .join(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Task.due_date.isnot(None),
            Task.due_date >= start_date,
            Task.due_date <= end_date,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .order_by(Task.due_date.asc(), Task.id.asc())
    )

    for task in query.yield_per(batch_size):
        if not task.due_date:
            continue
        due_dt = dt.combine(task.due_date, task.due_time or dt.min.time())
        if tzinfo:
            due_dt = due_dt.replace(tzinfo=tzinfo)
        if window_start <= due_dt <= window_end:
            yield task


def iter_overdue_tasks(
    db: Session,
    org_id: UUID,
    today,
    batch_size: int = 1000,
):
    """Yield overdue tasks (org-scoped)."""
    from app.db.models import Surrogate

    query = (
        db.query(Task)
        .join(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Task.due_date.isnot(None),
            Task.due_date < today,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .order_by(Task.due_date.asc(), Task.id.asc())
    )

    yield from query.yield_per(batch_size)


def list_user_tasks_due_on(
    db: Session,
    org_id: UUID,
    due_date,
) -> list[Task]:
    """List user-owned tasks due on a specific date."""
    return (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.due_date == due_date,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
            Task.owner_type == OwnerType.USER.value,
        )
        .all()
    )


def list_user_tasks_overdue(
    db: Session,
    org_id: UUID,
    today,
) -> list[Task]:
    """List user-owned tasks overdue before a date."""
    return (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.due_date < today,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
            Task.owner_type == OwnerType.USER.value,
        )
        .all()
    )


# =============================================================================
# Workflow Approval Functions
# =============================================================================


class WorkflowApprovalError(Exception):
    """Error during workflow approval resolution."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def resolve_workflow_approval(
    db: Session,
    task_id: UUID,
    org_id: UUID,
    decision: str,
    user_id: UUID,
    reason: str | None = None,
) -> Task:
    """
    Approve or deny a workflow approval task.

    SURROGATE OWNER ONLY - no permission override, no fallback.

    Args:
        db: Database session
        task_id: ID of the approval task
        org_id: Organization context for scoping
        decision: "approve" or "deny"
        user_id: ID of the user making the decision
        reason: Optional denial reason

    Returns:
        The updated task

    Raises:
        WorkflowApprovalError: If resolution fails
    """
    # Lock task row for update
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == org_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
        )
        .with_for_update()
        .first()
    )

    if not task:
        raise WorkflowApprovalError("Approval task not found", 404)

    # Check if already resolved
    if task.status not in [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]:
        raise WorkflowApprovalError(f"Task already resolved: {task.status}", 400)

    # Lock execution row to prevent double-resume
    execution = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.id == task.workflow_execution_id)
        .with_for_update()
        .first()
    )

    if not execution:
        raise WorkflowApprovalError("Workflow execution not found", 404)

    if execution.paused_task_id != task.id:
        raise WorkflowApprovalError("Execution not waiting on this task", 400)

    # SURROGATE OWNER ONLY - strictly enforced, no exceptions
    if user_id != task.owner_id:
        raise WorkflowApprovalError(
            "Only the surrogate owner can approve or deny this request",
            403,
        )

    # Update task based on decision
    now = datetime.now(timezone.utc)
    if decision == "approve":
        task.status = TaskStatus.COMPLETED.value
        task.is_completed = True
        task.completed_at = now
        task.completed_by_user_id = user_id
    else:  # deny
        task.status = TaskStatus.DENIED.value
        task.workflow_denial_reason = reason or "Denied by surrogate owner"

    task.updated_at = now
    db.flush()

    # Queue resume job with idempotency key
    idempotency_key = f"{execution.id}:{task.workflow_action_index}"
    _queue_workflow_resume_job(
        db,
        execution_id=execution.id,
        task_id=task.id,
        org_id=task.organization_id,
        idempotency_key=idempotency_key,
    )

    db.commit()

    # Log activity with latency metrics
    _log_approval_activity(db, task, decision, user_id, now)

    logger.info(f"Workflow approval {task.id} resolved: {decision} by user {user_id}")

    return task


def _queue_workflow_resume_job(
    db: Session,
    execution_id: UUID,
    task_id: UUID,
    org_id: UUID,
    idempotency_key: str,
) -> WorkflowResumeJob | None:
    """Queue a workflow resume job with idempotency."""
    from sqlalchemy.exc import IntegrityError
    from app.db.models import Job
    from app.db.enums import JobType, JobStatus

    resume_job = WorkflowResumeJob(
        idempotency_key=idempotency_key,
        execution_id=execution_id,
        task_id=task_id,
        status="pending",
    )

    try:
        with db.begin_nested():
            db.add(resume_job)
            db.flush()
    except IntegrityError:
        # Job already exists (idempotency)
        logger.info(f"Resume job already exists for key {idempotency_key}")
        return None

    job = Job(
        organization_id=org_id,
        job_type=JobType.WORKFLOW_RESUME.value,
        payload={
            "execution_id": str(execution_id),
            "task_id": str(task_id),
            "idempotency_key": idempotency_key,
        },
        run_at=datetime.now(timezone.utc),
        status=JobStatus.PENDING.value,
        idempotency_key=idempotency_key,
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        logger.info(f"Resume job already scheduled for key {idempotency_key}")

    logger.info(f"Queued resume job for execution {execution_id}")
    return resume_job


def _log_approval_activity(
    db: Session,
    task: Task,
    decision: str,
    user_id: UUID,
    resolved_at: datetime,
) -> None:
    """Log approval activity with latency metrics."""
    from app.services import activity_service
    from app.db.enums import SurrogateActivityType

    latency_hours = (resolved_at - task.created_at).total_seconds() / 3600

    activity_service.log_activity(
        db=db,
        surrogate_id=task.surrogate_id,
        organization_id=task.organization_id,
        activity_type=SurrogateActivityType.WORKFLOW_APPROVAL_RESOLVED,
        actor_user_id=user_id,
        details={
            "task_id": str(task.id),
            "workflow_execution_id": str(task.workflow_execution_id),
            "action_type": task.workflow_action_type,
            "decision": decision,
            "triggered_by_user_id": str(task.workflow_triggered_by_user_id)
            if task.workflow_triggered_by_user_id
            else None,
            "approval_latency_hours": round(latency_hours, 2),
        },
    )


def get_pending_approval_tasks(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
) -> list[Task]:
    """Get pending workflow approval tasks, optionally filtered by assignee."""
    query = db.query(Task).filter(
        Task.organization_id == org_id,
        Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
    )

    if user_id:
        query = query.filter(
            Task.owner_type == OwnerType.USER.value,
            Task.owner_id == user_id,
        )

    return query.order_by(Task.due_at.asc()).all()


def get_expired_approval_tasks(db: Session) -> list[Task]:
    """Get approval tasks that have passed their due_at deadline."""
    now = datetime.now(timezone.utc)

    return (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
            Task.due_at < now,
        )
        .with_for_update(skip_locked=True)
        .all()
    )


def expire_approval_task(
    db: Session,
    task: Task,
) -> None:
    """Mark an approval task as expired and queue resume job."""
    now = datetime.now(timezone.utc)

    if task.status not in [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]:
        logger.info("Skip expiring task %s with status %s", task.id, task.status)
        return

    # Mark as expired
    task.status = TaskStatus.EXPIRED.value
    task.workflow_denial_reason = "Approval timed out"
    task.updated_at = now

    # Queue resume job
    if task.workflow_execution_id and task.workflow_action_index is not None:
        idempotency_key = f"{task.workflow_execution_id}:{task.workflow_action_index}"
        _queue_workflow_resume_job(
            db,
            execution_id=task.workflow_execution_id,
            task_id=task.id,
            org_id=task.organization_id,
            idempotency_key=idempotency_key,
        )

    db.commit()

    # Notify owner that approval expired
    from app.services import notification_facade
    from app.db.enums import NotificationType

    notification_facade.create_notification(
        db=db,
        org_id=task.organization_id,
        user_id=task.owner_id,
        type=NotificationType.TASK_OVERDUE,
        title="Workflow Approval Expired",
        body=f"Approval task timed out: {task.title}",
        entity_type="task",
        entity_id=task.id,
    )

    logger.info(f"Expired approval task {task.id}")


def invalidate_pending_approvals_for_surrogate(
    db: Session,
    surrogate_id: UUID,
    reason: str,
    actor_user_id: UUID,
) -> int:
    """
    Invalidate all pending approval tasks for a surrogate.

    Called when surrogate owner changes while approvals are pending.
    Returns count of invalidated tasks.
    """
    from app.db.enums import WorkflowExecutionStatus

    pending_tasks = (
        db.query(Task)
        .filter(
            Task.surrogate_id == surrogate_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
        )
        .all()
    )

    count = 0
    for task in pending_tasks:
        # Mark task as denied
        task.status = TaskStatus.DENIED.value
        task.workflow_denial_reason = reason
        task.updated_at = datetime.now(timezone.utc)

        # Cancel workflow execution
        if task.workflow_execution_id:
            execution = (
                db.query(WorkflowExecution)
                .filter(WorkflowExecution.id == task.workflow_execution_id)
                .first()
            )

            if execution and execution.status == WorkflowExecutionStatus.PAUSED.value:
                execution.status = WorkflowExecutionStatus.CANCELED.value
                execution.error_message = reason
                execution.paused_at_action_index = None
                execution.paused_task_id = None

        count += 1

    if count > 0:
        db.commit()
        logger.info(
            f"Invalidated {count} pending approval(s) for surrogate {surrogate_id}: {reason}"
        )

    return count
