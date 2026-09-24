"""Task creation for authorized workflow subjects."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import OwnerType, TaskType
from app.db.models import Donor, Surrogate


def create_task(
    db: Session,
    action: dict,
    entity: Surrogate | Donor,
    workflow_actor_id: UUID | None = None,
    use_workflow_actor: bool = False,
) -> dict:
    """Create a task linked to the workflow subject."""
    from datetime import timedelta

    from app.schemas.task import TaskCreate
    from app.services import task_service

    title = action.get("title", "Follow up")
    description = action.get("description")
    due_days = action.get("due_days", 1)
    assignee = action.get("assignee", "owner")

    # Determine assignee
    owner_type = OwnerType.USER.value
    owner_id = None
    if assignee == "owner":
        owner_type = entity.owner_type
        owner_id = entity.owner_id
    elif assignee == "creator":
        owner_type = OwnerType.USER.value
        owner_id = getattr(entity, "created_by_user_id", None) or entity.owner_id
    elif isinstance(assignee, str) and assignee.startswith(("admin", "owner", "creator")):
        owner_type = entity.owner_type
        owner_id = entity.owner_id
    else:
        owner_type = OwnerType.USER.value
        owner_id = UUID(assignee) if assignee else None

    due_date = datetime.now(UTC) + timedelta(days=due_days)

    actor_user_id = (
        workflow_actor_id if use_workflow_actor else getattr(entity, "created_by_user_id", None)
    )
    if not actor_user_id and entity.owner_type == OwnerType.USER.value:
        actor_user_id = entity.owner_id
    if not actor_user_id:
        actor_user_id = workflow_actor_id
    if not actor_user_id:
        return {"success": False, "error": "No actor user available for task creation"}

    task_data = TaskCreate(
        title=title,
        description=description,
        task_type=TaskType.FOLLOW_UP,
        surrogate_id=entity.id if isinstance(entity, Surrogate) else None,
        donor_id=entity.id if isinstance(entity, Donor) else None,
        owner_type=owner_type,
        owner_id=owner_id,
        due_date=due_date.date(),
    )
    task = task_service.create_task(
        db=db,
        org_id=entity.organization_id,
        user_id=actor_user_id,
        data=task_data,
    )

    return {
        "success": True,
        "task_id": str(task.id),
        "description": f"Created task: {title}",
    }
