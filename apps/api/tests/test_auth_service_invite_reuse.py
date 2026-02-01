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
