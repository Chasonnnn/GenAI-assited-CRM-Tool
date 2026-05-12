"""Authentication service - user resolution, invite handling, session creation."""

from datetime import datetime, timezone
import logging
from uuid import UUID

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
    identity = find_identity_by_subject(db, provider, provider_subject)
    return identity.user if identity else None


def find_identity_by_subject(
    db: Session, provider: AuthProvider, provider_subject: str
) -> AuthIdentity | None:
    """Find an external identity provider credential row."""
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == provider.value,
            AuthIdentity.provider_subject == provider_subject,
        )
        .first()
    )
    return identity


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


def get_valid_invite_by_id_for_email(
    db: Session, invite_id: str | UUID | None, email: str
) -> OrgInvite | None:
    """Find a valid pending invite by clicked invite ID and verified email."""
    if not invite_id:
        return None
    try:
        normalized_invite_id = UUID(str(invite_id))
    except ValueError:
        return None

    return (
        db.query(OrgInvite)
        .filter(
            OrgInvite.id == normalized_invite_id,
            func.lower(OrgInvite.email) == email.lower(),
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
            or_(OrgInvite.expires_at.is_(None), OrgInvite.expires_at > func.now()),
        )
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


def _normalized_email(email: str) -> str:
    return email.lower().strip()


def _emails_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return _normalized_email(left) == _normalized_email(right)


def _get_active_membership(db: Session, user_id: UUID) -> Membership | None:
    return (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
        )
        .first()
    )


def _get_or_create_user_for_verified_email(db: Session, google_user: GoogleUserInfo) -> User:
    email = _normalized_email(google_user.email)
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        return user

    user = User(
        email=email,
        display_name=google_user.name or email.split("@")[0],
        avatar_url=google_user.picture,
    )
    db.add(user)
    db.flush()
    return user


def _transfer_identity_to_invited_user(
    db: Session,
    identity: AuthIdentity,
    invite: OrgInvite,
    google_user: GoogleUserInfo,
    previous_user: User | None = None,
) -> tuple[User, Membership]:
    """Bind a reused Google identity to the user represented by the verified invite email."""
    from app.services import invite_service, membership_service

    user = _get_or_create_user_for_verified_email(db, google_user)
    if not user.is_active:
        raise ValueError("Invited user account is disabled")

    role_value = invite_service.validate_invite_role(invite.role)
    now = datetime.now(timezone.utc)

    existing_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.organization_id == invite.organization_id,
        )
        .first()
    )
    if existing_membership:
        existing_membership.role = role_value
        existing_membership.is_active = True
        membership = existing_membership
    else:
        membership = Membership(
            user_id=user.id,
            organization_id=invite.organization_id,
            role=role_value,
            is_active=True,
        )
        db.add(membership)

    identity.user_id = user.id
    identity.email = _normalized_email(google_user.email)
    invite.accepted_at = now

    if previous_user and previous_user.id != user.id:
        previous_membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == previous_user.id,
                Membership.organization_id == invite.organization_id,
            )
            .first()
        )
        if previous_membership:
            previous_membership.is_active = False
            previous_user.token_version += 1

    membership_service.ensure_surrogate_pool_membership(
        db=db,
        org_id=invite.organization_id,
        user_id=user.id,
        role=role_value,
    )

    db.commit()
    db.refresh(user)
    db.refresh(membership)
    return user, membership


def _create_login_session(
    db: Session,
    user: User,
    membership: Membership,
    request: Request | None = None,
) -> str:
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # MFA is required for all users. A fresh Google login still needs Duo/TOTP verification.
    token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )

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
    return token


def resolve_user_and_create_session(
    db: Session,
    google_user: GoogleUserInfo,
    request: Request | None = None,
    invite_id: str | UUID | None = None,
) -> tuple[str | None, str | None]:
    """
    Find or create user based on Google identity.

    Flow:
    1. Check if user already exists (has auth identity)
    2. If not, check for the clicked invite, then any valid invite by verified email
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
    identity = find_identity_by_subject(db, AuthProvider.GOOGLE, google_user.sub)
    user = identity.user if identity else None

    if user:
        if not _emails_match(user.email, google_user.email):
            invite = get_valid_invite_by_id_for_email(db, invite_id, google_user.email)
            if not invite:
                invite = get_valid_invite(db, google_user.email)
            if invite and identity:
                try:
                    from app.services.audit_service import hash_email

                    logger.warning(
                        "Transferring reused Google identity from user=%s email=%s "
                        "to invited email=%s invite=%s",
                        user.id,
                        hash_email(user.email),
                        hash_email(google_user.email),
                        invite.id,
                    )
                    invited_user, invited_membership = _transfer_identity_to_invited_user(
                        db,
                        identity,
                        invite,
                        google_user,
                        previous_user=user,
                    )
                    token = _create_login_session(
                        db,
                        invited_user,
                        invited_membership,
                        request=request,
                    )
                    return token, None
                except (PermissionError, ValueError) as exc:
                    logger.warning("Failed to transfer reused Google identity: %s", exc)
                    _log_login_failed(invite.organization_id, "identity_email_mismatch")
                    return None, "no_membership"

            active_membership = _get_active_membership(db, user.id)
            _log_login_failed(
                active_membership.organization_id if active_membership else None,
                "identity_email_mismatch",
            )
            return None, "no_membership"

        # Existing user - validate and create session
        membership = _get_active_membership(db, user.id)
        if not user.is_active:
            _log_login_failed(
                membership.organization_id if membership else None, "account_disabled"
            )
            return None, "account_disabled"

        if not membership:
            invite = get_valid_invite_by_id_for_email(db, invite_id, google_user.email)
            if not invite:
                invite = get_valid_invite(db, google_user.email)
            if invite:
                try:
                    from app.services import invite_service, membership_service

                    invite_service.accept_invite(
                        db,
                        invite.id,
                        user.id,
                        verified_email=google_user.email,
                    )
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

        token = _create_login_session(db, user, membership, request=request)
        return token, None

    # New user - check for valid invite
    invite = get_valid_invite_by_id_for_email(db, invite_id, google_user.email)
    if not invite:
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

    token = _create_login_session(db, user, membership, request=request)
    return token, None
