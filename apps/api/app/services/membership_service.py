"""Membership service - organization membership lookups and role hooks."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Membership, Queue, QueueMember


logger = logging.getLogger(__name__)

# Queue name for surrogate claim workflow
SURROGATE_POOL_QUEUE_NAME = "Surrogate Pool"

# Roles that should be members of the Surrogate Pool queue
SURROGATE_POOL_ROLES = {"case_manager", "admin", "developer"}


def get_membership_by_user_id(db: Session, user_id: UUID) -> Membership | None:
    """Get membership by user ID (first match)."""
    return (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
        )
        .first()
    )


def get_membership_for_org(db: Session, org_id: UUID, user_id: UUID) -> Membership | None:
    """Get membership scoped to an organization."""
    return (
        db.query(Membership)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
        )
        .first()
    )


def ensure_surrogate_pool_membership(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    role: str,
) -> bool:
    """
    Add user to Surrogate Pool queue if they have a qualifying role.

    Call this after:
    - Creating a membership from an invite
    - Changing a user's role

    Returns True if user was added to queue, False otherwise.
    """
    # Check if role qualifies for Surrogate Pool
    if role not in SURROGATE_POOL_ROLES:
        return False

    # Find the Surrogate Pool queue for this org
    queue = (
        db.query(Queue)
        .filter(
            Queue.organization_id == org_id,
            Queue.name == SURROGATE_POOL_QUEUE_NAME,
            Queue.is_active.is_(True),
        )
        .first()
    )

    if not queue:
        # Queue doesn't exist yet - will be created by migration or org setup
        logger.debug(
            "Surrogate Pool queue not found for org %s, skipping membership",
            org_id,
        )
        return False

    # Check if already a member
    existing = (
        db.query(QueueMember)
        .filter(
            QueueMember.queue_id == queue.id,
            QueueMember.user_id == user_id,
        )
        .first()
    )

    if existing:
        return False

    # Add to queue
    member = QueueMember(queue_id=queue.id, user_id=user_id)
    db.add(member)
    db.flush()

    logger.info(
        "Added user %s to Surrogate Pool queue in org %s",
        user_id,
        org_id,
    )
    return True


def remove_surrogate_pool_membership(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    new_role: str,
) -> bool:
    """
    Remove user from Surrogate Pool queue if they no longer have a qualifying role.

    Call this after changing a user's role to a non-qualifying role.

    Returns True if user was removed from queue, False otherwise.
    """
    # If new role still qualifies, don't remove
    if new_role in SURROGATE_POOL_ROLES:
        return False

    # Find the Surrogate Pool queue
    queue = (
        db.query(Queue)
        .filter(
            Queue.organization_id == org_id,
            Queue.name == SURROGATE_POOL_QUEUE_NAME,
            Queue.is_active.is_(True),
        )
        .first()
    )

    if not queue:
        return False

    # Remove membership
    deleted = (
        db.query(QueueMember)
        .filter(
            QueueMember.queue_id == queue.id,
            QueueMember.user_id == user_id,
        )
        .delete()
    )

    if deleted:
        logger.info(
            "Removed user %s from Surrogate Pool queue in org %s",
            user_id,
            org_id,
        )

    return deleted > 0
