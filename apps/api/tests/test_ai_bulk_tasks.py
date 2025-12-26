"""
Tests for AI bulk task creation endpoint.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Case, Membership, User
from app.main import app


def _create_case(db, org_id, user_id, stage):
    case = Case(
        id=uuid.uuid4(),
        organization_id=org_id,
        case_number=f"C{uuid.uuid4().hex[:9]}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Bulk Task Case",
        email=f"bulk-task-{uuid.uuid4().hex[:8]}@example.com",
    )
    db.add(case)
    db.flush()
    return case


@pytest.mark.asyncio
async def test_bulk_task_creation_allows_case_manager(
    db, test_org, default_stage
):
    user = User(
        id=uuid.uuid4(),
        email=f"case-manager-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Case Manager",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER,
    )
    db.add(membership)
    db.flush()

    case = _create_case(db, test_org.id, user.id, default_stage)

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        token_version=user.token_version,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token},
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as client:
            response = await client.post(
                "/ai/create-bulk-tasks",
                json={
                    "request_id": str(uuid.uuid4()),
                    "case_id": str(case.id),
                    "tasks": [
                        {
                            "title": "Follow up with client",
                            "task_type": "follow_up",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["created"]) == 1
    finally:
        app.dependency_overrides.clear()
