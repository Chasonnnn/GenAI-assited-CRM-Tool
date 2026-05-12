"""Tests for reusing invites when a user already exists."""

from datetime import datetime, timedelta, timezone
import uuid


def test_existing_user_can_accept_invite_when_membership_inactive(db, test_org):
    """Existing users with inactive membership should be reactivated via invite."""
    from app.db.enums import AuthProvider, Role
    from app.db.models import AuthIdentity, Membership, OrgInvite, User
    from app.services.auth_service import resolve_user_and_create_session
    from app.services.google_oauth import GoogleUserInfo

    user = User(
        id=uuid.uuid4(),
        email="invited-user@example.com",
        display_name="Invited User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="google-sub-123",
        email=user.email,
    )
    db.add(identity)

    membership = Membership(
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        is_active=False,
    )
    db.add(membership)

    invite = OrgInvite(
        organization_id=test_org.id,
        email=user.email,
        role=Role.ADMIN.value,
        invited_by_user_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()

    google_user = GoogleUserInfo(
        sub="google-sub-123",
        email=user.email,
        name="Invited User",
        picture=None,
        hd=None,
    )

    token, error_code = resolve_user_and_create_session(db, google_user)
    assert error_code is None
    assert token is not None

    db.refresh(membership)
    db.refresh(invite)
    assert membership.is_active is True
    assert membership.role == Role.ADMIN.value
    assert invite.accepted_at is not None


def test_reused_google_identity_invite_creates_invited_user_not_removed_member(db, test_org):
    """Reused Google accounts must not reactivate a removed different-email member."""
    from app.db.enums import AuthProvider, Role
    from app.db.models import AuthIdentity, Membership, OrgInvite, User
    from app.core.security import decode_session_token
    from app.services.auth_service import resolve_user_and_create_session
    from app.services.google_oauth import GoogleUserInfo

    removed_user = User(
        id=uuid.uuid4(),
        email="elizabethcontreras@ewifamilyglobal.com",
        display_name="Elizabeth Contreras",
        token_version=1,
        is_active=True,
    )
    db.add(removed_user)
    db.flush()

    identity = AuthIdentity(
        user_id=removed_user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="workspace-account-reused",
        email=removed_user.email,
    )
    db.add(identity)

    removed_membership = Membership(
        user_id=removed_user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        is_active=False,
    )
    db.add(removed_membership)

    invite = OrgInvite(
        organization_id=test_org.id,
        email="serenaguillen@ewifamilyglobal.com",
        role=Role.CASE_MANAGER.value,
        invited_by_user_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()

    google_user = GoogleUserInfo(
        sub="workspace-account-reused",
        email=invite.email,
        name="Serena Guillen",
        picture=None,
        hd=None,
    )

    token, error_code = resolve_user_and_create_session(db, google_user, invite_id=str(invite.id))
    assert error_code is None
    assert token is not None

    invited_user = db.query(User).filter(User.email == invite.email).one_or_none()
    assert invited_user is not None
    assert invited_user.id != removed_user.id

    invited_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == invited_user.id,
            Membership.organization_id == test_org.id,
        )
        .one_or_none()
    )

    db.refresh(identity)
    db.refresh(removed_membership)
    db.refresh(invite)
    payload = decode_session_token(token)
    assert payload["sub"] == str(invited_user.id)
    assert identity.user_id == invited_user.id
    assert identity.email == invite.email
    assert invited_membership is not None
    assert invited_membership.role == Role.CASE_MANAGER.value
    assert removed_membership.is_active is False
    assert invite.accepted_at is not None


