from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import EmailTemplate, Membership, User
from app.main import app
from app.services import session_service


def create_user_with_role(db, org_id, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"{role.value} user",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_id,
        role=role,
    )
    db.add(membership)
    db.flush()
    return user


@asynccontextmanager
async def authed_client_for_user(db, org_id, user: User, role: Role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_personal_templates_visible_only_to_owner(db, test_org):
    owner = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)
    other = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    owner_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=owner.id,
        name="Owner Personal",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=owner.id,
        is_active=True,
    )
    other_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=other.id,
        name="Other Personal",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=other.id,
        is_active=True,
    )
    org_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=admin.id,
        name="Org Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add_all([owner_template, other_template, org_template])
    db.commit()

    async with authed_client_for_user(db, test_org.id, owner, Role.CASE_MANAGER) as client:
        res = await client.get("/email-templates?scope=personal")
        assert res.status_code == 200
        ids = {item["id"] for item in res.json()}
        assert str(owner_template.id) in ids
        assert str(other_template.id) not in ids
        assert str(org_template.id) not in ids

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.get("/email-templates?scope=personal&show_all_personal=true")
        assert res.status_code == 200
        ids = {item["id"] for item in res.json()}
        assert str(owner_template.id) in ids
        assert str(other_template.id) in ids


@pytest.mark.asyncio
async def test_org_templates_exclude_platform_system_keys(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    org_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=admin.id,
        name="Org Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=False,
        system_key=None,
    )
    seeded_system_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=admin.id,
        name="Welcome New Lead",
        subject="Welcome",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=True,
        system_key="welcome_new_lead",
    )
    legacy_platform_invite = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=admin.id,
        name="Organization Invite",
        subject="Invitation to join {{org_name}} as {{role_title}}",
        body="<p>Invite</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=True,
        system_key="org_invite",
    )
    db.add_all([org_template, seeded_system_template, legacy_platform_invite])
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.get("/email-templates?scope=org")
        assert res.status_code == 200
        names = {item["name"] for item in res.json()}
        assert "Org Template" in names
        assert "Welcome New Lead" in names
        assert "Organization Invite" not in names


@pytest.mark.asyncio
async def test_copy_org_template_to_personal(db, test_org):
    user = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)

    org_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="Org Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(org_template)
    db.commit()

    async with authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        res = await client.post(
            f"/email-templates/{org_template.id}/copy",
            json={"name": "Org Template Copy"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["scope"] == "personal"
        assert data["owner_user_id"] == str(user.id)
        assert data["source_template_id"] == str(org_template.id)


@pytest.mark.asyncio
async def test_share_personal_template_creates_org_copy(db, test_org):
    user = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)

    personal_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="Personal Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=user.id,
        is_active=True,
    )
    db.add(personal_template)
    db.commit()

    async with authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        res = await client.post(
            f"/email-templates/{personal_template.id}/share",
            json={"name": "Shared Personal Template"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["scope"] == "org"
        assert data["owner_user_id"] is None
        assert data["source_template_id"] == str(personal_template.id)


@pytest.mark.asyncio
async def test_admin_cannot_share_other_users_personal_template(db, test_org):
    owner = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    personal_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=owner.id,
        name="Owner Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=owner.id,
        is_active=True,
    )
    db.add(personal_template)
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/email-templates/{personal_template.id}/share",
            json={"name": "Admin Share Attempt"},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_org_template_invalid_from_email_returns_422(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            "/email-templates",
            json={
                "name": "Welcome",
                "subject": "Hi",
                "from_email": "Not an email",
                "body": "<p>Hello</p>",
                "scope": "org",
            },
        )
        assert res.status_code == 422
        assert "from_email" in str(res.json()).lower()


@pytest.mark.asyncio
async def test_create_org_template_requires_manage_permission(db, test_org):
    user = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)

    async with authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        res = await client.post(
            "/email-templates",
            json={
                "name": "Welcome",
                "subject": "Hi",
                "from_email": None,
                "body": "<p>Hello</p>",
                "scope": "org",
            },
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_org_template_success(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            "/email-templates",
            json={
                "name": "Welcome",
                "subject": "Hi",
                "from_email": "Surrogacy Force <invites@test.com>",
                "body": "<p>Hello</p>",
                "scope": "org",
            },
        )
        assert res.status_code == 201
        payload = res.json()
        assert payload["name"] == "Welcome"
        assert payload["scope"] == "org"
        assert payload["owner_user_id"] is None
