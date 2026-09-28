"""Characterization of match cancellation approvals for permission policy v2 orgs.

Counterpart to test_match_approvals_characterization.py (v1). Pins who can
approve, reject, and withdraw a match cancellation request under v2, and who is
notified, before step 7 of docs/match-lifecycle-refactor-plan.md. Expected
values come from the current code.
"""

import uuid

import pytest

from app.db.enums import Role
from app.db.models import (
    IntendedParentStatusHistory,
    Notification,
    PipelineStage,
    Surrogate,
    SurrogateStatusHistory,
)
from tests.test_match_approvals_characterization import _pending_cancellation, _request_row
from tests.test_match_lifecycle_characterization import _client_for, _match_row
from tests.test_match_permissions_v2_characterization import (
    _set_role_permission,
    _v2_other_org,
)
from tests.test_match_permissions_v2_characterization import (
    v2_org as v2_org,
)

# =============================================================================
# Approve and reject
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
@pytest.mark.parametrize(
    "action,request_status,match_status",
    [("approve", "approved", "cancelled"), ("reject", "rejected", "accepted")],
)
async def test_v2_protected_roles_resolve_cancellation(
    authed_client, db, v2_org, role, action, request_status, match_status
):
    match, request = await _pending_cancellation(authed_client, db, reason="Ended")

    async with _client_for(db, v2_org.id, role=role) as (user, client):
        response = await client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == request_status
    by = "approved_by_user_id" if action == "approve" else "rejected_by_user_id"
    assert response.json()[by] == str(user.id)
    assert _match_row(db, match["id"]).status == match_status
    if action == "approve":
        for model in (SurrogateStatusHistory, IntendedParentStatusHistory):
            history = db.query(model).filter(model.request_id == request.id).one()
            assert history.changed_by_user_id == user.id
            assert history.approved_by_user_id == user.id
            assert history.reason == "Ended"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.OPERATIONS, Role.INTAKE_SPECIALIST])
async def test_v2_roles_without_approval_permission_cannot_reach_cancellation_request(
    authed_client, db, v2_org, role, subtests
):
    match, request = await _pending_cancellation(authed_client, db)
    for path in ["{id}/approve", "{id}/reject", "{id}"]:
        with subtests.test(path=repr(path)):
            method = "GET" if path == "{id}" else "POST"

            async with _client_for(db, v2_org.id, role=role) as (_user, client):
                response = await client.request(
                    method,
                    f"/status-change-requests/{path.format(id=request.id)}",
                    json=None if method == "GET" else {},
                )

            assert response.status_code == 403
            assert response.json()["detail"] == "Missing permission: approve_status_change_requests"
            assert _request_row(db, request.id).status == "pending"
            assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("granted_by", ["legacy_user_grant", "role_grant"])
@pytest.mark.parametrize(
    "action,request_status,match_status",
    [("approve", "approved", "cancelled"), ("reject", "rejected", "accepted")],
)
async def test_v2_case_manager_granted_approval_resolves_without_admin_role_check(
    authed_client, db, v2_org, granted_by, action, request_status, match_status
):
    # Both policy versions authorize review by permission alone.
    match, request = await _pending_cancellation(authed_client, db)
    grant = ("approve_status_change_requests",) if granted_by == "legacy_user_grant" else ()
    if granted_by == "role_grant":
        _set_role_permission(
            db, v2_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True
        )

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER, grant=grant) as (_u, client):
        response = await client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 200, response.text
    assert _request_row(db, request.id).status == request_status
    assert _match_row(db, match["id"]).status == match_status


@pytest.mark.asyncio
@pytest.mark.parametrize("denied_by", ["legacy_user_revoke", "role_denial"])
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_v2_admin_ignores_approval_permission_denials(
    authed_client, db, v2_org, denied_by, action
):
    _match, request = await _pending_cancellation(authed_client, db)
    revoke = ("approve_status_change_requests",) if denied_by == "legacy_user_revoke" else ()
    if denied_by == "role_denial":
        _set_role_permission(db, v2_org.id, Role.ADMIN, "approve_status_change_requests", False)

    async with _client_for(db, v2_org.id, role=Role.ADMIN, revoke=revoke) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_v2_granted_approver_without_view_matches_gets_404(
    authed_client, db, v2_org, subtests
):
    match, request = await _pending_cancellation(authed_client, db)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "view_matches", False)

    for action in ["approve", "reject"]:
        with subtests.test(action=repr(action)):
            async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
                response = await client.post(
                    f"/status-change-requests/{request.id}/{action}", json={}
                )

            assert response.status_code == 404
            assert response.json()["detail"] == "Request not found"
            assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
