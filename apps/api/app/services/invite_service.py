"""Invitation management service with rate limiting."""

from datetime import datetime, timedelta
from typing import Literal
import uuid

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.db.models import OrgInvite, Membership, User


# Rate limit configuration
INVITE_RESEND_COOLDOWN_MINUTES = 5
MAX_RESENDS_PER_DAY = 3
INVITE_EXPIRY_DAYS = 7
MAX_PENDING_INVITES_PER_ORG = 50


def get_invite_status(invite: OrgInvite) -> Literal["pending", "accepted", "expired", "revoked"]:
    """Derive invite status from fields."""
    if invite.revoked_at:
        return "revoked"
    if invite.accepted_at:
        return "accepted"
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return "expired"
    return "pending"


def list_invites(db: Session, org_id: uuid.UUID) -> list[OrgInvite]:
    """List all invites for organization (including accepted/revoked for history)."""
    return db.query(OrgInvite).filter(
        OrgInvite.organization_id == org_id
    ).order_by(OrgInvite.created_at.desc()).limit(100).all()


def list_pending_invites(db: Session, org_id: uuid.UUID) -> list[OrgInvite]:
    """List only pending (active) invites."""
    return db.query(OrgInvite).filter(
        OrgInvite.organization_id == org_id,
        OrgInvite.accepted_at.is_(None),
        OrgInvite.revoked_at.is_(None),
        or_(
            OrgInvite.expires_at.is_(None),
            OrgInvite.expires_at > func.now()
        )
    ).order_by(OrgInvite.created_at.desc()).all()


def count_pending_invites(db: Session, org_id: uuid.UUID) -> int:
    """Count active pending invites for rate limiting."""
    return db.query(func.count(OrgInvite.id)).filter(
        OrgInvite.organization_id == org_id,
        OrgInvite.accepted_at.is_(None),
        OrgInvite.revoked_at.is_(None),
        or_(
            OrgInvite.expires_at.is_(None),
            OrgInvite.expires_at > func.now()
        )
    ).scalar() or 0


def create_invite(
    db: Session,
    org_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_user_id: uuid.UUID,
) -> OrgInvite:
    """Create a new invitation."""
    email = email.lower().strip()
    
    # Check org limit
    pending_count = count_pending_invites(db, org_id)
    if pending_count >= MAX_PENDING_INVITES_PER_ORG:
        raise ValueError(f"Maximum of {MAX_PENDING_INVITES_PER_ORG} pending invites reached")
    
    # Check if already a member
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        existing_membership = db.query(Membership).filter(
            Membership.user_id == existing_user.id,
            Membership.organization_id == org_id
        ).first()
        if existing_membership:
            raise ValueError("User is already a member of this organization")
    
    # Check for existing pending invite
    existing_invite = db.query(OrgInvite).filter(
        func.lower(OrgInvite.email) == email,
        OrgInvite.accepted_at.is_(None),
        OrgInvite.revoked_at.is_(None),
    ).first()
    if existing_invite:
        raise ValueError("A pending invite already exists for this email")
    
    invite = OrgInvite(
        organization_id=org_id,
        email=email,
        role=role,
        invited_by_user_id=invited_by_user_id,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_EXPIRY_DAYS),
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
        if datetime.utcnow() < cooldown_end:
            remaining = int((cooldown_end - datetime.utcnow()).total_seconds())
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
    invite.last_resent_at = datetime.utcnow()
    # Extend expiry on resend
    invite.expires_at = datetime.utcnow() + timedelta(days=INVITE_EXPIRY_DAYS)
    
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
    
    invite.revoked_at = datetime.utcnow()
    invite.revoked_by_user_id = revoked_by_user_id
    
    db.flush()


def get_invite(db: Session, org_id: uuid.UUID, invite_id: uuid.UUID) -> OrgInvite | None:
    """Get single invite by ID."""
    return db.query(OrgInvite).filter(
        OrgInvite.id == invite_id,
        OrgInvite.organization_id == org_id,
    ).first()
