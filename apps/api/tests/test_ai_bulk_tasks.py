"""
Tests for AI bulk task creation endpoint.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Surrogate, IntendedParent, Match, Membership, Task, User
from app.main import app
from app.utils.normalization import normalize_email


def _create_case(db, org_id, user_id, stage):
    email = f"bulk-task-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    case = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Bulk Task Case",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(case)
    db.flush()
    return case


def _create_intended_parent(db, org_id):
    email = f"bulk-task-ip-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    ip = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"I{uuid.uuid4().int % 90000 + 10000:05d}",
        full_name="Bulk Task IP",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
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
        match_number=f"M{uuid.uuid4().int % 90000 + 10000:05d}",
        surrogate_id=case.id,
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
        mfa_verified=True,
        mfa_required=True,
    )
    from app.services import session_service

    session_service.create_session(
        db=db,
        user_id=case_manager_user.id,
        org_id=test_org.id,
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
            "surrogate_id": str(case.id),
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
    assert created_task.surrogate_id is None


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
    assert created_task.surrogate_id == match.surrogate_id
    assert created_task.intended_parent_id == match.intended_parent_id
