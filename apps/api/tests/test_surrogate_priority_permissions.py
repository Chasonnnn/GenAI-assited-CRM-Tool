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


def _create_user_with_membership(db, org_id, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"{role.value} user",
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
            is_active=True,
        )
    )
    db.flush()
    return user


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

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_priority_toggle_allowed_with_view_access_even_without_edit(
    db, test_org, authed_client
):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Priority Toggle Lead",
            "email": f"priority-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    case_manager = _create_user_with_membership(db, test_org.id, Role.CASE_MANAGER)
    db.add(
        UserPermissionOverride(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            user_id=case_manager.id,
            permission="edit_surrogates",
            override_type="revoke",
        )
    )
    db.flush()

    async with _authed_client_for_user(db, test_org.id, case_manager, Role.CASE_MANAGER) as client:
        mark_res = await client.patch(
            f"/surrogates/{surrogate_id}",
            json={"is_priority": True},
        )
        assert mark_res.status_code == 200, mark_res.text
        assert mark_res.json()["is_priority"] is True

        unmark_res = await client.patch(
            f"/surrogates/{surrogate_id}",
            json={"is_priority": False},
        )
        assert unmark_res.status_code == 200, unmark_res.text
        assert unmark_res.json()["is_priority"] is False


@pytest.mark.asyncio
async def test_non_priority_update_still_requires_edit_permission(db, test_org, authed_client):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Permission Guard Lead",
            "email": f"priority-guard-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    case_manager = _create_user_with_membership(db, test_org.id, Role.CASE_MANAGER)
    db.add(
        UserPermissionOverride(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            user_id=case_manager.id,
            permission="edit_surrogates",
            override_type="revoke",
        )
    )
    db.flush()

    async with _authed_client_for_user(db, test_org.id, case_manager, Role.CASE_MANAGER) as client:
        update_res = await client.patch(
            f"/surrogates/{surrogate_id}",
            json={"full_name": "Should Be Denied"},
        )
        assert update_res.status_code == 403, update_res.text
        assert "edit_surrogates" in update_res.text
