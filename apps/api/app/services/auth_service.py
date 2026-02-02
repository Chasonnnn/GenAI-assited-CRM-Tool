"""Authentication service - user resolution, invite handling, session creation."""

from datetime import datetime, timezone
import logging

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import Request

from app.core.security import create_session_token
from app.db.enums import AuthProvider, Role
from app.db.models import AuthIdentity, Membership, OrgInvite, User
from app.services.google_oauth import GoogleUserInfo
from app.services import session_service

logger = logging.getLogger(__name__)


def find_user_by_identity(
    db: Session, provider: AuthProvider, provider_subject: str
) -> User | None:
    """Find user by their external identity provider credentials."""
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == provider.value,
            AuthIdentity.provider_subject == provider_subject,
        )
        .first()
    )
    return identity.user if identity else None


def get_valid_invite(db: Session, email: str) -> OrgInvite | None:
    """
    Find valid pending invite for email (globally).

    Valid means:
    - accepted_at IS NULL (not already used)
    - revoked_at IS NULL (not revoked)
    - expires_at IS NULL OR expires_at > now()
    """
    return (
        db.query(OrgInvite)
        .filter(
            func.lower(OrgInvite.email) == email.lower(),
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
            or_(OrgInvite.expires_at.is_(None), OrgInvite.expires_at > func.now()),
        )
        .order_by(OrgInvite.created_at.desc())
        .first()
    )


def get_expired_invite(db: Session, email: str) -> OrgInvite | None:
    """Check for expired invite (for better error messaging)."""
    return (
        db.query(OrgInvite)
        .filter(
            func.lower(OrgInvite.email) == email.lower(),
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
            OrgInvite.expires_at.isnot(None),
            OrgInvite.expires_at <= func.now(),
        )
        .order_by(OrgInvite.created_at.desc())
        .first()
    )


def create_user_from_invite(
    db: Session, invite: OrgInvite, google_user: GoogleUserInfo
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
        is_active=True,
    )
    db.add(membership)

    # Mark invite as accepted
    invite.accepted_at = datetime.now(timezone.utc)

    # Add to Surrogate Pool queue if role qualifies
    from app.services import membership_service

    membership_service.ensure_surrogate_pool_membership(
        db=db,
        org_id=invite.organization_id,
        user_id=user.id,
        role=invite.role.value if hasattr(invite.role, "value") else invite.role,
    )

    db.commit()
    db.refresh(user)
    db.refresh(membership)

    return user, membership


def resolve_user_and_create_session(
    db: Session,
    google_user: GoogleUserInfo,
    request: Request | None = None,
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

    def _log_login_failed(org_id, reason: str) -> None:
        if not org_id:
            return
        try:
            from app.services import audit_service

            audit_service.log_login_failed(
                db=db,
                org_id=org_id,
                email=google_user.email,
                reason=reason,
                request=request,
            )
            db.commit()
        except Exception as exc:
            logger.warning("Failed to log login failure: %s", exc)

    # Check for existing auth identity
    user = find_user_by_identity(db, AuthProvider.GOOGLE, google_user.sub)

    if user:
        # Existing user - validate and create session
        membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == user.id,
                Membership.is_active.is_(True),
            )
            .first()
        )
        if not user.is_active:
            _log_login_failed(
                membership.organization_id if membership else None, "account_disabled"
            )
            return None, "account_disabled"

        if not membership:
            invite = get_valid_invite(db, google_user.email)
            if invite:
                try:
                    from app.services import invite_service, membership_service

                    invite_service.accept_invite(db, invite.id, user.id)
                    membership = (
                        db.query(Membership)
                        .filter(
                            Membership.user_id == user.id,
                            Membership.is_active.is_(True),
                        )
                        .first()
                    )
                    if membership:
                        membership_service.ensure_surrogate_pool_membership(
                            db=db,
                            org_id=membership.organization_id,
                            user_id=user.id,
                            role=membership.role,
                        )
                except (PermissionError, ValueError) as exc:
                    logger.warning("Failed to accept invite for existing user: %s", exc)
                    _log_login_failed(invite.organization_id if invite else None, "invite_invalid")
                    return None, "no_membership"
            if not membership:
                return None, "no_membership"

        # Track last login time
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()

        # Check MFA status - if MFA is enabled, user needs to complete challenge
        # If MFA not yet set up but required, they need to set it up
        mfa_required = True  # MFA required for all users
        mfa_verified = False  # User hasn't verified MFA yet in this session

        token = create_session_token(
            user.id,
            membership.organization_id,
            membership.role,
            user.token_version,
            mfa_verified=mfa_verified,
            mfa_required=mfa_required,
        )

        # Create session record in database (enables revocation)
        session_service.create_session(
            db=db,
            user_id=user.id,
            org_id=membership.organization_id,
            token=token,
            request=request,
        )

        try:
            from app.services import audit_service

            audit_service.log_login_success(
                db=db,
                org_id=membership.organization_id,
                user_id=user.id,
                request=request,
                provider="google",
            )
            db.commit()
        except Exception as exc:
            logger.warning("Failed to log login success: %s", exc)
        return token, None

    # New user - check for valid invite
    invite = get_valid_invite(db, google_user.email)

    if not invite:
        expired = get_expired_invite(db, google_user.email)
        if expired:
            _log_login_failed(expired.organization_id, "invite_expired")
            return None, "invite_expired"
        # No org context available to log
        return None, "not_invited"

    # Validate role from invite
    try:
        Role(invite.role)
    except ValueError:
        _log_login_failed(invite.organization_id, "invalid_invite_role")
        return None, "invalid_invite_role"

    # Create user from invite
    user, membership = create_user_from_invite(db, invite, google_user)

    # Track last login time for new users
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # New users need to set up MFA
    token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )

    # Create session record in database (enables revocation)
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=membership.organization_id,
        token=token,
        request=request,
    )

    try:
        from app.services import audit_service

        audit_service.log_login_success(
            db=db,
            org_id=membership.organization_id,
            user_id=user.id,
            request=request,
            provider="google",
        )
        db.commit()
    except Exception as exc:
        logger.warning("Failed to log login success: %s", exc)
    return token, None
