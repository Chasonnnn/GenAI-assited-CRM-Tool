from contextlib import asynccontextmanager
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User, UserPermissionOverride
from app.main import app
from app.services import session_service


@asynccontextmanager
async def _authed_client_for_user(db, org_id, user, role: Role):
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


def _create_user_with_membership(db, org_id, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"{role.value}-user",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=role.value,
        )
    )
    db.flush()
    return user


@pytest.mark.asyncio
async def test_signature_update_honors_manage_org_permission_for_non_admin(db, test_org):
    user = _create_user_with_membership(db, test_org.id, Role.CASE_MANAGER)
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=user.id,
            permission="manage_org",
            override_type="grant",
        )
    )
    db.flush()

    async with _authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        response = await client.patch(
            "/settings/organization/signature",
            json={"signature_company_name": "Permitted Name"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["signature_company_name"] == "Permitted Name"


@pytest.mark.asyncio
async def test_import_pending_honors_manage_org_permission_for_non_admin(db, test_org):
    user = _create_user_with_membership(db, test_org.id, Role.CASE_MANAGER)
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=user.id,
            permission="manage_org",
            override_type="grant",
        )
    )
    db.flush()

    async with _authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        response = await client.get("/surrogates/import/pending")

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
