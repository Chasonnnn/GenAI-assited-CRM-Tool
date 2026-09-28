"""Intended parent stage changes follow the stage-change permission and pipeline rules."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.db.enums import Role
from app.db.models import (
    IntendedParent,
    IntendedParentStatusHistory,
    StatusChangeRequest,
    Surrogate,
    User,
)
from app.db.models.record_access import RoleRecordScope
from app.services import intended_parent_status_service, ip_service, pipeline_service
from tests.test_intended_parent_status_changes import (
    _create_intended_parent,
    _get_stage,
    _other_org_ip_stage,
)
from tests.test_match_cancel_request import _create_intended_parent as _create_ready_ip
from tests.test_match_cancel_request import _create_surrogate
from tests.test_match_cases import _case
from tests.test_match_lifecycle_characterization import _client_for, _match_row, _other_org
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


def _latest_history(db, ip_id: str) -> IntendedParentStatusHistory:
    return (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == UUID(ip_id))
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )


def _require_reason_on_enter(db, stage) -> None:
    stage.semantics = {**(stage.semantics or {}), "requires_reason_on_enter": True}
    db.commit()


def _limit_role_mutation(db, org_id: UUID, role: Role, stage_keys: list[str]) -> None:
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, entity_type="intended_parent"
    )
    pipeline.feature_config = {
        **(pipeline.feature_config or {}),
        "role_mutation": {
            role.value: {"stage_keys": stage_keys, "stage_types": [], "capabilities": []}
        },
    }
    db.commit()


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
async def test_stage_change_on_another_orgs_intended_parent_returns_not_found(
    db, test_org, authed_client
):
    other_org = _other_org(db)
    creator = User(
        id=uuid.uuid4(),
        email=f"other-ip-owner-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other Org Owner",
        token_version=1,
        is_active=True,
    )
    db.add(creator)
    db.flush()
    foreign_ip = ip_service.create_intended_parent(
        db,
        other_org.id,
        creator.id,
        full_name="Other Org Stage IP",
        email=f"other-org-stage-{uuid.uuid4().hex[:8]}@example.com",
    )
    foreign_stage_id = foreign_ip.stage_id
    history = _history_count(db, str(foreign_ip.id))
    targets = (
        _get_stage(db, test_org.id, "ready_to_match"),
        _get_stage(db, other_org.id, "ready_to_match"),
    )

    for target in targets:
        response = await authed_client.patch(
            f"/intended-parents/{foreign_ip.id}/status", json={"stage_id": str(target.id)}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Intended parent not found"

    assert _stage_id(db, str(foreign_ip.id)) == foreign_stage_id
    assert _history_count(db, str(foreign_ip.id)) == history


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


@pytest.mark.asyncio
async def test_stage_requiring_reason_on_enter_rejects_missing_reason(db, test_org, authed_client):
    ready = _get_stage(db, test_org.id, "ready_to_match")
    _require_reason_on_enter(db, ready)
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])
    history = _history_count(db, ip["id"])
    path = f"/intended-parents/{ip['id']}/status"

    for payload in ({}, {"reason": "   "}):
        response = await authed_client.patch(path, json={"stage_id": str(ready.id), **payload})
        assert response.status_code == 403
        assert response.json()["detail"] == f"Reason required when moving to {ready.label}"
    assert _stage_id(db, ip["id"]) == before
    assert _history_count(db, ip["id"]) == history

    applied = await authed_client.patch(
        path, json={"stage_id": str(ready.id), "reason": " Budget confirmed "}
    )
    assert applied.status_code == 200, applied.text
    assert _stage_id(db, ip["id"]) == ready.id
    assert _latest_history(db, ip["id"]).reason == "Budget confirmed"


@pytest.mark.asyncio
@pytest.mark.parametrize("allowed_keys,expected", [(["ready_to_match"], 200), (["delivered"], 403)])
async def test_pipeline_role_mutation_rule_limits_target_stages(
    db, test_org, authed_client, allowed_keys, expected
):
    ready = _get_stage(db, test_org.id, "ready_to_match")
    _limit_role_mutation(db, test_org.id, Role.CASE_MANAGER, allowed_keys)
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])

    async with _client_for(db, test_org.id, role=Role.CASE_MANAGER) as (_, client):
        response = await client.patch(
            f"/intended-parents/{ip['id']}/status", json={"stage_id": str(ready.id)}
        )

    assert response.status_code == expected, response.text
    if expected == 200:
        assert _stage_id(db, ip["id"]) == ready.id
    else:
        assert response.json()["detail"] == "Role not permitted to change intended parent stage"
        assert _stage_id(db, ip["id"]) == before


@pytest.mark.asyncio
async def test_v2_stage_scope_blocks_stage_change(db, test_org, authed_client):
    _activate_v2(db, test_org.id)
    ready = _get_stage(db, test_org.id, "ready_to_match")
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])
    db.add(
        RoleRecordScope(
            organization_id=test_org.id,
            role=Role.CASE_MANAGER.value,
            module="intended_parents",
            assignment="all",
            phase="all",
            stage_ids=[str(ready.id)],
        )
    )
    db.commit()

    async with _client_for(db, test_org.id, role=Role.CASE_MANAGER) as (user, client):
        response = await client.patch(
            f"/intended-parents/{ip['id']}/status", json={"stage_id": str(ready.id)}
        )
        assert response.status_code == 404
        with pytest.raises(ValueError, match="Record is outside your access scope"):
            intended_parent_status_service.change_status(
                db=db,
                ip=db.get(IntendedParent, UUID(ip["id"])),
                new_stage=ready,
                user_id=user.id,
                user_role=Role.CASE_MANAGER,
            )

    assert _stage_id(db, ip["id"]) == before


@pytest.mark.asyncio
async def test_v2_stage_change_requires_permission_in_service(db, test_org, authed_client):
    _activate_v2(db, test_org.id)
    _set_role_permission(db, test_org.id, Role.CASE_MANAGER, CHANGE, False)
    ready = _get_stage(db, test_org.id, "ready_to_match")
    ip = await _create_intended_parent(authed_client)
    before = _stage_id(db, ip["id"])

    async with _client_for(db, test_org.id, role=Role.CASE_MANAGER) as (user, _):
        with pytest.raises(ValueError, match="Stage change permission required"):
            intended_parent_status_service.change_status(
                db=db,
                ip=db.get(IntendedParent, UUID(ip["id"])),
                new_stage=ready,
                user_id=user.id,
                user_role=Role.CASE_MANAGER,
            )

    assert _stage_id(db, ip["id"]) == before


@pytest.mark.asyncio
async def test_match_accept_follows_intended_parent_role_mutation_rule(db, test_org, authed_client):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_ready_ip(authed_client)
    match = await _case(authed_client, ip, surrogate=surrogate)
    _limit_role_mutation(db, test_org.id, Role.DEVELOPER, ["ready_to_match"])
    surrogate_stage = db.get(Surrogate, UUID(surrogate["id"])).stage_id
    ip_stage = _stage_id(db, ip["id"])
    expected = "Role not permitted to change intended parent stage"

    read = await authed_client.get(f"/matches/{match['id']}")
    assert "accept" not in read.json()["allowed_actions"]
    assert read.json()["blocked_reasons"]["accept"] == expected
    response = await authed_client.put(f"/matches/{match['id']}/accept", json={})

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == expected
    assert _match_row(db, match["id"]).status == "under_review"
    db.expire_all()
    assert db.get(Surrogate, UUID(surrogate["id"])).stage_id == surrogate_stage
    assert _stage_id(db, ip["id"]) == ip_stage


@pytest.mark.asyncio
async def test_match_accept_allows_intended_parent_on_stage_eligible_for_matching(
    db, test_org, authed_client
):
    new = _get_stage(db, test_org.id, "new")
    semantics = dict(new.semantics or {})
    semantics["capabilities"] = {
        **semantics.get("capabilities", {}),
        "eligible_for_matching": True,
    }
    new.semantics = semantics
    db.commit()
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    assert _stage_id(db, ip["id"]) == new.id

    match = await _case(authed_client, ip, surrogate=surrogate)
    assert match["accept_eligibility_warnings"] == []
    response = await authed_client.put(f"/matches/{match['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert _stage_id(db, ip["id"]) == _get_stage(db, test_org.id, "matched").id


APPROVE = "approve_status_change_requests"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy,role,grant,revoke,expected",
    [
        (1, Role.CASE_MANAGER, (APPROVE,), (), "applied"),
        (2, Role.CASE_MANAGER, (), (), "applied"),
        (1, Role.ADMIN, (), (APPROVE,), "pending_approval"),
    ],
    ids=["v1_granted_case_manager", "v2_granted_case_manager", "v1_revoked_admin"],
)
async def test_regression_self_approval_follows_approve_permission(
    db, test_org, authed_client, policy, role, grant, revoke, expected
):
    if policy == 2:
        _activate_v2(db, test_org.id)
        _set_role_permission(db, test_org.id, Role.CASE_MANAGER, APPROVE, True)
    new = _get_stage(db, test_org.id, "new")
    ready = _get_stage(db, test_org.id, "ready_to_match")
    ip = await _create_intended_parent(authed_client)
    moved = await authed_client.patch(
        f"/intended-parents/{ip['id']}/status", json={"stage_id": str(ready.id)}
    )
    assert moved.status_code == 200, moved.text

    async with _client_for(db, test_org.id, role=role, grant=grant, revoke=revoke) as (
        user,
        client,
    ):
        response = await client.patch(
            f"/intended-parents/{ip['id']}/status",
            json={"stage_id": str(new.id), "reason": "Requested correction"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == expected
    if expected == "applied":
        assert _stage_id(db, ip["id"]) == new.id
        assert _latest_history(db, ip["id"]).approved_by_user_id == user.id
    else:
        assert _stage_id(db, ip["id"]) == ready.id
        assert response.json()["request_id"] is not None
