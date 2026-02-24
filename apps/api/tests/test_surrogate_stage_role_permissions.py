import uuid
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.main import app
from app.services import pipeline_service, session_service


def _get_stage_id(db, org_id: UUID, slug: str) -> UUID:
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage.id


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


async def _create_surrogate(client: AsyncClient, name_prefix: str) -> str:
    email_prefix = name_prefix.lower().replace(" ", "-")
    response = await client.post(
        "/surrogates",
        json={
            "full_name": f"{name_prefix} {uuid.uuid4().hex[:6]}",
            "email": f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_case_manager_can_read_default_pipeline_without_manage_permission(db, test_org):
    async with _client_for_role(db, test_org.id, Role.CASE_MANAGER) as (_, client):
        response = await client.get("/settings/pipelines/default")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["is_default"] is True
        assert any(stage["stage_type"] == "post_approval" for stage in payload["stages"])


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_slug", ["lost", "disqualified"])
async def test_case_manager_can_change_from_post_approval_to_terminal(db, test_org, terminal_slug):
    ready_to_match_stage_id = _get_stage_id(db, test_org.id, "ready_to_match")
    terminal_stage_id = _get_stage_id(db, test_org.id, terminal_slug)

    async with _client_for_role(db, test_org.id, Role.CASE_MANAGER) as (_, client):
        surrogate_id = await _create_surrogate(client, "Case Manager Stage")

        to_ready = await client.patch(
            f"/surrogates/{surrogate_id}/status",
            json={"stage_id": str(ready_to_match_stage_id)},
        )
        assert to_ready.status_code == 200, to_ready.text
        assert to_ready.json()["status"] == "applied"

        to_terminal = await client.patch(
            f"/surrogates/{surrogate_id}/status",
            json={"stage_id": str(terminal_stage_id)},
        )
        assert to_terminal.status_code == 200, to_terminal.text
        assert to_terminal.json()["status"] == "applied"

        detail = await client.get(f"/surrogates/{surrogate_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["stage_id"] == str(terminal_stage_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_slug", ["lost", "disqualified"])
async def test_intake_can_change_to_terminal_stages(db, test_org, terminal_slug):
    terminal_stage_id = _get_stage_id(db, test_org.id, terminal_slug)

    async with _client_for_role(db, test_org.id, Role.INTAKE_SPECIALIST) as (_, client):
        surrogate_id = await _create_surrogate(client, "Intake Stage")

        to_terminal = await client.patch(
            f"/surrogates/{surrogate_id}/status",
            json={"stage_id": str(terminal_stage_id)},
        )
        assert to_terminal.status_code == 200, to_terminal.text
        assert to_terminal.json()["status"] == "applied"

        detail = await client.get(f"/surrogates/{surrogate_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["stage_id"] == str(terminal_stage_id)


@pytest.mark.asyncio
async def test_intake_can_follow_after_approving_case(db, test_org):
    approved_stage_id = _get_stage_id(db, test_org.id, "approved")

    async with _client_for_role(db, test_org.id, Role.INTAKE_SPECIALIST) as (_, client):
        surrogate_id = await _create_surrogate(client, "Intake Follow")

        to_approved = await client.patch(
            f"/surrogates/{surrogate_id}/status",
            json={"stage_id": str(approved_stage_id)},
        )
        assert to_approved.status_code == 200, to_approved.text
        assert to_approved.json()["status"] == "applied"

        detail = await client.get(f"/surrogates/{surrogate_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == surrogate_id

        listed = await client.get("/surrogates", params={"per_page": 100})
        assert listed.status_code == 200, listed.text
        assert any(item["id"] == surrogate_id for item in listed.json()["items"])

        updated_name = "Intake Follow Updated"
        updated = await client.patch(
            f"/surrogates/{surrogate_id}",
            json={"full_name": updated_name},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["full_name"] == updated_name