async def test_v2_granted_approver_outside_donor_scope_gets_404(authed_client, db, v2_org):
    # Case Manager donor scope is post-approval; a new donor is still pre-approval.
    match, request = await _pending_cancellation(authed_client, db, donor=True)
    from app.db.models import Donor
    from tests.test_match_participant_stages import _stage

    _stage(db, db.get(Donor, uuid.UUID(match["donor_id"])), "new")
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True)

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 404
    assert response.json()["detail"] == "Request not found"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


# =============================================================================
# Withdraw (requester cancels the request)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configured,code,detail",
    [
        ("none", 200, None),
        ("legacy_user_revoke", 200, None),
        ("role_denied_close_matches", 403, "Missing permission: close_matches"),
        ("role_denied_view_matches", 404, "Request not found"),
    ],
)
async def test_v2_case_manager_requester_withdraws_cancellation(
    authed_client, db, v2_org, configured, code, detail
):
    revoke = ("propose_matches", "view_matches") if configured == "legacy_user_revoke" else ()
    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER, revoke=revoke) as (
        _requester,
        client,
    ):
        match, request = await _pending_cancellation(authed_client, db, requester=client)
        if configured.startswith("role_denied_"):
            permission = configured.removeprefix("role_denied_")
            _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, permission, False)

        response = await client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == code, response.text
    if detail is None:
        assert _request_row(db, request.id).status == "cancelled"
        assert _match_row(db, match["id"]).status == "accepted"
    else:
        assert response.json()["detail"] == detail
        assert _request_row(db, request.id).status == "pending"
        assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
async def test_v2_withdraw_by_non_requester_admin_returns_403(authed_client, db, v2_org):
    match, request = await _pending_cancellation(authed_client, db)

    async with _client_for(db, v2_org.id, role=Role.ADMIN) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == 403
    assert response.json()["detail"] == "Only the requester can withdraw the cancellation request"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


# =============================================================================
# Organization isolation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.CASE_MANAGER])
async def test_v2_other_org_user_gets_404_for_match_cancellation_request(
    authed_client, db, v2_org, role, subtests
):
    match, request = await _pending_cancellation(authed_client, db)
    other_org = _v2_other_org(db)
    if role == Role.CASE_MANAGER:
        _set_role_permission(
            db, other_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True
        )

    for action in ["approve", "reject", "cancel", "detail"]:
        with subtests.test(action=repr(action)):
            async with _client_for(db, other_org.id, role=role) as (_user, client):
                if action == "detail":
                    response = await client.get(f"/status-change-requests/{request.id}")
                else:
                    response = await client.post(
                        f"/status-change-requests/{request.id}/{action}", json={}
                    )

            assert response.status_code == 404
            assert response.json()["detail"] == "Request not found"
            assert _request_row(db, request.id).status == "pending"
            assert _match_row(db, match["id"]).status == "cancellation_pending"


# =============================================================================
# Pending request list (GET /status-change-requests)
# =============================================================================


def _move_surrogate_before_approval(db, surrogate_id):
    """Put a surrogate back in an intake stage, outside the Case Manager scope."""
    surrogate = db.get(Surrogate, uuid.UUID(surrogate_id))
    intake = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == surrogate.stage.pipeline_id,
            PipelineStage.stage_type == "intake",
            PipelineStage.is_active.is_(True),
        )
        .order_by(PipelineStage.order)
        .first()
    )
    surrogate.stage_id = intake.id
    db.commit()


async def _listed_requests(db, org_id, role, **params):
    async with _client_for(db, org_id, role=role) as (_user, client):
        return await client.get("/status-change-requests", params=params)


@pytest.mark.asyncio
async def test_v2_request_list_requires_approval_permission(authed_client, db, v2_org, subtests):
    await _pending_cancellation(authed_client, db)

    for role in [Role.CASE_MANAGER, Role.OPERATIONS, Role.INTAKE_SPECIALIST]:
        with subtests.test(role=repr(role)):
            response = await _listed_requests(db, v2_org.id, role)

            assert response.status_code == 403
            assert response.json()["detail"] == "Missing permission: approve_status_change_requests"


