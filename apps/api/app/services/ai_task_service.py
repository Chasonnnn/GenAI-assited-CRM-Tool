"""AI task service - bulk task creation helpers."""

from __future__ import annotations

import logging
from datetime import date, time
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import SurrogateActivityType, TaskType
from app.db.models import AIBulkTaskRequest, Task
from app.schemas.ai_tasks import BulkTaskCreateRequest, BulkTaskCreateResponse
from app.schemas.auth import UserSession
from app.services import activity_service

logger = logging.getLogger(__name__)


def _get_cached_request(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request_id: UUID,
) -> AIBulkTaskRequest | None:
    return (
        db.query(AIBulkTaskRequest)
        .filter(
            AIBulkTaskRequest.organization_id == org_id,
            AIBulkTaskRequest.user_id == user_id,
            AIBulkTaskRequest.request_id == request_id,
        )
        .first()
    )


def get_cached_bulk_response(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request_id: UUID,
) -> BulkTaskCreateResponse | None:
    """Return cached bulk task response if request_id was already processed."""
    existing_request = _get_cached_request(db, org_id, user_id, request_id)
    if not existing_request:
        return None
    return BulkTaskCreateResponse(**existing_request.response_payload)


def create_bulk_tasks(
    db: Session,
    session: UserSession,
    body: BulkTaskCreateRequest,
    *,
    entity_type: str,
    entity_id: UUID | None,
    task_surrogate_id: UUID | None,
    task_intended_parent_id: UUID | None,
    activity_surrogate_id: UUID | None,
) -> BulkTaskCreateResponse:
    """
    Create multiple tasks in a single transaction (all-or-nothing).

    Assumes entity validation and access checks already happened in the router.
    """
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

            if not task_surrogate_id and not task_intended_parent_id:
                raise ValueError("Each task must be linked to a surrogate_id or intended_parent_id")

            task = Task(
                organization_id=session.org_id,
                surrogate_id=task_surrogate_id,
                intended_parent_id=task_intended_parent_id,
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

        if activity_surrogate_id:
            activity_service.log_activity(
                db=db,
                surrogate_id=activity_surrogate_id,
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
            existing_request = _get_cached_request(
                db,
                session.org_id,
                session.user_id,
                body.request_id,
            )
            if existing_request:
                return BulkTaskCreateResponse(**existing_request.response_payload)
            raise

        logger.info(
            "Created %s tasks for %s %s by user %s",
            len(created_tasks),
            entity_type,
            entity_id,
            session.user_id,
        )

        return result

    except ValueError as exc:
        db.rollback()
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.error("Bulk task creation failed: %s", exc)
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error="Failed to create tasks",
        )
