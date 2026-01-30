from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User, WorkflowTemplate
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
async def test_use_template_creates_personal_workflow(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    template = WorkflowTemplate(
        id=uuid.uuid4(),
        name="Template One",
        description="Template description",
        icon="template",
        category="general",
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Hello"}],
        is_global=False,
        organization_id=test_org.id,
        created_by_user_id=admin.id,
    )
    db.add(template)
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Personal Workflow",
                "description": "From template",
                "is_enabled": False,
                "scope": "personal",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "personal"
        assert data["owner_user_id"] == str(admin.id)
