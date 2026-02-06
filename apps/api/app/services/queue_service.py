"""Queue management service with claim/release and audit logging."""

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import Queue, Surrogate, QueueMember, User
from app.db.enums import SurrogateActivityType
from app.db.enums import OwnerType
from app.services import activity_service


class QueueServiceError(Exception):
    """Base exception for queue service errors."""

    pass


class QueueNotFoundError(QueueServiceError):
    """Queue not found."""

    pass


class SurrogateNotFoundError(QueueServiceError):
    """Surrogate not found."""

    pass


class SurrogateAlreadyClaimedError(QueueServiceError):
    """Surrogate is already claimed by a user (not in a queue)."""

    pass


class SurrogateNotInQueueError(QueueServiceError):
    """Surrogate is not in a queue (cannot release)."""

    pass


class DuplicateQueueNameError(QueueServiceError):
    """Queue name already exists in org."""

    pass


class NotQueueMemberError(QueueServiceError):
    """User is not a member of the queue."""

    pass


class QueueMemberExistsError(QueueServiceError):
    """Queue member already exists."""

    pass


class QueueMemberNotFoundError(QueueServiceError):
    """Queue member not found."""

    pass


class QueueMemberUserNotFoundError(QueueServiceError):
    """User not found in org."""

    pass


DEFAULT_QUEUE_NAME = "Unassigned"
SURROGATE_POOL_QUEUE_NAME = "Surrogate Pool"


# =============================================================================
# Queue CRUD
# =============================================================================


def list_queues(
    db: Session,
    org_id: UUID,
    include_inactive: bool = False,
) -> list[Queue]:
    """List queues for an organization."""
    query = select(Queue).where(Queue.organization_id == org_id)
    if not include_inactive:
        query = query.where(Queue.is_active.is_(True))
    query = query.order_by(Queue.name)
    return list(db.execute(query).scalars().all())


def get_queue(db: Session, org_id: UUID, queue_id: UUID) -> Queue | None:
    """Get a single queue by ID."""
    return db.execute(
        select(Queue).where(and_(Queue.id == queue_id, Queue.organization_id == org_id))
    ).scalar_one_or_none()


def create_queue(
    db: Session,
    org_id: UUID,
    name: str,
    description: str | None = None,
) -> Queue:
    """Create a new queue."""
    queue = Queue(
        organization_id=org_id,
        name=name.strip(),
        description=description.strip() if description else None,
    )
    try:
        db.add(queue)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateQueueNameError(f"Queue '{name}' already exists")
    return queue


