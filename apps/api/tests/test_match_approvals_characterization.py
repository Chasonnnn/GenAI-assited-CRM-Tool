"""Characterization of approvals-queue paths that change Match.status.

Pins current behavior of status_change_request_service for match cancellation
requests (approve, reject, withdraw) before the match engine refactor
(docs/match-lifecycle-refactor-plan.md, step 2). Kept apart from the lifecycle
file because permission v2 rewrites status_change_request_service.
"""

import uuid

import pytest

from app.core.config import settings
from app.db.enums import Role
from app.db.models import (
    AuditLog,
    Donor,
    IntendedParent,
    Match,
    MatchAttempt,
    Notification,
    StatusChangeRequest,
    Surrogate,
    SurrogateStatusHistory,
    UserPermissionOverride,
)
from app.services import intended_parent_status_service, notification_service
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import (
    _client_for,
    _committed_org,
    _committed_state,
    _diff,
    _ip_stage_key,
    _locked_tables,
    _match_row,
    _move_ip_to_stage,
    _other_org,
    _snapshot,
    _Spy,
    _spy_ordered_effects,
    _stage_slug,
)


async def _pending_cancellation(
    authed_client, db, *, requester=None, donor=False, reason="Family withdrew"
):
    """Accept a new match and file a cancellation request; returns (match, request)."""
    ip = await _create_intended_parent(authed_client)
    party = await _donor(authed_client) if donor else await _create_surrogate(authed_client)
    match = await _accept(
        authed_client,
        await _case(authed_client, ip, **({"donor": party} if donor else {"surrogate": party})),
    )
    body = {} if reason is None else {"reason": reason}
    response = await (requester or authed_client).post(
        f"/matches/{match['id']}/cancel-request", json=body
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_id == uuid.UUID(match["id"]),
            StatusChangeRequest.status == "pending",
        )
        .one()
    )
    return match, request


def _request_row(db, request_id) -> StatusChangeRequest:
    db.expire_all()
    return db.get(StatusChangeRequest, request_id)


def _restored_history(event: str) -> dict:
    """Match history for a resolved request that returns the match to accepted."""
    return {
        "audit": {(event, "match"): 1},
        "surrogate_activity": {event: 1},
        "entity_activity": {("intended_parent", event): 1},
        "stage_history": {},
    }


# =============================================================================
# Approve
# =============================================================================


@pytest.mark.asyncio
async def test_approve_cancellation_cancels_match_and_returns_parties_to_ready(
    authed_client, db, test_auth, monkeypatch
):
    resolved = _Spy(notification_service.notify_match_cancel_request_resolved)
    monkeypatch.setattr(notification_service, "notify_match_cancel_request_resolved", resolved)
    async with _client_for(db, test_auth.org.id) as (requester, requester_client):
        match, request = await _pending_cancellation(
            authed_client, db, requester=requester_client, reason="Family withdrew"
        )
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["approved_by_user_id"] == str(test_auth.user.id)
    row = _match_row(db, match["id"])
    assert row.status == "cancelled"
    assert row.closed_by_user_id == test_auth.user.id
    assert row.closure_reason == "Family withdrew"
    assert row.closed_at is not None
    assert _stage_slug(db, Surrogate, match["surrogate_id"]) == "ready_to_match"
    assert _ip_stage_key(db, match["intended_parent_id"]) == "ready_to_match"
    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == uuid.UUID(match["surrogate_id"]))
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert history.changed_by_user_id == test_auth.user.id
    assert history.reason == "Family withdrew"
    assert locks == ["status_change_requests", "matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_cancelled", "match"): 1},
        "surrogate_activity": {"match_cancelled": 1, "note_added": 1},
        "entity_activity": {("intended_parent", "match_cancelled"): 1},
        "stage_history": {"surrogate": 1, "intended_parent": 1},
    }
    assert len(resolved.calls) == 1
    assert resolved.calls[0][1]["approved"] is True
    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == requester.id,
            Notification.entity_id == uuid.UUID(match["id"]),
            Notification.type == "status_change_approved",
        )
        .one()
    )
    assert notification.entity_type == "match"


