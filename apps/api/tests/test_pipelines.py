"""Tests for Pipelines API with versioning."""

import uuid
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, PipelineStage, User
from app.main import app
from app.services import session_service


@pytest.mark.asyncio
async def test_list_pipelines_authed(authed_client: AsyncClient):
    """Authenticated request to /settings/pipelines should return 200."""
    response = await authed_client.get("/settings/pipelines")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_pipeline(authed_client: AsyncClient):
    """Create a pipeline should return 201 with version=1."""
    payload = {
        "name": "Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
            {
                "slug": "contacted",
                "label": "Contacted",
                "color": "#F59E0B",
                "stage_type": "intake",
                "order": 2,
            },
            {
                "slug": "delivered",
                "label": "Delivered",
                "color": "#10B981",
                "stage_type": "terminal",
                "order": 3,
            },
        ],
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    if response.status_code != 201:
        print(f"Create response: {response.status_code} - {response.text}")
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Pipeline"
    assert data["current_version"] == 1
    assert len(data["stages"]) == 3


@pytest.mark.asyncio
async def test_update_pipeline_increments_version(authed_client: AsyncClient):
    """Updating a pipeline should increment current_version."""
    # Create first
    create_payload = {
        "name": "Version Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    initial_version = create_resp.json()["current_version"]

    # Update name only (stages unchanged)
    update_payload = {
        "name": "Version Test Pipeline Updated",
        "expected_version": initial_version,
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    if update_resp.status_code != 200:
        print(f"Update response: {update_resp.status_code} - {update_resp.text}")
    assert update_resp.status_code == 200
    assert update_resp.json()["current_version"] == initial_version + 1


@pytest.mark.asyncio
async def test_update_pipeline_version_conflict(authed_client: AsyncClient):
    """Updating with wrong expected_version should return 409."""
    # Create first
    create_payload = {
        "name": "Conflict Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]

    # Update with wrong version
    update_payload = {
        "name": "Should Fail",
        "expected_version": 999,  # Wrong version
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    assert update_resp.status_code == 409


@pytest.mark.asyncio
async def test_create_pipeline_sets_is_intake_stage(authed_client, db):
    payload = {
        "name": "Intake Stage Flags",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
            {
                "slug": "ready_to_match",
                "label": "Ready to Match",
                "color": "#F59E0B",
                "stage_type": "post_approval",
                "order": 2,
            },
            {
                "slug": "delivered",
                "label": "Delivered",
                "color": "#10B981",
                "stage_type": "post_approval",
                "order": 3,
            },
        ],
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    assert response.status_code == 201, response.text
    pipeline_id = UUID(response.json()["id"])

    stages = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline_id).all()
    stage_by_slug = {stage.slug: stage for stage in stages}

    assert stage_by_slug["new_unread"].is_intake_stage is True
    assert stage_by_slug["ready_to_match"].is_intake_stage is False
    assert stage_by_slug["delivered"].is_intake_stage is False


@pytest.mark.asyncio
async def test_intake_can_get_default_pipeline(db, test_org):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake Pipeline Reader",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=intake_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
            is_active=True,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None
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
        response = await client.get("/settings/pipelines/default")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["is_default"] is True
        assert len(payload["stages"]) > 0

    app.dependency_overrides.clear()
