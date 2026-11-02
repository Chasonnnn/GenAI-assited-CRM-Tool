"""Characterization of match cancellation, the rollout flag, permissions, org isolation, and CSRF.

Split from test_match_lifecycle_characterization.py; the same pinning rules apply.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import (
    Match,
    StatusChangeRequest,
    Surrogate,
    Task,
)
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import (
    _call_counts,
    _client_for,
    _diff,
    _foreign_accepted_match,
    _ip_stage_key,
    _locked_tables,
    _match_row,
    _other_org,
    _request_cancel,
    _reset,
    _snapshot,
    _spy_effects,
    _stage_slug,
)

# =============================================================================
# Cancellation request (accepted matches)
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_request_sets_cancellation_pending_and_notifies(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _accept(authed_client, await _case(authed_client, ip, surrogate=surrogate))
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.post(
            f"/matches/{created['id']}/cancel-request", json={"reason": "  Family withdrew  "}
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancellation_pending"
    assert _match_row(db, created["id"]).status == "cancellation_pending"
    request = (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(created["id"]))
        .one()
    )
    assert request.entity_type == "match"
    assert request.status == "pending"
    assert request.target_status == "cancelled"
    assert request.target_stage_id is None
    assert request.reason == "Family withdrew"
    assert request.requested_by_user_id == test_auth.user.id
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "matched"
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_cancel_requested", "match"): 1},
        "surrogate_activity": {"match_cancel_requested": 1},
        "entity_activity": {("intended_parent", "match_cancel_requested"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {"notify_match_cancel_request_pending": 1}
    kwargs = spies["notify_match_cancel_request_pending"].calls[0][1]
    assert kwargs["request"].id == request.id
    assert kwargs["match"].id == uuid.UUID(created["id"])
    assert kwargs["surrogate"].id == uuid.UUID(surrogate["id"])
    assert kwargs["intended_parent"].id == uuid.UUID(ip["id"])
    assert kwargs["requester_name"] == test_auth.user.display_name


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"reason": None}, {"reason": ""}, {"reason": "  "}])
async def test_cancel_request_requires_reason(authed_client, db, body):
    created = await _accept(
        authed_client,
        await _case(
            authed_client,
            await _create_intended_parent(authed_client),
            surrogate=await _create_surrogate(authed_client),
        ),
    )
    response = await authed_client.post(f"/matches/{created['id']}/cancel-request", json=body)
    assert response.status_code == 422
    assert _match_row(db, created["id"]).status == "accepted"
    assert (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(created["id"]))
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_cancel_request_for_donor_match_notifies_with_donor(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        await _request_cancel(authed_client, created, "Ended")

    assert locks == ["matches", "donors", "intended_parents"]
    assert _call_counts(spies) == {"notify_match_cancel_request_pending": 1}
    assert spies["notify_match_cancel_request_pending"].calls[0][1]["surrogate"].id == uuid.UUID(
        donor["id"]
    )
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_cancel_requested", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_cancel_requested"): 1,
            ("intended_parent", "match_cancel_requested"): 1,
        },
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_second_cancel_request_returns_same_409_as_stale_request(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    await _request_cancel(authed_client, created)

    response = await authed_client.post(
        f"/matches/{created['id']}/cancel-request", json={"reason": "Ended"}
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"] == "A pending cancellation request already exists for this match"
    )
    assert (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(created["id"]))
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_cancel_request_with_stale_pending_request_returns_409(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    now = datetime.now(UTC)
    db.add(
        StatusChangeRequest(
            organization_id=test_auth.org.id,
            entity_type="match",
            entity_id=uuid.UUID(created["id"]),
            target_status="cancelled",
            effective_at=now,
            reason="",
            requested_by_user_id=test_auth.user.id,
            requested_at=now,
            status="pending",
        )
    )
    db.commit()

    response = await authed_client.post(
        f"/matches/{created['id']}/cancel-request", json={"reason": "Ended"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A pending cancellation request already exists for this match"
    )
    assert _match_row(db, created["id"]).status == "accepted"


# =============================================================================
# Rollout flag MATCH_CASE_EXPANSION_ENABLED=false
# =============================================================================


@pytest.mark.asyncio
async def test_disabled_expansion_allows_surrogate_reject_cancel_and_cancel_request(
    authed_client, db, monkeypatch
):
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    surrogate = await _create_surrogate(authed_client)
    rejected = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    cancelled = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    accepted = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )

    response = await authed_client.put(f"/matches/{rejected['id']}/decline", json={"reason": "No"})
    assert response.status_code == 200
    assert (
        await authed_client.put(f"/matches/{cancelled['id']}/decline", json={"reason": "Withdrawn"})
    ).status_code == 200
    await _accept(authed_client, accepted)
    requested = await _request_cancel(authed_client, accepted)

    assert requested["status"] == "cancellation_pending"
    notes = await authed_client.patch(f"/matches/{accepted['id']}/notes", json={"notes": "Kept"})
    assert notes.status_code == 200


@pytest.mark.asyncio
async def test_disabled_expansion_blocks_donor_accept_with_503(authed_client, db, monkeypatch):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=await _donor(authed_client))
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 503
    assert response.json()["detail"] == "New match features are temporarily unavailable"
    assert _match_row(db, created["id"]).status == "under_review"
    assert _ip_stage_key(db, ip["id"]) == "ready_to_match"


@pytest.mark.asyncio
async def test_disabled_expansion_allows_donor_view_reject_cancel_and_cancel_request(
    authed_client, db, test_auth, monkeypatch
):
    donor = await _donor(authed_client)
    rejected = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    cancelled = await _case(
        authed_client, await _create_intended_parent(authed_client), donor=donor
    )
    accepted = await _accept(
        authed_client,
        await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
    )
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)

    response = await authed_client.put(f"/matches/{rejected['id']}/decline", json={"reason": "No"})
    assert response.status_code == 200
    assert (
        await authed_client.put(f"/matches/{cancelled['id']}/decline", json={"reason": "Withdrawn"})
    ).status_code == 200
    requested = await _request_cancel(authed_client, accepted)
    assert requested["status"] == "cancellation_pending"
    viewed = await authed_client.get(f"/matches/{accepted['id']}")
    assert viewed.status_code == 200


@pytest.mark.asyncio
async def test_disabled_expansion_blocks_donor_repeat_pair_after_closure_with_503(
    authed_client, db, test_auth, monkeypatch
):
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    first = await _case(authed_client, ip, donor=donor)
    await authed_client.put(f"/matches/{first['id']}/decline", json={"reason": "Withdrawn"})
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    count = db.query(Match).filter(Match.organization_id == test_auth.org.id).count()

    response = await authed_client.post(
        "/matches/", json={"donor_id": donor["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 503
    assert db.query(Match).filter(Match.organization_id == test_auth.org.id).count() == count


# =============================================================================
# Permissions (v1 organization: propose_matches gates every mutation)
# =============================================================================

MATCH_MUTATIONS = [
    ("PUT", "/matches/{id}/accept", {}),
    ("PUT", "/matches/{id}/decline", {"reason": "No"}),
    ("POST", "/matches/{id}/cancel-request", {"reason": "Ended"}),
    ("PATCH", "/matches/{id}/notes", {"notes": "Changed"}),
]


@pytest.mark.asyncio
async def test_user_without_propose_matches_cannot_propose(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    count = db.query(Match).filter_by(organization_id=test_auth.org.id).count()

    async with _client_for(db, test_auth.org.id, revoke=("propose_matches",)) as (_user, client):
        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: propose_matches"
    assert db.query(Match).filter_by(organization_id=test_auth.org.id).count() == count


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", MATCH_MUTATIONS)
async def test_user_without_propose_matches_is_denied_every_mutation(
    authed_client, db, test_auth, method, path, body
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if "cancel-request" in path:
        await _accept(authed_client, created)
    status_before = _match_row(db, created["id"]).status

    async with _client_for(db, test_auth.org.id, revoke=("propose_matches",)) as (_user, client):
        response = await client.request(method, path.format(id=created["id"]), json=body)

    assert response.status_code == 403
    assert _match_row(db, created["id"]).status == status_before


@pytest.mark.asyncio
async def test_user_without_propose_matches_views_match_without_changing_it(
    authed_client, db, test_auth
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, revoke=("propose_matches",)) as (_user, client):
        response = await client.get(f"/matches/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "under_review"
    assert _match_row(db, created["id"]).reviewed_by_user_id is None


@pytest.mark.asyncio
async def test_user_without_view_matches_cannot_view_match(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        listed = await client.get("/matches/")

    assert detail.status_code == 403
    assert listed.status_code == 403
    assert _match_row(db, created["id"]).status == "under_review"


@pytest.mark.asyncio
async def test_intake_specialist_role_cannot_view_or_mutate_match(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, role=Role.INTAKE_SPECIALIST) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        accept = await client.put(f"/matches/{created['id']}/accept", json={})

    assert detail.status_code == 403
    assert accept.status_code == 403
    assert _match_row(db, created["id"]).status == "under_review"


# =============================================================================
# Cross-organization isolation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/matches/{id}", None),
        ("GET", "/matches/{id}/events", None),
        *MATCH_MUTATIONS,
    ],
)
async def test_other_org_user_gets_404_for_match_routes(
    authed_client, db, test_auth, method, path, body
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if "cancel-request" in path:
        await _accept(authed_client, created)
    row = _match_row(db, created["id"])
    before = (row.status, row.notes, row.reviewed_by_user_id, row.updated_at)
    other_org = _other_org(db)

    async with _client_for(db, other_org.id) as (_user, client):
        response = await client.request(method, path.format(id=created["id"]), json=body)

    assert response.status_code == 404
    assert response.json()["detail"] == "Match not found"
    row = _match_row(db, created["id"])
    assert (row.status, row.notes, row.reviewed_by_user_id, row.updated_at) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "GET", "PUT", "DELETE"])
async def test_other_org_user_gets_404_for_match_event_actions(authed_client, db, method):
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    path = f"/matches/{match['id']}/events"
    body = {
        "person_type": "surrogate",
        "event_type": "medical_exam",
        "title": "Consultation",
        "all_day": True,
        "start_date": "2026-09-25",
    }
    created = await authed_client.post(path, json=body)
    assert created.status_code == 201, created.text
    before = (await authed_client.get(path)).json()
    target = path if method == "POST" else f"{path}/{created.json()['id']}"
    payload = body if method == "POST" else {"title": "Changed"} if method == "PUT" else None

    async with _client_for(db, _other_org(db).id) as (_user, client):
        response = await client.request(method, target, json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Match not found"
    assert (await authed_client.get(path)).json() == before


@pytest.mark.asyncio
async def test_other_org_user_cannot_propose_with_foreign_parties(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    other_org = _other_org(db)
    matches = db.query(Match).filter(Match.organization_id.in_((test_auth.org.id, other_org.id)))
    count = matches.count()

    async with _client_for(db, other_org.id) as (_user, client):
        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

    assert response.status_code == 404
    assert matches.count() == count


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "donor"])
@pytest.mark.parametrize("foreign_side", ["intended_parent", "participant"])
async def test_propose_with_one_foreign_party_returns_404(
    authed_client, db, test_auth, kind, foreign_side
):
    create_party = _donor if kind == "donor" else _create_surrogate
    other_org = _other_org(db)
    async with _client_for(db, other_org.id, role=Role.DEVELOPER) as (_user, foreign):
        foreign_ip = await _create_intended_parent(foreign)
        foreign_party = await create_party(foreign)
    local_ip = await _create_intended_parent(authed_client)
    local_party = await create_party(authed_client)
    if foreign_side == "intended_parent":
        ip, party = foreign_ip, local_party
    else:
        ip, party = local_ip, foreign_party
    matches = db.query(Match).filter(Match.organization_id.in_((test_auth.org.id, other_org.id)))
    count = matches.count()

    response = await authed_client.post(
        "/matches/", json={f"{kind}_id": party["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 404
    assert matches.count() == count


@pytest.mark.asyncio
async def test_ai_routes_return_404_for_foreign_match(authed_client, db, test_auth):
    match = await _foreign_accepted_match(db)
    tasks = db.query(Task).filter(
        Task.organization_id.in_((test_auth.org.id, _match_row(db, match["id"]).organization_id))
    )
    count = tasks.count()

    bulk = await authed_client.post(
        "/ai/create-bulk-tasks",
        json={
            "request_id": str(uuid.uuid4()),
            "match_id": match["id"],
            "tasks": [{"title": "Cross-org task"}],
        },
    )
    parsed = await authed_client.post(
        "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": match["id"]}
    )

    assert bulk.status_code == 404
    assert bulk.json()["detail"] == "Match not found"
    assert parsed.status_code == 404
    assert parsed.json()["detail"] == "Match not found"
    assert tasks.count() == count


@pytest.mark.asyncio
async def test_other_org_match_list_and_stats_exclude_foreign_matches(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    other_org = _other_org(db)

    async with _client_for(db, other_org.id) as (_user, client):
        listed = await client.get("/matches/")
        stats = await client.get("/matches/stats")

    assert listed.json()["total"] == 0
    assert stats.json()["total"] == 0


# =============================================================================
# CSRF
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [("POST", "/matches/", "propose"), *MATCH_MUTATIONS],
)
async def test_match_mutations_require_csrf_header(
    authed_client, db, test_auth, method, path, body
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    if body == "propose":
        body = {"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    count = db.query(Match).filter_by(organization_id=test_auth.org.id).count()

    response = await authed_client.request(
        method, path.format(id=created["id"]), json=body, headers={CSRF_HEADER: "invalid"}
    )

    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    assert db.query(Match).filter_by(organization_id=test_auth.org.id).count() == count
    assert _match_row(db, created["id"]).status == "under_review"