@pytest.mark.asyncio
async def test_approve_donor_cancellation_leaves_donor_stage_unchanged(
    authed_client, db, test_auth
):
    match, request = await _pending_cancellation(authed_client, db, donor=True)
    donor_stage = _stage_slug(db, Donor, match["donor_id"])
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "cancelled"
    assert _stage_slug(db, Donor, match["donor_id"]) == donor_stage
    assert _ip_stage_key(db, match["intended_parent_id"]) == "ready_to_match"
    assert locks == ["status_change_requests", "matches", "donors", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_cancelled", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_cancelled"): 1,
            ("intended_parent", "match_cancelled"): 1,
        },
        "stage_history": {"intended_parent": 1},
    }


@pytest.mark.asyncio
async def test_approve_cancellation_closes_open_surrogate_attempts(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    match = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    attempts = []
    for status in ("planned", "in_progress", "completed"):
        response = await authed_client.post(
            f"/matches/{match['id']}/attempts",
            json={"attempt_type": "embryo_transfer", "status": status},
        )
        assert response.status_code == 201, response.text
        attempts.append(response.json()["id"])
    response = await authed_client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
    assert response.status_code == 200
    request = (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(match["id"]))
        .one()
    )

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    db.expire_all()
    assert [db.get(MatchAttempt, uuid.UUID(a)).status for a in attempts] == [
        "cancelled",
        "cancelled",
        "completed",
    ]


@pytest.mark.asyncio
async def test_approve_when_match_no_longer_cancel_pending_returns_400(
    authed_client, db, test_auth
):
    match, request = await _pending_cancellation(authed_client, db)
    db.get(Match, uuid.UUID(match["id"])).status = "accepted"
    db.commit()

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == "Match is no longer pending cancellation"
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "accepted"


