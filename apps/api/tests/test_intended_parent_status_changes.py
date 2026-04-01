from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import IntendedParentStatusHistory, Membership, StatusChangeRequest, User
from app.main import app
from app.services import pipeline_service, session_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type="intended_parent",
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, slug)
    assert stage is not None
    return stage


@asynccontextmanager
async def _client_for_role(db, org_id: UUID, role: Role):
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
            role=role,
            is_active=True,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org_id, token=token, request=None)

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
            yield user, client
    finally:
        app.dependency_overrides.clear()


async def _create_intended_parent(client: AsyncClient) -> dict:
    response = await client.post(
        "/intended-parents",
        json={
            "full_name": "IP Status Change Test",
            "email": f"ip-status-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_intended_parent_status_regression_creates_pending_request_for_non_admin(db, test_org):
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")
    new_stage = _get_stage(db, test_org.id, "new")

    async with _client_for_role(db, test_org.id, Role.CASE_MANAGER) as (_, client):
        intended_parent = await _create_intended_parent(client)

        response = await client.patch(
            f"/intended-parents/{intended_parent['id']}/status",
            json={"stage_id": str(ready_stage.id)},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "applied"

        intended_parent_id = UUID(intended_parent["id"])
        history = (
            db.query(IntendedParentStatusHistory)
            .filter(IntendedParentStatusHistory.intended_parent_id == intended_parent_id)
            .order_by(IntendedParentStatusHistory.recorded_at.desc())
            .first()
        )
        assert history is not None
        history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()

        regression = await client.patch(
            f"/intended-parents/{intended_parent['id']}/status",
            json={"stage_id": str(new_stage.id), "reason": "Requested correction"},
        )
        assert regression.status_code == 200, regression.text
        assert regression.json()["status"] == "pending_approval"

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "intended_parent",
            StatusChangeRequest.entity_id == intended_parent_id,
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    assert request is not None
    assert request.target_stage_id == new_stage.id


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_intended_parent_status_regression_self_approves_for_admin_or_developer(
    db, test_org, role
):
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")
    new_stage = _get_stage(db, test_org.id, "new")

    async with _client_for_role(db, test_org.id, role) as (user, client):
        intended_parent = await _create_intended_parent(client)

        response = await client.patch(
            f"/intended-parents/{intended_parent['id']}/status",
            json={"stage_id": str(ready_stage.id)},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "applied"

        intended_parent_id = UUID(intended_parent["id"])
        history = (
            db.query(IntendedParentStatusHistory)
            .filter(IntendedParentStatusHistory.intended_parent_id == intended_parent_id)
            .order_by(IntendedParentStatusHistory.recorded_at.desc())
            .first()
        )
        assert history is not None
        history.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()

        regression = await client.patch(
            f"/intended-parents/{intended_parent['id']}/status",
            json={"stage_id": str(new_stage.id), "reason": "Requested correction"},
        )
        assert regression.status_code == 200, regression.text
        assert regression.json()["status"] == "applied"
        assert regression.json()["request_id"] is None

    request_count = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "intended_parent",
            StatusChangeRequest.entity_id == intended_parent_id,
            StatusChangeRequest.status == "pending",
        )
        .count()
    )
    assert request_count == 0

    regression_history = (
        db.query(IntendedParentStatusHistory)
        .filter(
            IntendedParentStatusHistory.intended_parent_id == intended_parent_id,
            IntendedParentStatusHistory.new_stage_id == new_stage.id,
        )
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )
    assert regression_history is not None
    assert regression_history.request_id is None
    assert regression_history.changed_by_user_id == user.id
    assert regression_history.approved_by_user_id == user.id
    assert regression_history.approved_at is not None
