from __future__ import annotations

from contextlib import asynccontextmanager
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.main import app
from app.services import session_service


@asynccontextmanager
async def role_client(db, org, role: Role):
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
        organization_id=org.id,
        role=role,
    )
    db.add(membership)
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org.id,
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
        yield client, user

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_surrogates_list_owner_filter_requires_admin(db, test_org):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        response = await client.get("/surrogates", params={"owner_id": str(other_user.id)})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_surrogate_created_dates_owner_filter_requires_admin(db, test_org):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        response = await client.get(
            "/surrogates/created-dates",
            params={"owner_id": str(other_user.id)},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_surrogates_list_owner_filter_allows_admin(db, test_org):
    async with role_client(db, test_org, Role.ADMIN) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.CASE_MANAGER,
            )
        )
        db.flush()

        response = await client.get("/surrogates", params={"owner_id": str(other_user.id)})
        assert response.status_code == 200