@pytest.mark.asyncio
async def test_approve_stage_failure_commits_nothing(authed_client, db, test_auth, monkeypatch):
    # Called at the service level: over HTTP the test session is shared with the
    # mutation-audit fallback middleware, which commits it after a 4xx.
    from app.services import status_change_request_service

    match, request = await _pending_cancellation(authed_client, db)
    commits = []

    def fail(**kwargs):
        raise ValueError("IP stage change failed")

    monkeypatch.setattr(intended_parent_status_service, "apply_status_change", fail)
    monkeypatch.setattr(db, "commit", lambda: commits.append("commit"))

    request_id = request.id
    with pytest.raises(ValueError, match="IP stage change failed"), db.begin_nested():
        status_change_request_service.approve_request(
            db=db,
            request_id=request_id,
            org_id=test_auth.org.id,
            admin_user_id=test_auth.user.id,
            admin_role=Role.DEVELOPER,
        )

    assert commits == []
    assert _request_row(db, request_id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"
    assert _stage_slug(db, Surrogate, match["surrogate_id"]) == "matched"


async def _committed_pending_cancellation(client, db_engine):
    """Pending cancellation in a committed org; returns (match, request_id)."""
    from sqlalchemy.orm import Session

    match = await _accept(
        client,
        await _case(
            client, await _create_intended_parent(client), surrogate=await _create_surrogate(client)
        ),
    )
    response = await client.post(f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"})
    assert response.status_code == 200, response.text
    with Session(db_engine) as verify:
        request_id = (
            verify.query(StatusChangeRequest.id)
            .filter(StatusChangeRequest.entity_id == uuid.UUID(match["id"]))
            .scalar()
        )
    return match, request_id


@pytest.mark.asyncio
async def test_approve_dispatches_surrogate_stage_callbacks_before_notification(
    authed_client, db, test_auth, monkeypatch
):
    async with _client_for(db, test_auth.org.id) as (requester, requester_client):
        match, request = await _pending_cancellation(
            authed_client, db, requester=requester_client, reason="Ended"
        )
    events: list[str] = []
    spies = _spy_ordered_effects(monkeypatch, events)

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    assert events == [
        "dispatch_note_added",
        "handle_status_changed",
        "notify_match_cancel_request_resolved",
    ]
    stage = spies["handle_status_changed"].calls[0][1]
    assert stage["surrogate"].id == uuid.UUID(match["surrogate_id"])
    assert stage["new_stage"].slug == "ready_to_match"
    assert stage["old_slug"] == "matched"
    assert stage["user_id"] == test_auth.user.id
    assert stage["request_id"] == request.id
    assert stage["approved_by_user_id"] == test_auth.user.id
    assert stage["trigger_workflows"] is True
    note = spies["dispatch_note_added"].calls[0][1]
    assert note["org_id"] == test_auth.org.id
    resolved = spies["notify_match_cancel_request_resolved"].calls[0][1]
    assert resolved["approved"] is True
    assert resolved["match"].id == uuid.UUID(match["id"])


@pytest.mark.asyncio
async def test_approve_donor_cancellation_dispatches_no_stage_callbacks(
    authed_client, db, monkeypatch
):
    _match, request = await _pending_cancellation(authed_client, db, donor=True)
    events: list[str] = []
    _spy_ordered_effects(monkeypatch, events)

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    assert events == ["notify_match_cancel_request_resolved"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failing",
    ["dispatch_note_added", "handle_status_changed", "notify_match_cancel_request_resolved"],
)
async def test_failing_approval_effect_returns_success_and_runs_later_effects(
    db_engine, monkeypatch, failing
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        match, request_id = await _committed_pending_cancellation(client, db_engine)
        events: list[str] = []
        _spy_ordered_effects(monkeypatch, events, failing=failing)

        response = await client.post(f"/status-change-requests/{request_id}/approve")

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"
        assert events == [
            "dispatch_note_added",
            "handle_status_changed",
            "notify_match_cancel_request_resolved",
        ]
        assert _committed_state(
            db_engine, match["id"], match["surrogate_id"], match["intended_parent_id"]
        ) == {
            "match": "cancelled",
            "requests": ["approved"],
            "surrogate_stage": "ready_to_match",
            "ip_stage": "ready_to_match",
        }


@pytest.mark.asyncio
async def test_approve_cancellation_preserves_ip_outside_matched(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    match = await _accept(authed_client, await _case(authed_client, ip, surrogate=surrogate))
    _move_ip_to_stage(db, test_auth.org.id, ip["id"], "delivered")
    response = await authed_client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
    assert response.status_code == 200
    request = (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(match["id"]))
        .one()
    )
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "cancelled"
    assert _ip_stage_key(db, ip["id"]) == "delivered"
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "ready_to_match"
    assert _diff(before, _snapshot(db, test_auth.org.id))["stage_history"] == {"surrogate": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True], ids=["surrogate_handoff", "ip_handoff"])
async def test_approve_without_handoff_stage_returns_400(
    authed_client, db, test_auth, monkeypatch, donor
):
    from app.services import pipeline_service

    match, request = await _pending_cancellation(authed_client, db, donor=donor)
    original = pipeline_service.get_stage_by_system_role

    def without_handoff(db, pipeline_id, system_role, *args, **kwargs):
        if system_role == "handoff":
            return None
        return original(db, pipeline_id, system_role, *args, **kwargs)

    monkeypatch.setattr(pipeline_service, "get_stage_by_system_role", without_handoff)

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ready to match stage not found"
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"
    assert _ip_stage_key(db, match["intended_parent_id"]) == "matched"
    if not donor:
        assert _stage_slug(db, Surrogate, match["surrogate_id"]) == "matched"


@pytest.mark.asyncio
async def test_approve_by_non_admin_role_with_approval_permission_returns_400(
    authed_client, db, test_auth
):
    match, request = await _pending_cancellation(authed_client, db)

    async with _client_for(
        db,
        test_auth.org.id,
        role=Role.CASE_MANAGER,
        grant=("approve_status_change_requests",),
    ) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/approve")
        rejected = await client.post(f"/status-change-requests/{request.id}/reject", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Only admins can approve status change requests"
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "Only admins can reject status change requests"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


# =============================================================================
# Reject
# =============================================================================


@pytest.mark.asyncio
async def test_reject_cancellation_restores_accepted_with_match_history(
    authed_client, db, test_auth, monkeypatch
):
    resolved = _Spy(notification_service.notify_match_cancel_request_resolved)
    monkeypatch.setattr(notification_service, "notify_match_cancel_request_resolved", resolved)
    async with _client_for(db, test_auth.org.id) as (requester, requester_client):
        match, request = await _pending_cancellation(authed_client, db, requester=requester_client)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.post(
            f"/status-change-requests/{request.id}/reject", json={"reason": "Not yet"}
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert response.json()["rejected_by_user_id"] == str(test_auth.user.id)
    row = _match_row(db, match["id"])
    assert row.status == "accepted"
    assert row.closed_at is None
    assert _stage_slug(db, Surrogate, match["surrogate_id"]) == "matched"
    assert _ip_stage_key(db, match["intended_parent_id"]) == "matched"
    assert locks == ["status_change_requests", "matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == _restored_history(
        "match_cancel_request_rejected"
    )
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type == "match_cancel_request_rejected",
            AuditLog.target_id == uuid.UUID(match["id"]),
        )
        .one()
    )
    assert audit.actor_user_id == test_auth.user.id
    assert audit.details["status_request_id"] == str(request.id)
    assert len(resolved.calls) == 1
    assert resolved.calls[0][1]["approved"] is False
    assert resolved.calls[0][1]["reason"] == "Not yet"
    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == requester.id,
            Notification.entity_id == uuid.UUID(match["id"]),
            Notification.type == "status_change_rejected",
        )
        .one()
    )
    assert notification.body.endswith(": Not yet")