@pytest.mark.asyncio
async def test_v2_request_list_shows_only_requests_in_the_callers_scope(
    authed_client, db, v2_org, subtests
):
    _visible_match, visible = await _pending_cancellation(authed_client, db)
    _donor_match, donor = await _pending_cancellation(authed_client, db, donor=True)
    intake_match, intake = await _pending_cancellation(authed_client, db)
    _move_surrogate_before_approval(db, intake_match["surrogate_id"])
    other_org = _v2_other_org(db)
    async with _client_for(db, other_org.id, role=Role.DEVELOPER) as (_dev, developer):
        _foreign_match, foreign = await _pending_cancellation(developer, db)
    for org_id in (v2_org.id, other_org.id):
        _set_role_permission(db, org_id, Role.CASE_MANAGER, "approve_status_change_requests", True)

    for per_page in [20, 1]:
        with subtests.test(per_page=repr(per_page)):
            manager = await _listed_requests(db, v2_org.id, Role.CASE_MANAGER, per_page=per_page)
            admin = await _listed_requests(db, v2_org.id, Role.ADMIN)
            foreign_admin = await _listed_requests(db, other_org.id, Role.ADMIN)

            assert manager.status_code == 200, manager.text
            expected = {str(visible.id), str(donor.id)}
            listed = {item["request"]["id"] for item in manager.json()["items"]}
            assert listed <= expected
            assert len(listed) == min(per_page, 2)
            assert manager.json()["total"] == 2
            if per_page == 1:
                second_page = await _listed_requests(
                    db, v2_org.id, Role.CASE_MANAGER, per_page=1, page=2
                )
                assert (
                    listed | {item["request"]["id"] for item in second_page.json()["items"]}
                    == expected
                )
            else:
                assert listed == expected
            assert admin.status_code == 200, admin.text
            assert {item["request"]["id"] for item in admin.json()["items"]} == {
                str(visible.id),
                str(donor.id),
                str(intake.id),
            }
            assert admin.json()["total"] == 3
            assert {item["request"]["id"] for item in foreign_admin.json()["items"]} == {
                str(foreign.id)
            }
            assert foreign_admin.json()["total"] == 1


# =============================================================================
# Notifications on request
# =============================================================================


@pytest.mark.asyncio
async def test_v2_cancel_request_notifies_members_with_effective_approval_permission(
    authed_client, db, test_auth, v2_org
):
    approval = "approve_status_change_requests"
    _set_role_permission(db, v2_org.id, Role.OPERATIONS, approval, True)
    _set_role_permission(db, v2_org.id, Role.ADMIN, approval, False)
    async with (
        _client_for(db, v2_org.id) as (admin, _c1),
        _client_for(db, v2_org.id, revoke=(approval,)) as (revoked_admin, _c2),
        _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (manager, _c3),
        _client_for(db, v2_org.id, role=Role.CASE_MANAGER, grant=(approval,)) as (granted, _c4),
        _client_for(db, v2_org.id, role=Role.OPERATIONS) as (operations, _c5),
        _client_for(db, v2_org.id, role=Role.INTAKE_SPECIALIST) as (intake, _c6),
    ):
        match, _request = await _pending_cancellation(authed_client, db)

    recipients = {
        row.user_id
        for row in db.query(Notification).filter(
            Notification.entity_id == uuid.UUID(match["id"]),
            Notification.type == "status_change_requested",
        )
    }
    assert {test_auth.user.id, admin.id, revoked_admin.id, granted.id, operations.id} <= recipients
    assert manager.id not in recipients
    assert intake.id not in recipients


@pytest.mark.asyncio
async def test_v2_donor_cancel_requires_stage_permission_only_when_last_match_closes(
    authed_client, db, v2_org
):
    from app.db.models import Donor
    from tests.test_match_cancel_request import _create_intended_parent
    from tests.test_match_cases import _accept, _case, _donor

    donor = await _donor(authed_client)
    matches = [
        await _accept(
            authed_client,
            await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
        )
        for _ in range(2)
    ]
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "change_donor_status", False)
    for index, match in enumerate(matches):
        response = await authed_client.post(
            f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
        )
        assert response.status_code == 200
        from app.db.models import StatusChangeRequest

        request = (
            db.query(StatusChangeRequest)
            .filter_by(entity_id=uuid.UUID(match["id"]), status="pending")
            .one()
        )
        async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_, client):
            approved = await client.post(f"/status-change-requests/{request.id}/approve")
        assert approved.status_code == (200 if index == 0 else 400), approved.text
        if index == 1:
            assert approved.json()["detail"] == "Missing permission: change_donor_status"
            assert _request_row(db, request.id).status == "pending"
        assert db.get(Donor, uuid.UUID(donor["id"])).stage.stage_key == "matched"


@pytest.mark.asyncio
async def test_v2_cancel_requires_no_stage_permission_when_parties_already_at_handoff(
    authed_client, db, v2_org
):
    from app.db.models import IntendedParent
    from tests.test_match_participant_stages import _stage

    match, request = await _pending_cancellation(authed_client, db)
    _stage(db, db.get(Surrogate, uuid.UUID(match["surrogate_id"])), "ready_to_match")
    _stage(db, db.get(IntendedParent, uuid.UUID(match["intended_parent_id"])), "ready_to_match")
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "approve_status_change_requests", True)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "change_surrogate_status", False)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "edit_intended_parents", False)
    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_, client):
        response = await client.post(f"/status-change-requests/{request.id}/approve")
    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "cancelled"
    assert db.query(SurrogateStatusHistory).filter_by(request_id=request.id).count() == 0
    assert db.query(IntendedParentStatusHistory).filter_by(request_id=request.id).count() == 0
