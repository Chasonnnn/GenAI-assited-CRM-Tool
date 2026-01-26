"""Task domain events (side-effect dispatch)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Task, Surrogate, User
from app.services import notification_service


def notify_task_assigned(
    db: Session,
    task: Task,
    *,
    actor_user_id: UUID,
    assignee_id: UUID,
) -> None:
    """Notify a user that a task has been assigned to them."""
    actor = db.query(User).filter(User.id == actor_user_id).first()
    actor_name = actor.display_name if actor else "Someone"

    surrogate_number = None
    if task.surrogate_id:
        surrogate = db.query(Surrogate).filter(Surrogate.id == task.surrogate_id).first()
        surrogate_number = surrogate.surrogate_number if surrogate else None

    notification_service.notify_task_assigned(
        db=db,
        task_id=task.id,
        task_title=task.title,
        org_id=task.organization_id,
        assignee_id=assignee_id,
        actor_name=actor_name,
        surrogate_number=surrogate_number,
    )