@pytest.mark.asyncio
async def test_reject_cancellation_without_body_is_allowed(authed_client, db):
    match, request = await _pending_cancellation(authed_client, db)

    response = await authed_client.post(f"/status-change-requests/{request.id}/reject")

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "accepted"


# =============================================================================
# Withdraw (requester cancels the request)
# =============================================================================


@pytest.mark.asyncio
async def test_withdraw_cancellation_restores_accepted_with_match_history(
    authed_client, db, test_auth, monkeypatch
):
    resolved = _Spy()
    monkeypatch.setattr(notification_service, "notify_match_cancel_request_resolved", resolved)
    match, request = await _pending_cancellation(authed_client, db, reason="Changed plans")
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancelled_by_user_id"] == str(test_auth.user.id)
    assert _match_row(db, match["id"]).status == "accepted"
    assert _stage_slug(db, Surrogate, match["surrogate_id"]) == "matched"
    assert locks == ["status_change_requests", "matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == _restored_history(
        "match_cancel_request_withdrawn"
    )
    assert resolved.calls == []


@pytest.mark.asyncio
async def test_withdraw_by_non_requester_returns_400(authed_client, db, test_auth):
    match, request = await _pending_cancellation(authed_client, db)

    async with _client_for(db, test_auth.org.id) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == 400
    assert response.json()["detail"] == "Only the requester can cancel their request"
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
async def test_withdraw_requires_propose_matches(authed_client, db, test_auth):
    async with _client_for(db, test_auth.org.id) as (requester, requester_client):
        match, request = await _pending_cancellation(authed_client, db, requester=requester_client)
        db.add(
            UserPermissionOverride(
                id=uuid.uuid4(),
                organization_id=test_auth.org.id,
                user_id=requester.id,
                permission="propose_matches",
                override_type="revoke",
            )
        )
        db.commit()

        response = await requester_client.post(f"/status-change-requests/{request.id}/cancel")

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission for request entity"
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["reject", "cancel"])
async def test_resolving_request_leaves_match_outside_cancel_pending_unchanged(
    authed_client, db, test_auth, action
):
    from datetime import UTC, datetime

    match, request = await _pending_cancellation(authed_client, db)
    row = db.get(Match, uuid.UUID(match["id"]))
    row.status = "cancelled"
    row.closed_at = datetime.now(UTC)
    db.commit()

    before = _snapshot(db, test_auth.org.id)
    response = await authed_client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 200, response.text
    assert (
        _request_row(db, request.id).status == {"reject": "rejected", "cancel": "cancelled"}[action]
    )
    assert _match_row(db, match["id"]).status == "cancelled"

    event = (
        "match_cancel_request_rejected" if action == "reject" else "match_cancel_request_withdrawn"
    )
    assert _diff(before, _snapshot(db, test_auth.org.id)) == _restored_history(event)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first,second,resolved_status",
    [
        ("approve", "approve", "approved"),
        ("approve", "reject", "approved"),
        ("approve", "cancel", "approved"),
        ("reject", "approve", "rejected"),
        ("reject", "reject", "rejected"),
        ("cancel", "approve", "cancelled"),
        ("cancel", "cancel", "cancelled"),
    ],
)
async def test_resolving_already_resolved_request_returns_400(
    authed_client, db, first, second, resolved_status
):
    match, request = await _pending_cancellation(authed_client, db)
    response = await authed_client.post(f"/status-change-requests/{request.id}/{first}", json={})
    assert response.status_code == 200, response.text
    match_status = _match_row(db, match["id"]).status

    response = await authed_client.post(f"/status-change-requests/{request.id}/{second}", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == f"Request is not pending (status: {resolved_status})"
    assert _request_row(db, request.id).status == resolved_status
    assert _match_row(db, match["id"]).status == match_status


# =============================================================================
# Permissions and organization isolation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize(
    "role,revoke",
    [(Role.CASE_MANAGER, ()), (Role.ADMIN, ("approve_status_change_requests",))],
)
async def test_resolving_cancellation_requires_approval_permission(
    authed_client, db, test_auth, action, role, revoke
):
    match, request = await _pending_cancellation(authed_client, db)

    async with _client_for(db, test_auth.org.id, role=role, revoke=revoke) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 403
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
async def test_approving_cancellation_requires_view_matches(authed_client, db, test_auth):
    match, request = await _pending_cancellation(authed_client, db)

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 403
    assert _match_row(db, match["id"]).status == "cancellation_pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject", "cancel"])
