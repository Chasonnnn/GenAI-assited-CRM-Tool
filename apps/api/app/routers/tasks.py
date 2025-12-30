"""Tasks router - API endpoints for task management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_assignee_or_manager,
    is_owner_or_can_manage,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import TaskType
from app.schemas.auth import UserSession
from app.schemas.task import (
    BulkCompleteResponse,
    BulkTaskComplete,
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)
from app.services import task_service, ip_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter(
    dependencies=[Depends(require_permission(POLICIES["tasks"].default))]
)


def _check_task_case_access(task, session: "UserSession", db: Session) -> None:
    """Check case access for a task linked to a case."""
    from app.core.case_access import check_case_access
    from app.services import case_service

    if task.case_id:
        case = case_service.get_case(db, session.org_id, task.case_id)
        if case:
            check_case_access(
                case, session.role, session.user_id, db=db, org_id=session.org_id
            )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    q: str | None = Query(None, description="Search in title and description"),
    owner_id: UUID | None = None,
    case_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    is_completed: bool | None = None,
    task_type: TaskType | None = None,
    due_before: str | None = Query(None, description="Due date before (YYYY-MM-DD)"),
    due_after: str | None = Query(None, description="Due date after (YYYY-MM-DD)"),
    my_tasks: bool = False,
):
    """
    List tasks.

    - my_tasks=true: Filter to tasks created by or owned by current user
    - If case_id is specified, role-based access is checked
    """
    # If filtering by case_id, check access first
    if case_id:
        from app.core.case_access import check_case_access
        from app.services import case_service

        case = case_service.get_case(db, session.org_id, case_id)
        if case:
            check_case_access(
                case, session.role, session.user_id, db=db, org_id=session.org_id
            )

    # If filtering by intended_parent_id, verify existence
    if intended_parent_id:
        ip = ip_service.get_intended_parent(db, intended_parent_id, session.org_id)
        if not ip:
            raise HTTPException(status_code=404, detail="Intended parent not found")

    tasks, total = task_service.list_tasks(
        db=db,
        org_id=session.org_id,
        user_role=session.role,
        page=page,
        per_page=per_page,
        q=q,
        owner_id=owner_id,
        case_id=case_id,
        intended_parent_id=intended_parent_id,
        is_completed=is_completed,
        task_type=task_type,
        due_before=due_before,
        due_after=due_after,
        my_tasks_user_id=session.user_id if my_tasks else None,
    )

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    q_type = None
    if q:
        if "@" in q:
            q_type = "email"
        else:
            digit_count = sum(1 for ch in q if ch.isdigit())
            q_type = "phone" if digit_count >= 7 else "text"

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="task_list",
        target_id=None,
        request=request,
        details={
            "count": len(tasks),
            "page": page,
            "per_page": per_page,
            "owner_id": str(owner_id) if owner_id else None,
            "case_id": str(case_id) if case_id else None,
            "intended_parent_id": str(intended_parent_id)
            if intended_parent_id
            else None,
            "is_completed": is_completed,
            "task_type": task_type.value if task_type else None,
            "due_before": due_before,
            "due_after": due_after,
            "my_tasks": my_tasks,
            "q_type": q_type,
        },
    )
    db.commit()

    context = task_service.get_task_context(db, tasks)
    return TaskListResponse(
        items=[task_service.to_task_list_item(t, context) for t in tasks],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post(
    "",
    response_model=TaskRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_task(
    data: TaskCreate,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["create"])
    ),
    db: Session = Depends(get_db),
):
    """Create a new task (respects case access control)."""
    from app.core.case_access import check_case_access

    # Verify case belongs to org if specified
    if data.case_id:
        from app.services import case_service

        case = case_service.get_case(db, session.org_id, data.case_id)
        if not case:
            raise HTTPException(status_code=400, detail="Case not found")
        # Access control: checks ownership + post-approval permission
        check_case_access(
            case, session.role, session.user_id, db=db, org_id=session.org_id
        )

    # Verify owner belongs to org if specified
    try:
        task_service.validate_task_owner(
            db,
            session.org_id,
            data.owner_type,
            data.owner_id,
            allow_none=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task = task_service.create_task(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        data=data,
    )
    context = task_service.get_task_context(db, [task])
    return task_service.to_task_read(task, context)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get task by ID (respects role-based case access)."""
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Access control: check case access if task is linked to a case
    _check_task_case_access(task, session, db)

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="task",
        target_id=task.id,
        request=request,
        details={
            "view": "task_detail",
            "case_id": str(task.case_id) if task.case_id else None,
            "intended_parent_id": str(task.intended_parent_id)
            if task.intended_parent_id
            else None,
        },
    )
    db.commit()

    context = task_service.get_task_context(db, [task])
    return task_service.to_task_read(task, context)


