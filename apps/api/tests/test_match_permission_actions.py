"""Step 7 action contract, permission resolution, and transport denial parity."""

from datetime import UTC, datetime

import pytest

from app.db.enums import Role
from app.db.models import Match, RolePermission, StatusChangeRequest
from tests.match_fixtures import seed_surrogate_match
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _case
from tests.test_match_lifecycle_characterization import _client_for, _match_row, _other_org
from tests.test_match_permissions_v2_characterization import _activate_v2, _set_role_permission

ACTIONS = {
    "accept": ("under_review", "PUT", "accept", {}, "decide_matches"),
    "decline": ("under_review", "PUT", "decline", {"reason": "Not a fit"}, "decide_matches"),
    "request_cancel": ("accepted", "POST", "cancel-request", {"reason": "Ended"}, "close_matches"),
    "complete": ("accepted", "PUT", "complete", {"outcome": "Finished"}, "close_matches"),
    "withdraw_cancel": ("cancellation_pending", "POST", "cancel", None, "close_matches"),
}


async def _fixture(client, db, user_id, status):
    row = seed_surrogate_match(db, client)
    row.status = status
    party = row.surrogate
    party.owner_type, party.owner_id = "user", user_id
    request = None
    if status == "cancellation_pending":
        request = StatusChangeRequest(
            organization_id=row.organization_id,
            entity_type="match",
            entity_id=row.id,
            target_status="cancelled",
            effective_at=datetime.now(UTC),
            reason="Ended",
            requested_by_user_id=user_id,
            status="pending",
        )
        db.add(request)
    db.commit()
    return row, request


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_allowed_actions_by_role_status_and_version(
    authed_client, db, test_auth, version, subtests
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
    for role in list(Role):
        with subtests.test(role=repr(role)):
            async with _client_for(db, test_auth.org.id, role=role) as (user, client):
                for status in (
                    "under_review",
                    "accepted",
                    "cancellation_pending",
                    "declined",
                    "cancelled",
                    "completed",
                ):
                    with subtests.test(status=status):
                        match, request = await _fixture(authed_client, db, user.id, status)
                        response = await client.get(f"/matches/{match.id}")
                        if role == Role.INTAKE_SPECIALIST or (
                            version == 1 and role == Role.OPERATIONS
                        ):
                            assert response.status_code == 403
                            continue
                        assert response.status_code == 200, response.text
                        body = response.json()
                        applicable = {
                            action for action, spec in ACTIONS.items() if spec[0] == status
                        }
                        allowed = applicable if role != Role.OPERATIONS else set()
                        assert set(body["allowed_actions"]) == allowed
                        assert set(body["blocked_reasons"]) == applicable - allowed
                        for action in applicable - allowed:
                            assert (
                                body["blocked_reasons"][action]
                                == f"Missing permission: {ACTIONS[action][4]}"
                            )
                        assert body["status"] == status
                        assert body["pending_cancellation_request_id"] == (
                            str(request.id) if request else None
                        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_each_action_permission_is_enforced_and_matches_preview(
    authed_client, db, test_auth, version, subtests
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
    for action in ACTIONS:
        for allowed in [False, True]:
            with subtests.test(action=repr(action), allowed=repr(allowed)):
                db.query(RolePermission).filter_by(organization_id=test_auth.org.id).delete()
                db.flush()
                status, method, suffix, body, permission = ACTIONS[action]
                if version == 2:
                    _set_role_permission(
                        db, test_auth.org.id, Role.CASE_MANAGER, permission, allowed
                    )
                    _set_role_permission(
                        db, test_auth.org.id, Role.CASE_MANAGER, "propose_matches", not allowed
                    )
                async with _client_for(
                    db,
                    test_auth.org.id,
                    role=Role.CASE_MANAGER,
                    revoke=("propose_matches",) if version == 1 and not allowed else (),
                ) as (user, client):
                    match, request = await _fixture(authed_client, db, user.id, status)
                    read = await client.get(f"/matches/{match.id}")
                    assert read.status_code == 200, read.text
                    assert (action in read.json()["allowed_actions"]) is allowed
                    path = (
                        f"/status-change-requests/{request.id}/cancel"
                        if request
                        else f"/matches/{match.id}/{suffix}"
                    )
                    result = await client.request(
                        method, path, **({"json": body} if body is not None else {})
                    )
                    assert result.status_code == (200 if allowed else 403), result.text
                    if not allowed:
                        assert (
                            result.json()["detail"]
                            == read.json()["blocked_reasons"][action]
                            == f"Missing permission: {permission}"
                        )
                        assert _match_row(db, match.id).status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_every_action_is_org_scoped(authed_client, db, test_auth, version, subtests):
    other = _other_org(db)
    if version == 2:
        _activate_v2(db, other.id)
    if version == 2:
        _activate_v2(db, test_auth.org.id)
    for action in ACTIONS:
        with subtests.test(action=repr(action)):
            status, method, suffix, body, _ = ACTIONS[action]
            match, request = await _fixture(authed_client, db, test_auth.user.id, status)
            async with _client_for(db, other.id) as (_, client):
                read = await client.get(f"/matches/{match.id}")
                assert read.status_code == 404
                assert "allowed_actions" not in read.json()
                path = (
                    f"/status-change-requests/{request.id}/cancel"
                    if request
                    else f"/matches/{match.id}/{suffix}"
                )
                response = await client.request(
                    method, path, **({"json": body} if body is not None else {})
                )
                assert response.status_code == 404
            assert _match_row(db, match.id).status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_view_only_member_proposal_follows_policy_version(
    authed_client, db, test_auth, version
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
        for permission in ("propose_matches", "decide_matches", "close_matches"):
            _set_role_permission(db, test_auth.org.id, Role.CASE_MANAGER, permission, False)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    async with _client_for(
        db,
        test_auth.org.id,
        role=Role.CASE_MANAGER,
        revoke=("propose_matches",) if version == 1 else (),
    ) as (_, client):
        matches = db.query(Match).filter(Match.organization_id == test_auth.org.id)
        before = matches.count()
        proposed = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )
        if version == 1:
            assert proposed.status_code == 403
            assert proposed.json()["detail"] == "Missing permission: propose_matches"
            assert matches.count() == before
            return
        assert proposed.status_code == 201, proposed.text
        assert proposed.json()["allowed_actions"] == ["decline"]
        response = await client.put(
            f"/matches/{proposed.json()['id']}/decline", json={"reason": "Withdrawn"}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("allowed", [False, True])
async def test_approval_uses_permission_not_admin_role(
    authed_client, db, test_auth, version, allowed, subtests
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
        _set_role_permission(
            db, test_auth.org.id, Role.CASE_MANAGER, "approve_status_change_requests", allowed
        )
    for resolution in ["approve", "reject"]:
        with subtests.test(resolution=repr(resolution)):
            async with _client_for(
                db,
                test_auth.org.id,
                role=Role.CASE_MANAGER,
                grant=("approve_status_change_requests",) if version == 1 and allowed else (),
            ) as (user, client):
                match, request = await _fixture(authed_client, db, user.id, "cancellation_pending")
                response = await client.post(f"/status-change-requests/{request.id}/{resolution}")
                assert response.status_code == (200 if allowed else 403), response.text
                if not allowed:
                    assert (
                        response.json()["detail"]
                        == "Missing permission: approve_status_change_requests"
                    )
                    assert _match_row(db, match.id).status == "cancellation_pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize(
    "kind,permission",
    [
        ("surrogate", "change_surrogate_status"),
        ("surrogate", "edit_intended_parents"),
        ("egg", "change_donor_status"),
        ("sperm", "change_donor_status"),
    ],
)
async def test_accept_preview_and_execution_require_each_moving_party_permission(
    authed_client, db, test_auth, version, kind, permission
):
    from tests.test_match_cases import _donor

    if version == 2:
        _activate_v2(db, test_auth.org.id)
        _set_role_permission(db, test_auth.org.id, Role.CASE_MANAGER, permission, False)
    async with _client_for(
        db,
        test_auth.org.id,
        role=Role.CASE_MANAGER,
        revoke=(permission,) if version == 1 else (),
    ) as (user, client):
        if kind == "surrogate":
            row, _ = await _fixture(authed_client, db, user.id, "under_review")
            match_id = row.id
        else:
            match = await _case(
                authed_client,
                await _create_intended_parent(authed_client),
                donor=await _donor(authed_client, donor_type=kind),
            )
            match_id = match["id"]
        read = await client.get(f"/matches/{match_id}")
        assert read.status_code == 200, read.text
        assert "accept" not in read.json()["allowed_actions"]
        response = await client.put(f"/matches/{match_id}/accept", json={})
        assert response.status_code == 400, response.text
        assert (
            response.json()["detail"]
            == read.json()["blocked_reasons"]["accept"]
            == f"Missing permission: {permission}"
        )
        assert _match_row(db, match_id).status == "under_review"


@pytest.mark.asyncio
async def test_complete_preview_and_execution_block_open_attempts(
    authed_client, db, test_auth, subtests
):
    from app.db.models import MatchAttempt

    for status in ["planned", "in_progress"]:
        with subtests.test(status=repr(status)):
            match, _ = await _fixture(authed_client, db, test_auth.user.id, "accepted")
            db.add(
                MatchAttempt(
                    organization_id=match.organization_id,
                    match_id=match.id,
                    sequence=1,
                    attempt_type="embryo_transfer",
                    status=status,
                )
            )
            db.commit()
            read = await authed_client.get(f"/matches/{match.id}")
            assert "complete" not in read.json()["allowed_actions"]
            response = await authed_client.put(
                f"/matches/{match.id}/complete", json={"outcome": "Ended"}
            )
            assert response.status_code == 400
            assert response.json()["detail"] == read.json()["blocked_reasons"]["complete"]
            assert _match_row(db, match.id).status == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["accept", "complete"])
async def test_preview_and_execution_respect_expansion_flag(authed_client, db, monkeypatch, action):
    from app.core.config import settings
    from tests.test_match_cases import _accept, _donor

    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        donor=await _donor(authed_client),
    )
    if action == "complete":
        await _accept(authed_client, match)
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    read = await authed_client.get(f"/matches/{match['id']}")
    assert read.status_code == 200, read.text
    assert action not in read.json()["allowed_actions"]
    response = await authed_client.put(
        f"/matches/{match['id']}/{action}",
        json={"outcome": "Ended"} if action == "complete" else {},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == read.json()["blocked_reasons"][action]


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_only_requester_has_withdraw_capability(authed_client, db, test_auth, version):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
    match, request = await _fixture(authed_client, db, test_auth.user.id, "cancellation_pending")
    async with _client_for(db, test_auth.org.id) as (_, client):
        read = await client.get(f"/matches/{match.id}")
        assert read.json()["allowed_actions"] == []
        response = await client.post(f"/status-change-requests/{request.id}/cancel")
        assert response.status_code == 403
        assert (
            response.json()["detail"]
            == read.json()["blocked_reasons"]["withdraw_cancel"]
            == "Only the requester can withdraw the cancellation request"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_pending_cancellation_id_is_visible_to_view_only_readers(
    authed_client, db, test_auth, version
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
        _set_role_permission(db, test_auth.org.id, Role.CASE_MANAGER, "close_matches", False)
    match, request = await _fixture(authed_client, db, test_auth.user.id, "cancellation_pending")
    async with _client_for(
        db,
        test_auth.org.id,
        role=Role.CASE_MANAGER,
        revoke=("propose_matches",) if version == 1 else (),
    ) as (_, client):
        response = await client.get(f"/matches/{match.id}")
        assert response.status_code == 200, response.text
        assert response.json()["pending_cancellation_request_id"] == str(request.id)
        assert response.json()["allowed_actions"] == []
        denied = await client.post(f"/status-change-requests/{request.id}/approve")
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Missing permission: approve_status_change_requests"
        for match_status, request_status in (
            ("accepted", "pending"),
            ("cancellation_pending", "rejected"),
        ):
            match.status, request.status = match_status, request_status
            db.commit()
            response = await client.get(f"/matches/{match.id}")
            assert response.status_code == 200
            assert response.json()["pending_cancellation_request_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_pending_cancellation_id_is_not_exposed_cross_org(
    authed_client, db, test_auth, version
):
    if version == 2:
        _activate_v2(db, test_auth.org.id)
    match, request = await _fixture(authed_client, db, test_auth.user.id, "cancellation_pending")
    other_org = _other_org(db)
    if version == 2:
        _activate_v2(db, other_org.id)
    async with _client_for(db, other_org.id) as (_, client):
        response = await client.get(f"/matches/{match.id}")
        assert response.status_code == 404
        assert "pending_cancellation_request_id" not in response.json()
        assert str(request.id) not in response.text
    assert _match_row(db, match.id).status == "cancellation_pending"
    db.refresh(request)
    assert request.status == "pending"
