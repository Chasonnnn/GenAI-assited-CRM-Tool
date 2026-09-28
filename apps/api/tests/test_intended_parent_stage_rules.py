"""Intended parent stage changes follow the stage-change permission and pipeline rules."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.db.enums import Role
from app.db.models import IntendedParent, IntendedParentStatusHistory, StatusChangeRequest, User
from app.services import ip_service
from tests.test_intended_parent_status_changes import (
    _create_intended_parent,
    _get_stage,
    _other_org_ip_stage,
)
from tests.test_match_lifecycle_characterization import _client_for, _other_org
from tests.test_match_permissions_v2_characterization import _activate_v2, _set_role_permission

CHANGE = "change_intended_parent_status"
EDIT = "edit_intended_parents"


def _stage_id(db, ip_id: str) -> UUID:
    db.expire_all()
    return db.get(IntendedParent, UUID(ip_id)).stage_id


def _history_count(db, ip_id: str) -> int:
    return (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == UUID(ip_id))
        .count()
    )


def _pending_request(db, org_id: UUID, ip_id: UUID, requester_id: UUID, stage_id: UUID):
    now = datetime.now(UTC)
    request = StatusChangeRequest(
        organization_id=org_id,
        entity_type="intended_parent",
        entity_id=ip_id,
        target_stage_id=stage_id,
        effective_at=now,
        reason="Requested correction",
        requested_by_user_id=requester_id,
        requested_at=now,
        status="pending",
    )
    db.add(request)
    db.commit()
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_stage_change_requires_change_status_permission(db, test_org, authed_client, policy):
    if policy == 2:
        _activate_v2(db, test_org.id)
        _set_role_permission(db, test_org.id, Role.CASE_MANAGER, CHANGE, False)
    ready = _get_stage(db, test_org.id, "ready_to_match")
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])

    async with _client_for(
        db, test_org.id, role=Role.CASE_MANAGER, revoke=(CHANGE,) if policy == 1 else ()
    ) as (_, client):
        response = await client.patch(
            f"/intended-parents/{ip['id']}/status", json={"stage_id": str(ready.id)}
        )

    assert response.status_code == 403
    assert response.json()["detail"] == f"Missing permission: {CHANGE}"
    assert _stage_id(db, ip["id"]) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_stage_change_does_not_require_edit_permission(db, test_org, authed_client, policy):
    if policy == 2:
        _activate_v2(db, test_org.id)
        _set_role_permission(db, test_org.id, Role.CASE_MANAGER, EDIT, False)
    ready = _get_stage(db, test_org.id, "ready_to_match")
    ip = await _create_intended_parent(authed_client)

    async with _client_for(
        db, test_org.id, role=Role.CASE_MANAGER, revoke=(EDIT,) if policy == 1 else ()
    ) as (_, client):
        response = await client.patch(
            f"/intended-parents/{ip['id']}/status", json={"stage_id": str(ready.id)}
        )

    assert response.status_code == 200, response.text
    assert _stage_id(db, ip["id"]) == ready.id


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked,expected", [(CHANGE, 403), (EDIT, 200)])
async def test_cancel_own_request_requires_change_status_permission(
    db, test_org, authed_client, revoked, expected
):
    new = _get_stage(db, test_org.id, "new")
    ip = await _create_intended_parent(authed_client)

    async with _client_for(db, test_org.id, role=Role.CASE_MANAGER, revoke=(revoked,)) as (
        user,
        client,
    ):
        request = _pending_request(db, test_org.id, UUID(ip["id"]), user.id, new.id)
        response = await client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == expected, response.text
    db.expire_all()
    status = db.get(StatusChangeRequest, request.id).status
    assert status == ("cancelled" if expected == 200 else "pending")


@pytest.mark.asyncio
async def test_stage_change_rejects_stage_from_another_org(db, test_org, test_user, authed_client):
    foreign_stage = _other_org_ip_stage(db, test_org.id, test_user.id)
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])
    history = _history_count(db, ip["id"])

    response = await authed_client.patch(
        f"/intended-parents/{ip['id']}/status", json={"stage_id": str(foreign_stage.id)}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Target stage not found"
    assert _stage_id(db, ip["id"]) == before
    assert _history_count(db, ip["id"]) == history


@pytest.mark.asyncio
async def test_approving_another_orgs_ip_request_returns_not_found(db, authed_client):
    other_org = _other_org(db)
    requester = User(
        id=uuid.uuid4(),
        email=f"other-ip-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other Org Requester",
        token_version=1,
        is_active=True,
    )
    db.add(requester)
    db.flush()
    foreign_ip = ip_service.create_intended_parent(
        db,
        other_org.id,
        requester.id,
        full_name="Other Org IP",
        email=f"other-org-ip-{uuid.uuid4().hex[:8]}@example.com",
    )
    ready = _get_stage(db, other_org.id, "ready_to_match")
    request = _pending_request(db, other_org.id, foreign_ip.id, requester.id, ready.id)

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 404
    db.expire_all()
    assert db.get(StatusChangeRequest, request.id).status == "pending"
    assert db.get(IntendedParent, foreign_ip.id).stage_id != ready.id
