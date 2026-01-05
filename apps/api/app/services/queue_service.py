"""Queue management service with claim/release and audit logging."""

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import Queue, Case, QueueMember, User
from app.db.enums import CaseActivityType
from app.db.enums import OwnerType
from app.services import activity_service


class QueueServiceError(Exception):
    """Base exception for queue service errors."""

    pass


class QueueNotFoundError(QueueServiceError):
    """Queue not found."""

    pass


class CaseNotFoundError(QueueServiceError):
    """Case not found."""

    pass


class CaseAlreadyClaimedError(QueueServiceError):
    """Case is already claimed by a user (not in a queue)."""

    pass


class CaseNotInQueueError(QueueServiceError):
    """Case is not in a queue (cannot release)."""

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

    This is used for system-created/unassigned cases so every case always has an owner.
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


# =============================================================================
# Claim / Release (Atomic with Audit)
# =============================================================================


def claim_case(
    db: Session,
    org_id: UUID,
    case_id: UUID,
    claimer_user_id: UUID,
) -> Case:
    """
    Claim a case from a queue. Atomic operation.

    - Case must be owner_type="queue" (in a queue)
    - Sets owner_type="user", owner_id=claimer
    - Logs activity for audit trail
    - Returns 409-style error if already claimed
    """
    # Lock row for update (atomic claim)
    case = db.execute(
        select(Case)
        .where(and_(Case.id == case_id, Case.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not case:
        raise CaseNotFoundError(f"Case {case_id} not found")

    if case.owner_type != OwnerType.QUEUE.value:
        raise CaseAlreadyClaimedError("Case is already owned by a user, not in a queue")

    # Check if user is a member of the queue (if queue has members)
    queue = db.query(Queue).filter(Queue.id == case.owner_id).first()
    if queue and queue.members:
        is_member = any(m.user_id == claimer_user_id for m in queue.members)
        if not is_member:
            raise NotQueueMemberError(
                f"You are not a member of queue '{queue.name}' and cannot claim cases from it"
            )

    old_queue_id = case.owner_id

    # Transfer ownership to user
    case.owner_type = OwnerType.USER.value
    case.owner_id = claimer_user_id
    case.assigned_at = datetime.now(timezone.utc)

    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=case_id,
        organization_id=org_id,
        activity_type=CaseActivityType.CASE_CLAIMED,
        actor_user_id=claimer_user_id,
        details={
            "from_queue_id": str(old_queue_id) if old_queue_id else None,
            "to_user_id": str(claimer_user_id),
        },
    )

    return case


def release_case(
    db: Session,
    org_id: UUID,
    case_id: UUID,
    queue_id: UUID,
    releaser_user_id: UUID,
) -> Case:
    """
    Release a case back to a queue.

    - Case must be owner_type="user"
    - Sets owner_type="queue", owner_id=queue_id
    - Logs activity for audit trail
    """
    # Verify queue exists
    queue = get_queue(db, org_id, queue_id)
    if not queue or not queue.is_active:
        raise QueueNotFoundError(f"Queue {queue_id} not found or inactive")

    # Lock row for update
    case = db.execute(
        select(Case)
        .where(and_(Case.id == case_id, Case.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not case:
        raise CaseNotFoundError(f"Case {case_id} not found")

    old_owner_id = case.owner_id

    # Transfer ownership to queue
    case.owner_type = OwnerType.QUEUE.value
    case.owner_id = queue_id
    case.assigned_at = None

    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=case_id,
        organization_id=org_id,
        activity_type=CaseActivityType.CASE_RELEASED,
        actor_user_id=releaser_user_id,
        details={
            "from_user_id": str(old_owner_id) if old_owner_id else None,
            "to_queue_id": str(queue_id),
        },
    )

    return case


def assign_to_queue(
    db: Session,
    org_id: UUID,
    case_id: UUID,
    queue_id: UUID,
    assigner_user_id: UUID,
) -> Case:
    """
    Assign a case to a queue (manager action).
    Works whether case is currently user-owned or queue-owned.
    """
    # Verify queue exists
    queue = get_queue(db, org_id, queue_id)
    if not queue or not queue.is_active:
        raise QueueNotFoundError(f"Queue {queue_id} not found or inactive")

    case = db.execute(
        select(Case)
        .where(and_(Case.id == case_id, Case.organization_id == org_id))
        .with_for_update()
    ).scalar_one_or_none()

    if not case:
        raise CaseNotFoundError(f"Case {case_id} not found")

    old_owner_type = case.owner_type
    old_owner_id = case.owner_id

    # Assign to queue
    case.owner_type = OwnerType.QUEUE.value
    case.owner_id = queue_id
    case.assigned_at = None

    # Log activity
    activity_service.log_activity(
        db=db,
        case_id=case_id,
        organization_id=org_id,
        activity_type=CaseActivityType.CASE_ASSIGNED_TO_QUEUE,
        actor_user_id=assigner_user_id,
        details={
            "from_owner_type": old_owner_type,
            "from_owner_id": str(old_owner_id) if old_owner_id else None,
            "to_queue_id": str(queue_id),
        },
    )

    return case


def add_queue_member(
    db: Session,
    org_id: UUID,
    queue_id: UUID,
    user_id: UUID,
) -> tuple[QueueMember, User]:
    """Add a user to a queue."""
    user = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.organization_id == org_id,
        )
        .first()
    )
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
