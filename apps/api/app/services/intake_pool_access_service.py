"""Intake pool access grants.

These grants let one intake specialist work another intake specialist's owned case pool
without changing surrogate ownership.
"""

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.db.enums import Role
from app.db.models import IntakePoolAccessGrant, Membership, User


class IntakePoolAccessError(ValueError):
    """Raised when an intake pool grant is invalid."""


def _get_active_intake_membership(db: Session, org_id: UUID, user_id: UUID) -> Membership | None:
    return (
        db.query(Membership)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            Membership.role == Role.INTAKE_SPECIALIST.value,
        )
        .first()
    )


def _require_active_intake_member(db: Session, org_id: UUID, user_id: UUID, label: str) -> None:
    if _get_active_intake_membership(db, org_id, user_id):
        return
    raise IntakePoolAccessError(f"{label} must be an active intake specialist")


def list_grants(db: Session, org_id: UUID, grantee_user_id: UUID | None = None) -> list[dict]:
    """List intake pool grants with source/grantee display details."""
    source_user = aliased(User)
    grantee_user = aliased(User)
    query = (
        db.query(
            IntakePoolAccessGrant,
            source_user.display_name.label("source_name"),
            source_user.email.label("source_email"),
            grantee_user.display_name.label("grantee_name"),
            grantee_user.email.label("grantee_email"),
        )
        .join(
            source_user,
            source_user.id == IntakePoolAccessGrant.source_user_id,
        )
        .join(
            grantee_user,
            grantee_user.id == IntakePoolAccessGrant.grantee_user_id,
        )
        .filter(
            IntakePoolAccessGrant.organization_id == org_id,
        )
    )
    if grantee_user_id:
        query = query.filter(IntakePoolAccessGrant.grantee_user_id == grantee_user_id)

    rows = query.order_by(grantee_user.display_name, source_user.display_name).all()
    return [
        {
            "id": grant.id,
            "source_user_id": grant.source_user_id,
            "source_user_name": source_name,
            "source_user_email": source_email,
            "grantee_user_id": grant.grantee_user_id,
            "grantee_user_name": grantee_name,
            "grantee_user_email": grantee_email,
            "created_by_user_id": grant.created_by_user_id,
            "created_at": grant.created_at,
            "updated_at": grant.updated_at,
        }
        for grant, source_name, source_email, grantee_name, grantee_email in rows
    ]


def create_grant(
    db: Session,
    org_id: UUID,
    *,
    source_user_id: UUID,
    grantee_user_id: UUID,
    actor_user_id: UUID,
) -> IntakePoolAccessGrant:
    """Create an intake pool access grant, returning the existing grant if present."""
    if source_user_id == grantee_user_id:
        raise IntakePoolAccessError("Source and grantee must be different intake users")
    _require_active_intake_member(db, org_id, source_user_id, "Source user")
    _require_active_intake_member(db, org_id, grantee_user_id, "Grantee user")

    existing = (
        db.query(IntakePoolAccessGrant)
        .filter(
            IntakePoolAccessGrant.organization_id == org_id,
            IntakePoolAccessGrant.source_user_id == source_user_id,
            IntakePoolAccessGrant.grantee_user_id == grantee_user_id,
        )
        .first()
    )
    if existing:
        return existing

    grant = IntakePoolAccessGrant(
        organization_id=org_id,
        source_user_id=source_user_id,
        grantee_user_id=grantee_user_id,
        created_by_user_id=actor_user_id,
    )
    db.add(grant)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise IntakePoolAccessError("Unable to create intake pool access grant") from exc
    return grant


def get_grant(db: Session, org_id: UUID, grant_id: UUID) -> IntakePoolAccessGrant | None:
    """Fetch an org-scoped intake pool access grant."""
    return (
        db.query(IntakePoolAccessGrant)
        .filter(
            IntakePoolAccessGrant.organization_id == org_id,
            IntakePoolAccessGrant.id == grant_id,
        )
        .first()
    )


def revoke_grant(db: Session, org_id: UUID, grant_id: UUID) -> bool:
    """Revoke an org-scoped intake pool access grant."""
    grant = get_grant(db, org_id, grant_id)
    if not grant:
        return False
    db.delete(grant)
    db.flush()
    return True


def delete_user_grants(db: Session, org_id: UUID, user_id: UUID) -> int:
    """Delete all grants where the user is source or grantee in an org."""
    return (
        db.query(IntakePoolAccessGrant)
        .filter(
            IntakePoolAccessGrant.organization_id == org_id,
            or_(
                IntakePoolAccessGrant.source_user_id == user_id,
                IntakePoolAccessGrant.grantee_user_id == user_id,
            ),
        )
        .delete(synchronize_session=False)
    )
