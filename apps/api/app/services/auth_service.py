"""Authentication service - user resolution, invite handling, session creation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.security import create_session_token
from app.db.enums import AuthProvider, Role
from app.db.models import AuthIdentity, Membership, OrgInvite, User
from app.services.google_oauth import GoogleUserInfo


def find_user_by_identity(
    db: Session, 
    provider: AuthProvider, 
    provider_subject: str
) -> User | None:
    """Find user by their external identity provider credentials."""
    identity = db.query(AuthIdentity).filter(
        AuthIdentity.provider == provider.value,
        AuthIdentity.provider_subject == provider_subject
    ).first()
    return identity.user if identity else None


def get_valid_invite(db: Session, email: str) -> OrgInvite | None:
    """
    Find valid pending invite for email (globally).
    
    Valid means:
    - accepted_at IS NULL (not already used)
    - expires_at IS NULL OR expires_at > now()
    """
    return db.query(OrgInvite).filter(
        func.lower(OrgInvite.email) == email.lower(),
        OrgInvite.accepted_at.is_(None),
        or_(
            OrgInvite.expires_at.is_(None),
            OrgInvite.expires_at > func.now()
        )
    ).first()


def get_expired_invite(db: Session, email: str) -> OrgInvite | None:
    """Check for expired invite (for better error messaging)."""
    return db.query(OrgInvite).filter(
        func.lower(OrgInvite.email) == email.lower(),
        OrgInvite.accepted_at.is_(None),
        OrgInvite.expires_at.isnot(None),
        OrgInvite.expires_at <= func.now()
    ).first()


def create_user_from_invite(
    db: Session, 
    invite: OrgInvite, 
    google_user: GoogleUserInfo
) -> tuple[User, Membership]:
    """
    Create user, auth identity, and membership from invite.
    
    Marks the invite as accepted.
    """
    # Create user
    user = User(
        email=google_user.email,
        display_name=google_user.name or google_user.email.split("@")[0],
        avatar_url=google_user.picture,
    )
    db.add(user)
    db.flush()  # Get user.id
    
    # Create auth identity
    identity = AuthIdentity(
        user_id=user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject=google_user.sub,
        email=google_user.email,
    )
    db.add(identity)
    
    # Create membership
    membership = Membership(
        user_id=user.id,
        organization_id=invite.organization_id,
        role=invite.role,
    )
    db.add(membership)
    
    # Mark invite as accepted
    invite.accepted_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    db.refresh(membership)
    
    return user, membership


def resolve_user_and_create_session(
    db: Session, 
    google_user: GoogleUserInfo
) -> tuple[str | None, str | None]:
    """
    Find or create user based on Google identity.
    
    Flow:
    1. Check if user already exists (has auth identity)
    2. If not, check for valid invite
    3. Create user from invite if found
    4. Return session token or error code
    
    Returns:
        (session_token, error_code) - one will be None
    """
    # Check for existing auth identity
    user = find_user_by_identity(db, AuthProvider.GOOGLE, google_user.sub)
    
    if user:
        # Existing user - validate and create session
        if not user.is_active:
            return None, "account_disabled"
        
        membership = db.query(Membership).filter(
            Membership.user_id == user.id
        ).first()
        
        if not membership:
            return None, "no_membership"
        
        token = create_session_token(
            user.id, 
            membership.organization_id, 
            membership.role, 
            user.token_version
        )
        return token, None
    
    # New user - check for valid invite
    invite = get_valid_invite(db, google_user.email)
    
    if not invite:
        expired = get_expired_invite(db, google_user.email)
        if expired:
            return None, "invite_expired"
        return None, "not_invited"
    
    # Validate role from invite
    try:
        Role(invite.role)
    except ValueError:
        return None, "invalid_invite_role"
    
    # Create user from invite
    user, membership = create_user_from_invite(db, invite, google_user)
    
    token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version
    )
    return token, None
