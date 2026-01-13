"""Membership service - organization membership lookups."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Membership


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


def get_membership_for_org(
    db: Session, org_id: UUID, user_id: UUID
) -> Membership | None:
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
