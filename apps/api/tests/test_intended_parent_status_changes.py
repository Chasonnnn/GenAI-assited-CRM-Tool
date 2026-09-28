import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import AuditEventType, Role
from app.db.models import (
    AuditLog,
    IntendedParentStatusHistory,
    Membership,
    StatusChangeRequest,
    User,
)
from app.main import app
from app.services import audit_service, pipeline_service, session_service


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


def _fail_status_change_audit(monkeypatch) -> None:
    log_event = audit_service.log_event

    def fail(*args, **kwargs):
        if kwargs.get("event_type") == AuditEventType.INTENDED_PARENT_STATUS_CHANGED:
            raise RuntimeError("Synthetic audit failure")
        return log_event(*args, **kwargs)

    monkeypatch.setattr(audit_service, "log_event", fail)


async def _apply_then_age_last_change(db, client: AsyncClient, ip_id: str, stage_id) -> None:
    response = await client.patch(
        f"/intended-parents/{ip_id}/status",
        json={"stage_id": str(stage_id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"
    history = (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == UUID(ip_id))
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )
    assert history is not None
    history.recorded_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()


@pytest.mark.asyncio
async def test_intended_parent_status_regression_creates_pending_request_for_non_admin(
    db, test_org
):
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
        history.recorded_at = datetime.now(UTC) - timedelta(minutes=10)
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
        history.recorded_at = datetime.now(UTC) - timedelta(minutes=10)
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


@pytest.mark.asyncio
async def test_intended_parent_stage_change_does_not_commit_when_audit_fails(
    db, test_org, monkeypatch
):
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")

    async with _client_for_role(db, test_org.id, Role.ADMIN) as (_, client):
        intended_parent = await _create_intended_parent(client)
        commits: list[str] = []
        monkeypatch.setattr(db, "commit", lambda: commits.append("commit"))
        _fail_status_change_audit(monkeypatch)

        with pytest.raises(RuntimeError, match="Synthetic audit failure"):
            await client.patch(
                f"/intended-parents/{intended_parent['id']}/status",
                json={"stage_id": str(ready_stage.id)},
            )

    assert commits == []


@pytest.mark.asyncio
async def test_intended_parent_stage_change_request_does_not_commit_when_audit_fails(
    db, test_org, monkeypatch
):
    new_stage = _get_stage(db, test_org.id, "new")
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")

    async with _client_for_role(db, test_org.id, Role.CASE_MANAGER) as (_, client):
        intended_parent = await _create_intended_parent(client)
        await _apply_then_age_last_change(db, client, intended_parent["id"], ready_stage.id)
        commits: list[str] = []
        monkeypatch.setattr(db, "commit", lambda: commits.append("commit"))
        _fail_status_change_audit(monkeypatch)

        with pytest.raises(RuntimeError, match="Synthetic audit failure"):
            await client.patch(
                f"/intended-parents/{intended_parent['id']}/status",
                json={"stage_id": str(new_stage.id), "reason": "Requested correction"},
            )

    assert commits == []


@pytest.mark.asyncio
async def test_intended_parent_stage_change_request_audit_records_request(db, test_org):
    new_stage = _get_stage(db, test_org.id, "new")
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")

    async with _client_for_role(db, test_org.id, Role.CASE_MANAGER) as (user, client):
        intended_parent = await _create_intended_parent(client)
        await _apply_then_age_last_change(db, client, intended_parent["id"], ready_stage.id)

        response = await client.patch(
            f"/intended-parents/{intended_parent['id']}/status",
            json={"stage_id": str(new_stage.id), "reason": "Requested correction"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "pending_approval"
        request_id = response.json()["request_id"]

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == AuditEventType.INTENDED_PARENT_STATUS_CHANGED.value,
            AuditLog.target_id == UUID(intended_parent["id"]),
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.actor_user_id == user.id
    assert audit.details == {
        "from_status": "ready_to_match",
        "requested_stage_id": str(new_stage.id),
        "requested_stage_key": "new",
        "result": "pending_approval",
        "request_id": request_id,
    }
