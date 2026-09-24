"""Organization-scoped choices for record ownership."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Membership, Queue, User
from app.schemas.record_owner import RecordOwnerOptions, RecordQueueOption, RecordUserOption


def list_owner_options(db: Session, org_id: UUID) -> RecordOwnerOptions:
    users = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(User.display_name, User.id)
        .all()
    )
    queues = (
        db.query(Queue.id, Queue.name)
        .filter(Queue.organization_id == org_id, Queue.is_active.is_(True))
        .order_by(Queue.name, Queue.id)
        .all()
    )
    return RecordOwnerOptions(
        users=[RecordUserOption(id=user.id, display_name=user.display_name) for user in users],
        queues=[RecordQueueOption(id=queue.id, name=queue.name) for queue in queues],
    )


def owner_label(
    db: Session, org_id: UUID, owner_type: str | None, owner_id: UUID | None
) -> str | None:
    if owner_id is None:
        return None
    if owner_type == "user":
        return (
            db.query(User.display_name)
            .join(Membership, Membership.user_id == User.id)
            .filter(
                Membership.organization_id == org_id,
                User.id == owner_id,
            )
            .scalar()
        )
    if owner_type == "queue":
        return (
            db.query(Queue.name)
            .filter(Queue.organization_id == org_id, Queue.id == owner_id)
            .scalar()
        )
    return None
