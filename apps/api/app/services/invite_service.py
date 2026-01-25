"""Invitation management service with rate limiting."""

from datetime import datetime, timedelta, timezone
from typing import Literal
import uuid

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import OrgInvite, Membership, User, Organization
from app.services import org_service


# Rate limit configuration
INVITE_RESEND_COOLDOWN_MINUTES = 5
MAX_RESENDS_PER_DAY = 3
INVITE_EXPIRY_DAYS = 7
MAX_PENDING_INVITES_PER_ORG = 50
INVITE_ALLOWED_ROLES = {
    Role.INTAKE_SPECIALIST.value,
    Role.CASE_MANAGER.value,
    Role.ADMIN.value,
}
INVITE_ALLOWED_ROLES_PLATFORM = INVITE_ALLOWED_ROLES | {Role.DEVELOPER.value}


def validate_invite_role(role: str, *, allow_developer: bool = False) -> str:
    role_value = role.value if hasattr(role, "value") else role
    allowed_roles = INVITE_ALLOWED_ROLES_PLATFORM if allow_developer else INVITE_ALLOWED_ROLES
    if not Role.has_value(role_value) or role_value not in allowed_roles:
        raise ValueError("Invalid invite role")
    return role_value


def get_invite_status(
    invite: OrgInvite,
) -> Literal["pending", "accepted", "expired", "revoked"]:
    """Derive invite status from fields."""
    if invite.revoked_at:
        return "revoked"
    if invite.accepted_at:
        return "accepted"
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        return "expired"
    return "pending"


def list_invites(db: Session, org_id: uuid.UUID) -> list[OrgInvite]:
    """List all invites for organization (including accepted/revoked for history)."""
    return (
        db.query(OrgInvite)
        .filter(OrgInvite.organization_id == org_id)
        .order_by(OrgInvite.created_at.desc())
        .limit(100)
        .all()
    )


def list_pending_invites(db: Session, org_id: uuid.UUID) -> list[OrgInvite]:
    """List only pending (active) invites."""
    return (
        db.query(OrgInvite)
        .filter(
            OrgInvite.organization_id == org_id,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
            or_(OrgInvite.expires_at.is_(None), OrgInvite.expires_at > func.now()),
        )
        .order_by(OrgInvite.created_at.desc())
        .all()
    )


def count_pending_invites(db: Session, org_id: uuid.UUID) -> int:
    """Count active pending invites for rate limiting."""
    return (
        db.query(func.count(OrgInvite.id))
        .filter(
            OrgInvite.organization_id == org_id,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
            or_(OrgInvite.expires_at.is_(None), OrgInvite.expires_at > func.now()),
        )
        .scalar()
        or 0
    )


def create_invite(
    db: Session,
    org_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_user_id: uuid.UUID,
) -> OrgInvite:
    """Create a new invitation."""
    org = org_service.get_org_by_id(db, org_id)
    if not org:
        raise ValueError("Organization not found")
    email = email.lower().strip()
    role_value = validate_invite_role(role)

    # Check org limit
    pending_count = count_pending_invites(db, org_id)
    if pending_count >= MAX_PENDING_INVITES_PER_ORG:
        raise ValueError(f"Maximum of {MAX_PENDING_INVITES_PER_ORG} pending invites reached")

    # Check if already a member
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        existing_membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == existing_user.id,
                Membership.organization_id == org_id,
            )
            .first()
        )
        if existing_membership and existing_membership.is_active:
            raise ValueError("User is already a member of this organization")

    # Check for existing pending invite
    existing_invite = (
        db.query(OrgInvite)
        .filter(
            func.lower(OrgInvite.email) == email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
        )
        .first()
    )
    if existing_invite:
        raise ValueError("A pending invite already exists for this email")

    invite = OrgInvite(
        organization_id=org_id,
        email=email,
        role=role_value,
        invited_by_user_id=invited_by_user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS),
        resend_count=0,
    )
    db.add(invite)
    db.flush()

    return invite


