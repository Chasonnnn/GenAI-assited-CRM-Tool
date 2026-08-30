"""Task domain events (side-effect dispatch)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Donor, Surrogate, Task, User
from app.services import notification_facade


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
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == task.surrogate_id,
                Surrogate.organization_id == task.organization_id,
            )
            .first()
        )
        surrogate_number = surrogate.surrogate_number if surrogate else None

    donor_number = None
    donor_type = None
    if task.donor_id:
        donor = (
            db.query(Donor)
            .filter(
                Donor.id == task.donor_id,
                Donor.organization_id == task.organization_id,
            )
            .first()
        )
        if donor:
            donor_number = donor.donor_number
            donor_type = donor.donor_type

    notification_facade.notify_task_assigned(
        db=db,
        task_id=task.id,
        task_title=task.title,
        org_id=task.organization_id,
        assignee_id=assignee_id,
        actor_name=actor_name,
        surrogate_number=surrogate_number,
        donor_number=donor_number,
        donor_type=donor_type,
    )
