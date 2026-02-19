from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, RolePermission, User
from app.main import app
from app.services import session_service


def _availability_payload() -> dict:
    return {
        "rules": [
            {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"},
            {"day_of_week": 1, "start_time": "09:00", "end_time": "17:00"},
        ],
        "timezone": "America/Los_Angeles",
    }


async def _client_with_role(db, test_org, role: Role) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"appt-rbac-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Appointments RBAC User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=role.value,
    )
    db.add(membership)
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

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


@pytest.mark.asyncio
async def test_intake_can_update_appointment_availability(db, test_org):
    client = await _client_with_role(db, test_org, Role.INTAKE_SPECIALIST)
    async with client:
        response = await client.put("/appointments/availability", json=_availability_payload())
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_case_manager_can_update_appointment_availability(db, test_org):
    client = await _client_with_role(db, test_org, Role.CASE_MANAGER)
    async with client:
        response = await client.put("/appointments/availability", json=_availability_payload())
        assert response.status_code == 200, response.text

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_update_appointment_availability(db, test_org):
    client = await _client_with_role(db, test_org, Role.ADMIN)
    async with client:
        response = await client.put("/appointments/availability", json=_availability_payload())
        assert response.status_code == 200, response.text

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intake_with_explicit_role_revoke_cannot_update_availability(db, test_org):
    role_permission = RolePermission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        permission="manage_appointments",
        is_granted=False,
    )
    db.add(role_permission)
    db.commit()

    client = await _client_with_role(db, test_org, Role.INTAKE_SPECIALIST)
    async with client:
        response = await client.put("/appointments/availability", json=_availability_payload())
        assert response.status_code == 403, response.text

    app.dependency_overrides.clear()