def update_queue(
    db: Session,
    org_id: UUID,
    queue_id: UUID,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> Queue:
    """Update a queue."""
    queue = get_queue(db, org_id, queue_id)
    if not queue:
        raise QueueNotFoundError(f"Queue {queue_id} not found")

    if name is not None:
        queue.name = name.strip()
    if description is not None:
        queue.description = description.strip() if description else None
    if is_active is not None:
        queue.is_active = is_active

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateQueueNameError(f"Queue '{name}' already exists")
    return queue


def delete_queue(db: Session, org_id: UUID, queue_id: UUID) -> None:
    """Soft-delete a queue (set is_active=False)."""
    queue = get_queue(db, org_id, queue_id)
    if not queue:
        raise QueueNotFoundError(f"Queue {queue_id} not found")
    queue.is_active = False
    db.flush()


def get_or_create_default_queue(db: Session, org_id: UUID) -> Queue:
    """
    Get the system default queue for an org, creating it if missing.

    This is used for system-created/unassigned surrogates so every surrogate always has an owner.
    """
    queue = db.execute(
        select(Queue).where(
            and_(
                Queue.organization_id == org_id,
                Queue.name == DEFAULT_QUEUE_NAME,
            )
        )
    ).scalar_one_or_none()

    if queue:
        if not queue.is_active:
            queue.is_active = True
            db.flush()
        return queue

    try:
        return create_queue(
            db=db,
            org_id=org_id,
            name=DEFAULT_QUEUE_NAME,
            description="System default queue",
        )
    except DuplicateQueueNameError:
        # Race condition: another transaction created it
        queue = db.execute(
            select(Queue).where(
                and_(
                    Queue.organization_id == org_id,
                    Queue.name == DEFAULT_QUEUE_NAME,
                )
            )
        ).scalar_one_or_none()
        if queue:
            return queue
        raise


def get_or_create_surrogate_pool_queue(db: Session, org_id: UUID) -> Queue:
    """
    Get the Surrogate Pool queue for an org, creating it if missing.

    This queue holds approved surrogates waiting to be claimed by case managers.
    All case_manager/admin/developer users are automatically members.
    """
    queue = db.execute(
        select(Queue).where(
            and_(
                Queue.organization_id == org_id,
                Queue.name == SURROGATE_POOL_QUEUE_NAME,
            )
        )
    ).scalar_one_or_none()

    if queue:
        if not queue.is_active:
            queue.is_active = True
            db.flush()
        return queue

    try:
        queue = create_queue(
            db=db,
            org_id=org_id,
            name=SURROGATE_POOL_QUEUE_NAME,
            description="Approved surrogates waiting for case manager assignment",
        )
        db.flush()

        # Auto-add all case_manager+ users as members
        from app.db.models import Membership
        from app.db.enums import Role

        manager_roles = [Role.CASE_MANAGER.value, Role.ADMIN.value, Role.DEVELOPER.value]
        memberships = (
            db.query(Membership)
            .filter(
                Membership.organization_id == org_id,
                Membership.role.in_(manager_roles),
                Membership.is_active.is_(True),
            )
            .all()
        )

        for membership in memberships:
            try:
                add_queue_member(db, org_id, queue.id, membership.user_id)
            except (QueueMemberExistsError, QueueMemberUserNotFoundError):
                pass

        return queue
    except DuplicateQueueNameError:
        # Race condition: another transaction created it
        queue = db.execute(
            select(Queue).where(
                and_(
                    Queue.organization_id == org_id,
                    Queue.name == SURROGATE_POOL_QUEUE_NAME,
                )
            )
        ).scalar_one_or_none()
        if queue:
            return queue
        raise


# =============================================================================
# Claim / Release (Atomic with Audit)
# =============================================================================


def claim_surrogate(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    claimer_user_id: UUID,
) -> Surrogate:
    """
    Claim a surrogate from a queue. Atomic operation.

    - Surrogate must be owner_type="queue" (in a queue)
    - Sets owner_type="user", owner_id=claimer
    - Logs activity for audit trail
    - Returns 409-style error if already claimed
    """
    # Lock row for update (atomic claim)
    surrogate = db.execute(
        select(Surrogate)
        .where(and_(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not surrogate:
        raise SurrogateNotFoundError(f"Surrogate {surrogate_id} not found")

    if surrogate.owner_type != OwnerType.QUEUE.value:
        raise SurrogateAlreadyClaimedError("Surrogate is already owned by a user, not in a queue")

    # Check if user is a member of the queue (if queue has members)
    queue = db.query(Queue).filter(Queue.id == surrogate.owner_id).first()
    if queue and queue.members:
        is_member = any(m.user_id == claimer_user_id for m in queue.members)
        if not is_member:
            raise NotQueueMemberError(
                f"You are not a member of queue '{queue.name}' and cannot claim surrogates from it"
            )

    old_queue_id = surrogate.owner_id

    # Transfer ownership to user
    surrogate.owner_type = OwnerType.USER.value
    surrogate.owner_id = claimer_user_id
    surrogate.assigned_at = datetime.now(timezone.utc)

    # Log activity
    activity_service.log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.SURROGATE_CLAIMED,
        actor_user_id=claimer_user_id,
        details={
            "from_queue_id": str(old_queue_id) if old_queue_id else None,
            "to_user_id": str(claimer_user_id),
        },
    )

    return surrogate


def release_surrogate(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    queue_id: UUID,
    releaser_user_id: UUID,
) -> Surrogate:
    """
    Release a surrogate back to a queue.

    - Surrogate must be owner_type="user"
    - Sets owner_type="queue", owner_id=queue_id
    - Logs activity for audit trail
    """
    # Verify queue exists
    queue = get_queue(db, org_id, queue_id)
    if not queue or not queue.is_active:
        raise QueueNotFoundError(f"Queue {queue_id} not found or inactive")

    # Lock row for update
    surrogate = db.execute(
        select(Surrogate)
        .where(and_(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not surrogate:
        raise SurrogateNotFoundError(f"Surrogate {surrogate_id} not found")

    old_owner_id = surrogate.owner_id

    # Transfer ownership to queue
    surrogate.owner_type = OwnerType.QUEUE.value
    surrogate.owner_id = queue_id
    surrogate.assigned_at = None

    # Log activity
    activity_service.log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.SURROGATE_RELEASED,
        actor_user_id=releaser_user_id,
        details={
            "from_user_id": str(old_owner_id) if old_owner_id else None,
            "to_queue_id": str(queue_id),
        },
    )

    return surrogate


def assign_surrogate_to_queue(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    queue_id: UUID,
    assigner_user_id: UUID,
) -> Surrogate:
    """
    Assign a surrogate to a queue (admin action).
    Works whether surrogate is currently user-owned or queue-owned.
    """
    # Verify queue exists
    queue = get_queue(db, org_id, queue_id)
    if not queue or not queue.is_active:
        raise QueueNotFoundError(f"Queue {queue_id} not found or inactive")

    surrogate = db.execute(
        select(Surrogate)
        .where(and_(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not surrogate:
        raise SurrogateNotFoundError(f"Surrogate {surrogate_id} not found")

    old_owner_type = surrogate.owner_type
    old_owner_id = surrogate.owner_id

    # Assign to queue
    surrogate.owner_type = OwnerType.QUEUE.value
    surrogate.owner_id = queue_id
    surrogate.assigned_at = None

    # Log activity
    activity_service.log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.SURROGATE_ASSIGNED_TO_QUEUE,
        actor_user_id=assigner_user_id,
        details={
            "from_owner_type": old_owner_type,
            "from_owner_id": str(old_owner_id) if old_owner_id else None,
            "to_queue_id": str(queue_id),
        },
    )

    return surrogate


def add_queue_member(
    db: Session,
    org_id: UUID,
    queue_id: UUID,
    user_id: UUID,
) -> tuple[QueueMember, User]:
    """Add a user to a queue."""
    # Users are org-scoped via Membership (not a direct FK on User).
    from app.services import membership_service

    membership = membership_service.get_membership_for_org(db, org_id, user_id)
    user = membership.user if membership else None
    if not user:
        raise QueueMemberUserNotFoundError("User not found")

    existing = (
        db.query(QueueMember)
        .filter(
            QueueMember.queue_id == queue_id,
            QueueMember.user_id == user_id,
        )
        .first()
    )
    if existing:
        raise QueueMemberExistsError("User is already a member of this queue")

    member = QueueMember(queue_id=queue_id, user_id=user_id)
    db.add(member)
    db.commit()
    db.refresh(member)

    return member, user


def remove_queue_member(
    db: Session,
    queue_id: UUID,
    user_id: UUID,
) -> None:
    """Remove a user from a queue."""
    result = (
        db.query(QueueMember)
        .filter(
            QueueMember.queue_id == queue_id,
            QueueMember.user_id == user_id,
        )
        .delete()
    )

    if not result:
        raise QueueMemberNotFoundError("Member not found")

    db.commit()
