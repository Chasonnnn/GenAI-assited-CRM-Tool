"""Tests for the dev endpoints that create invites and resolve Google sign-ins locally."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, Organization, OrgInvite, User, UserSession
from app.main import app
from app.services import session_service


def _dev_headers() -> dict[str, str]:
    return {"X-Dev-Secret": settings.DEV_SECRET.get_secret_value()}


def _create_org(db, name: str) -> Organization:
    org = Organization(id=uuid.uuid4(), name=name, slug=f"dev-invite-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    return org


async def _client_with_role(db, org: Organization, role: Role) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"dev-invite-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Dev Invite Actor",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role=role.value))
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org.id, token=token, request=None)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )


def _pending_invite(db, org: Organization, email: str, role: Role = Role.CASE_MANAGER) -> OrgInvite:
    invite = OrgInvite(
        id=uuid.uuid4(),
        organization_id=org.id,
        email=email,
        role=role.value,
        expires_at=datetime.now(UTC) + timedelta(days=3),
    )
    db.add(invite)
    db.commit()
    return invite


@pytest.fixture
def no_invite_email(monkeypatch):
    """Fail the test if anything tries to send or queue an invite email."""
    from app.services import invite_email_service

    async def _refuse(*_args, **_kwargs):
        raise AssertionError("dev invites must not send email")

    monkeypatch.setattr(invite_email_service, "send_invite_email", _refuse)


@pytest.mark.asyncio
async def test_dev_invite_creates_pending_invite_in_callers_org_without_email(
    db, test_org, no_invite_email
):
    async with await _client_with_role(db, test_org, Role.ADMIN) as client:
        response = await client.post(
            "/dev/invites",
            headers=_dev_headers(),
            json={"email": "New.Hire@Example.com", "role": "case_manager"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "new.hire@example.com"
    assert payload["role"] == "case_manager"
    assert payload["status"] == "pending"

    invite = db.get(OrgInvite, uuid.UUID(payload["id"]))
    assert invite is not None
    assert invite.organization_id == test_org.id


@pytest.mark.asyncio
async def test_dev_invite_can_start_expired(db, test_org, no_invite_email):
    expired_at = datetime.now(UTC) - timedelta(days=1)
    async with await _client_with_role(db, test_org, Role.ADMIN) as client:
        response = await client.post(
            "/dev/invites",
            headers=_dev_headers(),
            json={
                "email": "late@example.com",
                "role": "intake_specialist",
                "expires_at": expired_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_dev_invite_requires_dev_secret(db, test_org):
    async with await _client_with_role(db, test_org, Role.ADMIN) as client:
        response = await client.post(
            "/dev/invites",
            headers={"X-Dev-Secret": "wrong"},
            json={"email": "nobody@example.com", "role": "case_manager"},
        )

    assert response.status_code == 403
    assert db.query(OrgInvite).filter(OrgInvite.email == "nobody@example.com").count() == 0


@pytest.mark.asyncio
async def test_dev_invite_requires_csrf_header(db, test_org):
    client = await _client_with_role(db, test_org, Role.ADMIN)
    client.headers.pop(CSRF_HEADER)
    async with client:
        response = await client.post(
            "/dev/invites",
            headers=_dev_headers(),
            json={"email": "no-csrf@example.com", "role": "case_manager"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dev_invite_denies_case_manager(db, test_org, no_invite_email):
    async with await _client_with_role(db, test_org, Role.CASE_MANAGER) as client:
        response = await client.post(
            "/dev/invites",
            headers=_dev_headers(),
            json={"email": "blocked@example.com", "role": "case_manager"},
        )

    assert response.status_code == 403
    assert db.query(OrgInvite).filter(OrgInvite.email == "blocked@example.com").count() == 0


@pytest.mark.asyncio
async def test_dev_invite_never_writes_into_another_org(db, test_org, no_invite_email):
    other_org = _create_org(db, "Other Agency")
    async with await _client_with_role(db, other_org, Role.ADMIN) as client:
        response = await client.post(
            "/dev/invites",
            headers=_dev_headers(),
            json={"email": "elsewhere@example.com", "role": "case_manager"},
        )

    assert response.status_code == 200
    invite = db.get(OrgInvite, uuid.UUID(response.json()["id"]))
    assert invite.organization_id == other_org.id
    assert db.query(OrgInvite).filter(OrgInvite.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_dev_google_login_accepts_the_invite_with_a_verified_session(client, db, test_org):
    invite = _pending_invite(db, test_org, "invitee@example.com")

    response = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={
            "email": "Invitee@Example.com",
            "display_name": "Ivy Invitee",
            "invite_id": str(invite.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "invitee@example.com"
    assert payload["role"] == Role.CASE_MANAGER.value
    assert payload["org_id"] == str(test_org.id)

    db.refresh(invite)
    assert invite.accepted_at is not None
    user_id = uuid.UUID(payload["user_id"])
    membership = db.query(Membership).filter(Membership.user_id == user_id).one()
    assert membership.organization_id == test_org.id
    assert membership.is_active

    # Only the MFA-verified dev session remains; the callback's MFA-pending one is gone.
    assert db.query(UserSession).filter(UserSession.user_id == user_id).count() == 1
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == payload["user_id"]


@pytest.mark.asyncio
async def test_dev_google_login_signs_in_the_same_identity_again(client, db, test_org):
    invite = _pending_invite(db, test_org, "repeat@example.com")
    first = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={"email": "repeat@example.com", "invite_id": str(invite.id)},
    )
    second = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={"email": "Repeat@Example.com"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["user_id"] == first.json()["user_id"]
    user_id = uuid.UUID(first.json()["user_id"])
    assert db.query(UserSession).filter(UserSession.user_id == user_id).count() == 2


@pytest.mark.asyncio
async def test_dev_google_login_refuses_an_uninvited_email(client, db):
    response = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={"email": "stranger@example.com"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "not_invited"
    assert db.query(User).filter(User.email == "stranger@example.com").count() == 0


@pytest.mark.asyncio
async def test_dev_google_login_refuses_another_email_on_the_invite(client, db, test_org):
    invite = _pending_invite(db, test_org, "intended@example.com")

    response = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={"email": "intruder@example.com", "invite_id": str(invite.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "not_invited"
    db.refresh(invite)
    assert invite.accepted_at is None


@pytest.mark.asyncio
async def test_dev_google_login_reports_an_expired_invite(client, db, test_org):
    invite = _pending_invite(db, test_org, "expired-invitee@example.com")
    invite.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()

    response = await client.post(
        "/dev/google-login",
        headers=_dev_headers(),
        json={"email": "expired-invitee@example.com", "invite_id": str(invite.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invite_expired"


@pytest.mark.asyncio
async def test_dev_google_login_requires_dev_secret(client, db, test_org):
    invite = _pending_invite(db, test_org, "guarded@example.com")

    response = await client.post(
        "/dev/google-login",
        headers={"X-Dev-Secret": "wrong"},
        json={"email": "guarded@example.com", "invite_id": str(invite.id)},
    )

    assert response.status_code == 403
    db.refresh(invite)
    assert invite.accepted_at is None
