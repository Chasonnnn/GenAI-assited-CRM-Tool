"""AI bulk task creation routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import SurrogateActivityType
from app.schemas.auth import UserSession

router = APIRouter()
logger = logging.getLogger(__name__)


class BulkTaskItem(BaseModel):
    """A single task to create."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_date: str | None = None  # ISO format
    due_time: str | None = None  # HH:MM format
    task_type: str = "other"
    dedupe_key: str | None = None


class BulkTaskCreateRequest(BaseModel):
    """Request to create multiple tasks."""

    request_id: uuid.UUID  # Idempotency key
    # At least one entity ID must be provided
    surrogate_id: uuid.UUID | None = None
    intended_parent_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    tasks: list[BulkTaskItem] = Field(..., min_length=1, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_id(cls, values):
        if isinstance(values, dict) and not values.get("surrogate_id") and values.get("case_id"):
            values["surrogate_id"] = values["case_id"]
        return values

    @model_validator(mode="after")
    def _validate_entity_ids(self):
        if not any([self.surrogate_id, self.intended_parent_id, self.match_id]):
            raise ValueError(
                "At least one of surrogate_id, intended_parent_id, or match_id must be provided"
            )
        return self


class BulkTaskCreateResponse(BaseModel):
    """Response from bulk task creation."""

    success: bool
    created: list[dict]
    error: str | None = None


@router.post(
    "/create-bulk-tasks",
    response_model=BulkTaskCreateResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def create_bulk_tasks(
    body: BulkTaskCreateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.TASKS_CREATE)),
) -> BulkTaskCreateResponse:
    """
    Create multiple tasks in a single transaction (all-or-nothing).

    Uses request_id for idempotency - same request_id returns cached result.
    Tasks can be linked to case, surrogate, intended parent, or match.
    """
    from datetime import date, time

    from app.db.enums import TaskType
    from app.db.models import AIBulkTaskRequest, Task
    from app.services import activity_service, ip_service, match_service, surrogate_service

    existing_request = (
        db.query(AIBulkTaskRequest)
        .filter(
            AIBulkTaskRequest.organization_id == session.org_id,
            AIBulkTaskRequest.user_id == session.user_id,
            AIBulkTaskRequest.request_id == body.request_id,
        )
        .first()
    )
    if existing_request:
        logger.info("Returning cached result for request_id=%s", body.request_id)
        return BulkTaskCreateResponse(**existing_request.response_payload)

    # Verify entity exists and belongs to org
    entity_type = None
    entity_id = None
    match = None
    surrogate_for_access = None

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
        surrogate_for_access = surrogate
        entity_type = "case"
        entity_id = surrogate_id
    elif body.intended_parent_id:
        parent = ip_service.get_intended_parent(db, body.intended_parent_id, session.org_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intended parent not found",
            )
        entity_type = "intended_parent"
        entity_id = body.intended_parent_id
    elif body.match_id:
        match = match_service.get_match(db, body.match_id, session.org_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        entity_type = "match"
        entity_id = body.match_id

        # Enforce access to the associated surrogate (when present)
        if match.surrogate_id:
            surrogate_for_access = surrogate_service.get_surrogate(
                db, session.org_id, match.surrogate_id
            )

    # Surrogate access enforcement (owner/role-based). For IP-only tasks, there may be no surrogate to check.
    if surrogate_for_access:
        check_surrogate_access(
            surrogate=surrogate_for_access,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )

    # All-or-nothing: create all tasks in single transaction
    created_tasks: list[dict] = []

    try:
        for task_item in body.tasks:
            # Parse date
            due_date = None
            if task_item.due_date:
                try:
                    due_date = date.fromisoformat(task_item.due_date)
                except ValueError:
                    raise ValueError(f"Invalid date format: {task_item.due_date}")

            # Parse time
            due_time = None
            if task_item.due_time:
                try:
                    due_time = time.fromisoformat(task_item.due_time)
                except ValueError:
                    raise ValueError(f"Invalid time format: {task_item.due_time}")

            # Parse task type
            try:
                task_type = TaskType(task_item.task_type.lower())
            except ValueError:
                task_type = TaskType.OTHER

            # Resolve entity links for task - Task model only has surrogate_id and intended_parent_id
            task_surrogate_id = surrogate_id
            task_ip_id = body.intended_parent_id

            # If creating from match, link to both case and intended_parent from the match
            if body.match_id and entity_type == "match":
                task_surrogate_id = match.surrogate_id if match else None
                task_ip_id = match.intended_parent_id if match else None

            if not task_surrogate_id and not task_ip_id:
                raise ValueError("Each task must be linked to a surrogate_id or intended_parent_id")

            # Create task with appropriate entity link
            task = Task(
                organization_id=session.org_id,
                surrogate_id=task_surrogate_id,
                intended_parent_id=task_ip_id,
                title=task_item.title,
                description=task_item.description,
                task_type=task_type,
                due_date=due_date,
                due_time=due_time,
                owner_type="user",
                owner_id=session.user_id,
                created_by_user_id=session.user_id,
            )
            db.add(task)
            db.flush()  # Get task ID

            created_tasks.append(
                {
                    "task_id": str(task.id),
                    "title": task.title,
                }
            )

        # Log single case activity for bulk creation (when a case is available)
        surrogate_id_for_activity = None
        if entity_type == "match" and match and match.surrogate_id:
            surrogate_id_for_activity = match.surrogate_id
        elif entity_type == "case" and surrogate_id:
            surrogate_id_for_activity = surrogate_id

        if surrogate_id_for_activity:
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id_for_activity,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.TASK_CREATED,
                actor_user_id=session.user_id,
                details={
                    "description": f"Created {len(created_tasks)} tasks from AI schedule parsing",
                    "source": "ai",
                    "request_id": str(body.request_id),
                    "task_ids": [t["task_id"] for t in created_tasks],
                    "entity_type": entity_type,
                    "entity_id": str(entity_id) if entity_id else None,
                },
            )

        result = BulkTaskCreateResponse(
            success=True,
            created=created_tasks,
        )

        db.add(
            AIBulkTaskRequest(
                organization_id=session.org_id,
                user_id=session.user_id,
                request_id=body.request_id,
                response_payload=result.model_dump(),
            )
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_request = (
                db.query(AIBulkTaskRequest)
                .filter(
                    AIBulkTaskRequest.organization_id == session.org_id,
                    AIBulkTaskRequest.user_id == session.user_id,
                    AIBulkTaskRequest.request_id == body.request_id,
                )
                .first()
            )
            if existing_request:
                return BulkTaskCreateResponse(**existing_request.response_payload)
            raise

        logger.info(
            f"Created {len(created_tasks)} tasks for {entity_type} {entity_id} "
            f"by user {session.user_id}"
        )

        return result

    except ValueError as e:
        db.rollback()
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error=str(e),
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk task creation failed: {e}")
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error="Failed to create tasks",
        )
