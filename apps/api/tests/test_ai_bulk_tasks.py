"""
Tests for AI bulk task creation endpoint.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Case, IntendedParent, Match, Membership, Task, User
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


def _create_intended_parent(db, org_id):
    ip = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        full_name="Bulk Task IP",
        email=f"bulk-task-ip-{uuid.uuid4().hex[:8]}@example.com",
    )
    db.add(ip)
    db.flush()
    return ip


def _create_match(db, org_id, user_id, stage):
    case = _create_case(db, org_id, user_id, stage)
    ip = _create_intended_parent(db, org_id)
    match = Match(
        id=uuid.uuid4(),
        organization_id=org_id,
        case_id=case.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=user_id,
    )
    db.add(match)
    db.flush()
    return match


@pytest.fixture
def case_manager_user(db, test_org):
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
    return user


@pytest.fixture
async def case_manager_client(db, test_org, case_manager_user):
    token = create_session_token(
        user_id=case_manager_user.id,
        org_id=test_org.id,
        role=Role.CASE_MANAGER.value,
        token_version=case_manager_user.token_version,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_task_creation_allows_case_manager(
    case_manager_client: AsyncClient,
    case_manager_user,
    test_org,
    default_stage,
    db,
):
    case = _create_case(db, test_org.id, case_manager_user.id, default_stage)

    response = await case_manager_client.post(
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


@pytest.mark.asyncio
async def test_bulk_task_creation_intended_parent_links_ip(
    case_manager_client: AsyncClient,
    case_manager_user,
    test_org,
    db,
):
    ip = _create_intended_parent(db, test_org.id)

    response = await case_manager_client.post(
        "/ai/create-bulk-tasks",
        json={
            "request_id": str(uuid.uuid4()),
            "intended_parent_id": str(ip.id),
            "tasks": [
                {
                    "title": "Call intended parent",
                    "task_type": "contact",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    task_id = data["created"][0]["task_id"]

    created_task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    assert created_task is not None
    assert created_task.intended_parent_id == ip.id
    assert created_task.case_id is None


@pytest.mark.asyncio
async def test_bulk_task_creation_match_links_case_and_ip(
    case_manager_client: AsyncClient,
    case_manager_user,
    test_org,
    default_stage,
    db,
):
    match = _create_match(db, test_org.id, case_manager_user.id, default_stage)

    response = await case_manager_client.post(
        "/ai/create-bulk-tasks",
        json={
            "request_id": str(uuid.uuid4()),
            "match_id": str(match.id),
            "tasks": [
                {
                    "title": "Coordinate next steps",
                    "task_type": "follow_up",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    task_id = data["created"][0]["task_id"]

    created_task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    assert created_task is not None
    assert created_task.case_id == match.case_id
    assert created_task.intended_parent_id == match.intended_parent_id