def test_reused_google_identity_without_invite_cannot_login_as_existing_member(db, test_org):
    """A mismatched Google email must not receive a session for the stored identity user."""
    from app.db.enums import AuthProvider, Role
    from app.db.models import AuthIdentity, Membership, User
    from app.services.auth_service import resolve_user_and_create_session
    from app.services.google_oauth import GoogleUserInfo

    existing_user = User(
        id=uuid.uuid4(),
        email="elizabethcontreras@ewifamilyglobal.com",
        display_name="Elizabeth Contreras",
        token_version=1,
        is_active=True,
    )
    db.add(existing_user)
    db.flush()

    db.add(
        AuthIdentity(
            user_id=existing_user.id,
            provider=AuthProvider.GOOGLE.value,
            provider_subject="workspace-account-reused-active",
            email=existing_user.email,
        )
    )
    db.add(
        Membership(
            user_id=existing_user.id,
            organization_id=test_org.id,
            role=Role.CASE_MANAGER.value,
            is_active=True,
        )
    )
    db.commit()

    google_user = GoogleUserInfo(
        sub="workspace-account-reused-active",
        email="serenaguillen@ewifamilyglobal.com",
        name="Serena Guillen",
        picture=None,
        hd=None,
    )

    token, error_code = resolve_user_and_create_session(db, google_user)

    assert token is None
    assert error_code == "no_membership"


def test_reused_google_identity_invite_deactivates_existing_different_email_member(db, test_org):
    """Invite-based identity transfer should not leave the old account active."""
    from app.db.enums import AuthProvider, Role
    from app.db.models import AuthIdentity, Membership, OrgInvite, User
    from app.core.security import decode_session_token
    from app.services.auth_service import resolve_user_and_create_session
    from app.services.google_oauth import GoogleUserInfo

    existing_user = User(
        id=uuid.uuid4(),
        email="elizabethcontreras@ewifamilyglobal.com",
        display_name="Elizabeth Contreras",
        token_version=1,
        is_active=True,
    )
    db.add(existing_user)
    db.flush()

    db.add(
        AuthIdentity(
            user_id=existing_user.id,
            provider=AuthProvider.GOOGLE.value,
            provider_subject="workspace-account-reused-with-invite",
            email=existing_user.email,
        )
    )
    existing_membership = Membership(
        user_id=existing_user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        is_active=True,
    )
    db.add(existing_membership)

    invite = OrgInvite(
        organization_id=test_org.id,
        email="serenaguillen@ewifamilyglobal.com",
        role=Role.ADMIN.value,
        invited_by_user_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()

    google_user = GoogleUserInfo(
        sub="workspace-account-reused-with-invite",
        email=invite.email,
        name="Serena Guillen",
        picture=None,
        hd=None,
    )

    token, error_code = resolve_user_and_create_session(db, google_user, invite_id=str(invite.id))

    assert error_code is None
    assert token is not None
    payload = decode_session_token(token)
    assert payload["sub"] != str(existing_user.id)

    invited_user = db.query(User).filter(User.email == invite.email).one()
    invited_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == invited_user.id,
            Membership.organization_id == test_org.id,
        )
        .one()
    )
    db.refresh(existing_membership)
    db.refresh(existing_user)
    assert invited_membership.is_active is True
    assert invited_membership.role == Role.ADMIN.value
    assert existing_membership.is_active is False
    assert existing_user.token_version == 2


def test_existing_user_without_invite_returns_no_membership(db, test_org):
    """Existing users without a valid invite should still fail with no_membership."""
    from app.db.enums import AuthProvider
    from app.db.models import AuthIdentity, User
    from app.services.auth_service import resolve_user_and_create_session
    from app.services.google_oauth import GoogleUserInfo

    user = User(
        id=uuid.uuid4(),
        email="no-membership@example.com",
        display_name="No Membership",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider=AuthProvider.GOOGLE.value,
        provider_subject="google-sub-999",
        email=user.email,
    )
    db.add(identity)
    db.commit()

    google_user = GoogleUserInfo(
        sub="google-sub-999",
        email=user.email,
        name="No Membership",
        picture=None,
        hd=None,
    )

    token, error_code = resolve_user_and_create_session(db, google_user)
    assert token is None
    assert error_code == "no_membership"