@router.patch(
    "/{task_id}", response_model=TaskRead, dependencies=[Depends(require_csrf_header)]
)
def update_task(
    task_id: UUID,
    data: TaskUpdate,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["edit"])
    ),
    db: Session = Depends(get_db),
):
    """
    Update task.

    Requires: creator, owner, or manager+
    """
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Access control: check case access if task is linked to a case
    _check_task_case_access(task, session, db)

    # Permission: creator, owner, or manager+
    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.owner_type, task.owner_id
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to update this task"
        )

    update_fields = data.model_dump(exclude_unset=True)
    if "owner_type" in update_fields or "owner_id" in update_fields:
        owner_type = update_fields.get("owner_type", task.owner_type)
        owner_id = update_fields.get("owner_id", task.owner_id)
        try:
            task_service.validate_task_owner(db, session.org_id, owner_type, owner_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    task = task_service.update_task(db, task, data, actor_user_id=session.user_id)
    context = task_service.get_task_context(db, [task])
    return task_service.to_task_read(task, context)


@router.post(
    "/{task_id}/complete",
    response_model=TaskRead,
    dependencies=[Depends(require_csrf_header)],
)
def complete_task(
    task_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["edit"])
    ),
    db: Session = Depends(get_db),
):
    """
    Mark task as completed.

    Requires: creator, owner, or manager+
    """
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Access control: check case access if task is linked to a case
    _check_task_case_access(task, session, db)

    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.owner_type, task.owner_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")

    task = task_service.complete_task(db, task, session.user_id)
    context = task_service.get_task_context(db, [task])
    return task_service.to_task_read(task, context)


@router.post(
    "/{task_id}/uncomplete",
    response_model=TaskRead,
    dependencies=[Depends(require_csrf_header)],
)
def uncomplete_task(
    task_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["edit"])
    ),
    db: Session = Depends(get_db),
):
    """Mark task as not completed (respects role-based case access)."""
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Access control: check case access if task is linked to a case
    _check_task_case_access(task, session, db)

    if not is_owner_or_assignee_or_manager(
        session, task.created_by_user_id, task.owner_type, task.owner_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")

    task = task_service.uncomplete_task(db, task)
    context = task_service.get_task_context(db, [task])
    return task_service.to_task_read(task, context)


@router.post(
    "/bulk-complete",
    response_model=BulkCompleteResponse,
    dependencies=[Depends(require_csrf_header)],
)
def bulk_complete_tasks(
    data: BulkTaskComplete,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["edit"])
    ),
    db: Session = Depends(get_db),
):
    """
    Mark multiple tasks as completed.

    Processes each task individually, checking permissions for each.
    Returns count of successfully completed tasks and list of failures.

    Requires: creator, owner, or manager+ for each task
    """
    results = {"completed": 0, "failed": []}

    for task_id in data.task_ids:
        try:
            task = task_service.get_task(db, task_id, session.org_id)
            if not task:
                results["failed"].append(
                    {"task_id": str(task_id), "reason": "Task not found"}
                )
                continue

            # Access control: check case access if task is linked to a case
            try:
                _check_task_case_access(task, session, db)
            except HTTPException as e:
                results["failed"].append({"task_id": str(task_id), "reason": e.detail})
                continue

            # Permission: creator, owner, or manager+
            if not is_owner_or_assignee_or_manager(
                session, task.created_by_user_id, task.owner_type, task.owner_id
            ):
                results["failed"].append(
                    {"task_id": str(task_id), "reason": "Not authorized"}
                )
                continue

            # Already completed? Skip but count as success
            if task.is_completed:
                results["completed"] += 1
                continue

            task_service.complete_task(db, task, session.user_id, commit=False)
            results["completed"] += 1

        except Exception as e:
            # Log the actual error server-side, but don't leak details to client
            import logging

            logging.error(f"Bulk complete failed for task {task_id}: {e}")
            results["failed"].append(
                {"task_id": str(task_id), "reason": "An unexpected error occurred"}
            )

    # Commit all changes once at the end for efficiency
    db.commit()

    return BulkCompleteResponse(
        completed=results["completed"], failed=results["failed"]
    )


@router.delete(
    "/{task_id}", status_code=204, dependencies=[Depends(require_csrf_header)]
)
def delete_task(
    task_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["tasks"].actions["delete"])
    ),
    db: Session = Depends(get_db),
):
    """
    Delete task.

    Requires: creator or manager+ (assignee cannot delete)
    Access: Respects role-based case access
    """
    task = task_service.get_task(db, task_id, session.org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Access control: check case access if task is linked to a case
    _check_task_case_access(task, session, db)

    # Permission: creator or manager+ only (not assignee)
    if not is_owner_or_can_manage(session, task.created_by_user_id):
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this task"
        )

    task_service.delete_task(db, task)
    return None