def can_resend(invite: OrgInvite) -> tuple[bool, str | None]:
    """Check if invite can be resent. Returns (can_resend, error_reason)."""
    if invite.accepted_at:
        return False, "Invite already accepted"
    if invite.revoked_at:
        return False, "Invite was revoked"

    # Check cooldown
    if invite.last_resent_at:
        cooldown_end = invite.last_resent_at + timedelta(minutes=INVITE_RESEND_COOLDOWN_MINUTES)
        if datetime.now(timezone.utc) < cooldown_end:
            remaining = int((cooldown_end - datetime.now(timezone.utc)).total_seconds())
            return False, f"Wait {remaining} seconds before resending"

    # Check daily limit
    if invite.resend_count >= MAX_RESENDS_PER_DAY:
        return False, f"Maximum of {MAX_RESENDS_PER_DAY} resends per day reached"

    return True, None


def resend_invite(db: Session, invite: OrgInvite) -> None:
    """Mark invite as resent (increment counter, update timestamp)."""
    can, error = can_resend(invite)
    if not can:
        raise ValueError(error)

    invite.resend_count += 1
    invite.last_resent_at = datetime.now(timezone.utc)
    # Extend expiry on resend
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)

    db.flush()


def revoke_invite(
    db: Session,
    invite: OrgInvite,
    revoked_by_user_id: uuid.UUID,
) -> None:
    """Revoke an invitation."""
    if invite.accepted_at:
        raise ValueError("Cannot revoke an accepted invite")
    if invite.revoked_at:
        raise ValueError("Invite already revoked")

    invite.revoked_at = datetime.now(timezone.utc)
    invite.revoked_by_user_id = revoked_by_user_id

    db.flush()


def get_invite(db: Session, org_id: uuid.UUID, invite_id: uuid.UUID) -> OrgInvite | None:
    """Get single invite by ID."""
    return (
        db.query(OrgInvite)
        .filter(
            OrgInvite.id == invite_id,
            OrgInvite.organization_id == org_id,
        )
        .first()
    )


def get_invite_by_id(db: Session, invite_id: uuid.UUID) -> OrgInvite | None:
    """Get invite by ID without org scoping."""
    return db.query(OrgInvite).filter(OrgInvite.id == invite_id).first()


def get_invite_details(
    db: Session, invite_id: uuid.UUID
) -> tuple[OrgInvite | None, str, str | None]:
    """Get invite with organization and inviter details."""
    invite = get_invite_by_id(db, invite_id)
    if not invite:
        return None, "Unknown Organization", None

    org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
    org_name = org_service.get_org_display_name(org)

    inviter_name = None
    if invite.invited_by_user_id:
        inviter = db.query(User).filter(User.id == invite.invited_by_user_id).first()
        inviter_name = inviter.display_name if inviter else None

    return invite, org_name, inviter_name


def accept_invite(
    db: Session,
    invite_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Accept an invitation and create membership."""
    invite = get_invite_by_id(db, invite_id)
    if not invite:
        raise ValueError("Invite not found")

    status = get_invite_status(invite)
    if status == "accepted":
        raise ValueError("Invite already accepted")
    if status == "expired":
        raise ValueError("Invite has expired")
    if status == "revoked":
        raise ValueError("Invite was revoked")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    if user.email.lower() != invite.email.lower():
        raise PermissionError("This invite was sent to a different email address")

    role_value = validate_invite_role(invite.role)

    existing = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.organization_id == invite.organization_id,
        )
        .first()
    )
    if existing:
        if existing.is_active:
            raise ValueError("Already a member of this organization")
        existing.role = role_value
        existing.is_active = True
        invite.accepted_at = datetime.now(timezone.utc)
        db.commit()
        org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
        org_name = org_service.get_org_display_name(org)
        return {
            "organization_id": str(invite.organization_id),
            "organization_name": org_name,
        }

    membership = Membership(
        user_id=user_id,
        organization_id=invite.organization_id,
        role=role_value,
        is_active=True,
    )
    db.add(membership)

    invite.accepted_at = datetime.now(timezone.utc)

    db.commit()

    org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
    org_name = org_service.get_org_display_name(org)

    return {
        "organization_id": str(invite.organization_id),
        "organization_name": org_name,
    }