async def test_other_org_user_gets_404_for_match_cancellation_request(
    authed_client, db, test_auth, action
):
    match, request = await _pending_cancellation(authed_client, db)
    other_org = _other_org(db)

    async with _client_for(db, other_org.id) as (_user, client):
        response = await client.post(f"/status-change-requests/{request.id}/{action}", json={})
        detail = await client.get(f"/status-change-requests/{request.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Request not found"
    assert detail.status_code == 404
    assert _request_row(db, request.id).status == "pending"
    assert _match_row(db, match["id"]).status == "cancellation_pending"


# =============================================================================
# Rollout flag MATCH_CASE_EXPANSION_ENABLED=false
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True], ids=["surrogate", "donor"])
@pytest.mark.parametrize(
    "action,match_status",
    [("approve", "cancelled"), ("reject", "accepted"), ("cancel", "accepted")],
)
async def test_disabled_expansion_allows_resolving_match_cancellation(
    authed_client, db, monkeypatch, donor, action, match_status
):
    match, request = await _pending_cancellation(authed_client, db, donor=donor)
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)

    response = await authed_client.post(f"/status-change-requests/{request.id}/{action}", json={})

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == match_status


# =============================================================================
# Notifications on request
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_request_notifies_every_member_with_approval_permission(
    authed_client, db, test_auth
):
    async with (
        _client_for(db, test_auth.org.id) as (admin, _admin_client),
        _client_for(db, test_auth.org.id, role=Role.CASE_MANAGER) as (manager, _manager_client),
    ):
        match, request = await _pending_cancellation(authed_client, db)

    recipients = {
        row.user_id
        for row in db.query(Notification).filter(
            Notification.entity_id == uuid.UUID(match["id"]),
            Notification.type == "status_change_requested",
        )
    }
    assert admin.id in recipients
    assert test_auth.user.id in recipients
    assert manager.id not in recipients


@pytest.mark.asyncio
async def test_ip_left_matched_when_another_committed_match_remains(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    first = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    second = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    for match in (first, second):
        response = await authed_client.post(
            f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
        )
        assert response.status_code == 200
    request = (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(first["id"]))
        .one()
    )

    response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(IntendedParent, uuid.UUID(ip["id"])).status == "matched"
    assert _stage_slug(db, Surrogate, first["surrogate_id"]) == "ready_to_match"
    assert _match_row(db, second["id"]).status == "cancellation_pending"
