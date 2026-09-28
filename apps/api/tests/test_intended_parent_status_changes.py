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
    IntendedParent,
    IntendedParentStatusHistory,
    Membership,
    Organization,
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


async def _create_pending_ip_request(
    db, client: AsyncClient, org_id: UUID, requester_id: UUID, target_stage_id: UUID
) -> tuple[IntendedParent, StatusChangeRequest]:
    ready_stage = _get_stage(db, org_id, "ready_to_match")
    created = await _create_intended_parent(client)
    intended_parent = db.get(IntendedParent, UUID(created["id"]))
    intended_parent.stage_id = ready_stage.id
    intended_parent.status = ready_stage.stage_key
    now = datetime.now(UTC)
    status_request = StatusChangeRequest(
        organization_id=org_id,
        entity_type="intended_parent",
        entity_id=intended_parent.id,
        target_stage_id=target_stage_id,
        effective_at=now,
        reason="Requested correction",
        requested_by_user_id=requester_id,
        requested_at=now,
        status="pending",
    )
    db.add(status_request)
    db.commit()
    return intended_parent, status_request


def _assert_request_not_applied(db, intended_parent_id: UUID, request_id: UUID, stage_id: UUID):
    db.expire_all()
    assert db.get(StatusChangeRequest, request_id).status == "pending"
    assert db.get(IntendedParent, intended_parent_id).stage_id == stage_id
    assert (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.request_id == request_id)
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_intended_parent_request_approval_applies_target_stage(
    db, test_org, test_user, authed_client
):
    new_stage = _get_stage(db, test_org.id, "new")
    intended_parent, status_request = await _create_pending_ip_request(
        db, authed_client, test_org.id, test_user.id, new_stage.id
    )

    response = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    db.expire_all()
    assert db.get(IntendedParent, intended_parent.id).stage_id == new_stage.id
    history = (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.request_id == status_request.id)
        .one()
    )
    assert history.new_stage_id == new_stage.id
    assert history.approved_by_user_id == test_user.id


@pytest.mark.asyncio
async def test_archived_intended_parent_request_cannot_be_approved(
    db, test_org, test_user, authed_client
):
    new_stage = _get_stage(db, test_org.id, "new")
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")
    intended_parent, status_request = await _create_pending_ip_request(
        db, authed_client, test_org.id, test_user.id, new_stage.id
    )
    intended_parent.is_archived = True
    intended_parent.archived_at = datetime.now(UTC)
    db.commit()

    response = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Cannot approve a stage change for an archived intended parent"
    )
    _assert_request_not_applied(db, intended_parent.id, status_request.id, ready_stage.id)


@pytest.mark.asyncio
async def test_intended_parent_request_for_current_stage_cannot_be_approved(
    db, test_org, test_user, authed_client
):
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")
    intended_parent, status_request = await _create_pending_ip_request(
        db, authed_client, test_org.id, test_user.id, ready_stage.id
    )

    response = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == "Intended parent is already in the requested target stage"
    _assert_request_not_applied(db, intended_parent.id, status_request.id, ready_stage.id)


def _inactive_ip_stage(db, org_id: UUID, user_id: UUID):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, user_id, entity_type="intended_parent"
    )
    stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="secondary_review",
        label="Secondary Review",
        color="#475569",
        stage_type="intake",
        user_id=user_id,
    )
    stage.is_active = False
    stage.deleted_at = datetime.now(UTC)
    db.flush()
    return stage


def _surrogate_stage(db, org_id: UUID, user_id: UUID):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, user_id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new_unread")
    assert stage is not None
    return stage


def _other_org_ip_stage(db, org_id: UUID, user_id: UUID):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other IP Org",
        slug=f"other-ip-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    return _get_stage(db, other_org.id, "new")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target_stage_factory",
    [_inactive_ip_stage, _surrogate_stage, _other_org_ip_stage],
    ids=["inactive", "surrogate_pipeline", "other_org"],
)
async def test_intended_parent_request_approval_rejects_invalid_target_stage(
    db, test_org, test_user, authed_client, target_stage_factory
):
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")
    target_stage = target_stage_factory(db, test_org.id, test_user.id)
    intended_parent, status_request = await _create_pending_ip_request(
        db, authed_client, test_org.id, test_user.id, target_stage.id
    )

    response = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == "Target stage not found"
    _assert_request_not_applied(db, intended_parent.id, status_request.id, ready_stage.id)
