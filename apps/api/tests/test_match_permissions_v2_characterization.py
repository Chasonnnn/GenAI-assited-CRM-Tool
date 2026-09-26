"""Characterization of match permissions for organizations on permission policy v2.

Counterpart to the v1 suites test_match_lifecycle_characterization.py and
test_match_approvals_characterization.py. Pins what v2 does now
(docs/match-lifecycle-refactor-plan.md, Permissions (v2)) so step 7's
decide_matches and close_matches actions show up as test diffs. Expected values
come from the current code; do not update them to the planned design in a
behavior-preserving change.

Under v2, role configuration is RolePermission rows, legacy user revokes are
ignored, legacy user grants still add, and Admin/Developer ignore role rows.
"""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.db.enums import Role
from app.db.models import (
    Match,
    MatchAttempt,
    MatchEvent,
    Membership,
    RolePermission,
    Surrogate,
    Task,
    UserPermissionOverride,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.services import pipeline_service, schedule_parser
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import _client_for, _match_row, _other_org


def _activate_v2(db, org_id):
    db.add(OrganizationPermissionPolicy(organization_id=org_id, version=2))
    db.commit()


def _set_role_permission(db, org_id, role: Role, permission: str, granted: bool):
    """Role-level configuration, the only v2 way to change a non-protected role."""
    db.add(
        RolePermission(
            organization_id=org_id,
            role=role.value,
            permission=permission,
            is_granted=granted,
        )
    )
    db.commit()


@pytest.fixture
def v2_org(db, test_auth):
    """The authed developer's organization, on permission policy v2."""
    _activate_v2(db, test_auth.org.id)
    return test_auth.org


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """AI routes share one in-memory limit per client IP; clear it around each test."""
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


def _v2_other_org(db):
    org = _other_org(db)
    _activate_v2(db, org.id)
    return org


async def _ready_surrogate(client, db, org_id) -> dict:
    """Surrogate at ready_to_match, inside the v2 Case Manager post-approval scope."""
    surrogate = await _create_surrogate(client)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "ready_to_match")
    db.get(Surrogate, uuid.UUID(surrogate["id"])).stage_id = stage.id
    db.commit()
    return surrogate


async def _target(client, db, org_id, status="accepted") -> dict:
    """Match ids for a route: a proposed match, or an accepted one with an event and attempt.

    The attempt is completed so the complete route is not refused for an open attempt.
    """
    ip = await _create_intended_parent(client)
    match = await _case(client, ip, surrogate=await _ready_surrogate(client, db, org_id))
    ids = {"id": match["id"], "event_id": uuid.uuid4(), "attempt_id": uuid.uuid4()}
    if status == "proposed":
        return ids
    await _accept(client, match)
    event = await client.post(f"/matches/{match['id']}/events", json=_EVENT)
    assert event.status_code == 201, event.text
    attempt = await client.post(
        f"/matches/{match['id']}/attempts",
        json={"attempt_type": "embryo_transfer", "status": "completed"},
    )
    assert attempt.status_code == 201, attempt.text
    ids.update(event_id=event.json()["id"], attempt_id=attempt.json()["id"])
    return ids


def _state(db, match_id) -> tuple:
    row = _match_row(db, match_id)
    return (
        row.status,
        row.notes,
        db.query(MatchEvent).filter(MatchEvent.match_id == row.id).count(),
        db.query(MatchAttempt).filter(MatchAttempt.match_id == row.id).count(),
    )


def _count(db, model, *org_ids) -> int:
    """Rows in the named organizations only; other workers commit rows elsewhere."""
    return db.query(model).filter(model.organization_id.in_(org_ids)).count()


def _stub_schedule_parser(monkeypatch):
    async def parse(**kwargs):
        return SimpleNamespace(
            proposed_tasks=[],
            warnings=[],
            assumed_timezone="UTC",
            assumed_reference_date=date(2026, 9, 25),
        )

    monkeypatch.setattr(schedule_parser, "parse_schedule_text", parse)


_EVENT = {
    "person_type": "ip",
    "event_type": "legal",
    "title": "Legal consult",
    "starts_at": "2026-10-01T10:00:00Z",
}

# (method, path, body, target status); reads need no particular status.
MATCH_READS = [
    ("GET", "/matches/", None, "accepted"),
    ("GET", "/matches/stats", None, "accepted"),
    ("GET", "/matches/{id}", None, "accepted"),
    ("GET", "/matches/{id}/events", None, "accepted"),
    ("GET", "/matches/{id}/events/{event_id}", None, "accepted"),
    ("GET", "/matches/{id}/attempts", None, "accepted"),
]

# (method, path, body, target status, success code, match status after success)
MATCH_WRITES = [
    ("PUT", "/matches/{id}/accept", {}, "proposed", 200, "accepted"),
    ("PUT", "/matches/{id}/reject", {"rejection_reason": "No"}, "proposed", 200, "rejected"),
    ("DELETE", "/matches/{id}", None, "proposed", 204, "cancelled"),
    ("PATCH", "/matches/{id}/notes", {"notes": "Changed"}, "proposed", 200, "proposed"),
    ("POST", "/matches/{id}/cancel-request", {}, "accepted", 200, "cancel_pending"),
    ("PUT", "/matches/{id}/complete", {"outcome": "Done"}, "accepted", 200, "completed"),
    ("POST", "/matches/{id}/events", _EVENT, "accepted", 201, "accepted"),
    ("PUT", "/matches/{id}/events/{event_id}", {"title": "Moved"}, "accepted", 200, "accepted"),
    ("DELETE", "/matches/{id}/events/{event_id}", None, "accepted", 204, "accepted"),
    ("POST", "/matches/{id}/attempts", {"attempt_type": "other"}, "accepted", 201, "accepted"),
    (
        "PATCH",
        "/matches/{id}/attempts/{attempt_id}",
        {"outcome": "Updated"},
        "accepted",
        200,
        "accepted",
    ),
]

AI_ROUTES = [
    ("POST", "/ai/create-bulk-tasks", "bulk"),
    ("POST", "/ai/parse-schedule", "parse"),
    ("POST", "/ai/parse-schedule/stream", "parse"),
]


def _write_id(route) -> str:
    return f"{route[0]} {route[1]}"


def _ai_body(kind, match_id) -> dict:
    if kind == "bulk":
        return {
            "request_id": str(uuid.uuid4()),
            "match_id": str(match_id),
            "tasks": [{"title": "Schedule consult"}],
        }
    return {"text": "Consult tomorrow", "match_id": str(match_id)}


async def _propose(client, authed_client, db, org_id):
    surrogate = await _ready_surrogate(authed_client, db, org_id)
    ip = await _create_intended_parent(authed_client)
    return await client.post(
        "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    )


# =============================================================================
# Allowed under v2 role defaults
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.OPERATIONS, Role.ADMIN, Role.DEVELOPER])
@pytest.mark.parametrize("method,path,body,status", MATCH_READS)
async def test_v2_roles_with_view_matches_can_read_every_match_route(
    authed_client, db, v2_org, role, method, path, body, status
):
    ids = await _target(authed_client, db, v2_org.id, status)
    before = _state(db, ids["id"])

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == 200, response.text
    assert _state(db, ids["id"]) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER])
@pytest.mark.parametrize(
    "method,path,body,status,code,after", MATCH_WRITES, ids=[_write_id(r) for r in MATCH_WRITES]
)
async def test_v2_roles_with_propose_matches_can_run_every_match_mutation(
    authed_client, db, v2_org, role, method, path, body, status, code, after
):
    ids = await _target(authed_client, db, v2_org.id, status)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == code, response.text
    assert _match_row(db, ids["id"]).status == after


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER])
async def test_v2_roles_with_propose_matches_can_propose(authed_client, db, v2_org, role):
    async with _client_for(db, v2_org.id, role=role) as (user, client):
        response = await _propose(client, authed_client, db, v2_org.id)

    assert response.status_code == 201, response.text
    assert response.json()["proposed_by_user_id"] == str(user.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.OPERATIONS, Role.ADMIN])
async def test_v2_match_list_and_stats_include_scoped_match(authed_client, db, v2_org, role):
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        listed = await client.get("/matches/")
        stats = await client.get("/matches/stats")

    assert ids["id"] in {item["id"] for item in listed.json()["items"]}
    assert stats.json()["by_status"]["accepted"] >= 1


# =============================================================================
# Denied under v2 role defaults and role-level configuration
# =============================================================================

_ALL_MATCH_ROUTES = [
    *(route for route in MATCH_READS),
    *((method, path, body, status) for method, path, body, status, _code, _after in MATCH_WRITES),
    ("POST", "/matches/", "propose", "accepted"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", ["intake_default", "case_manager_role_denied"])
@pytest.mark.parametrize("method,path,body,status", _ALL_MATCH_ROUTES)
async def test_v2_role_without_view_matches_is_denied_every_match_route(
    authed_client, db, v2_org, configured, method, path, body, status
):
    ids = await _target(authed_client, db, v2_org.id, status)
    if body == "propose":
        surrogate = await _ready_surrogate(authed_client, db, v2_org.id)
        ip = await _create_intended_parent(authed_client)
        body = {"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    role = Role.INTAKE_SPECIALIST
    if configured == "case_manager_role_denied":
        role = Role.CASE_MANAGER
        _set_role_permission(db, v2_org.id, role, "view_matches", False)
    before = _state(db, ids["id"])
    count = _count(db, Match, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_matches"
    assert _state(db, ids["id"]) == before
    assert _count(db, Match, v2_org.id) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", ["operations_default", "case_manager_role_denied"])
@pytest.mark.parametrize(
    "method,path,body,status,code,after", MATCH_WRITES, ids=[_write_id(r) for r in MATCH_WRITES]
)
async def test_v2_role_without_propose_matches_is_denied_every_mutation(
    authed_client, db, v2_org, configured, method, path, body, status, code, after
):
    ids = await _target(authed_client, db, v2_org.id, status)
    role = Role.OPERATIONS
    if configured == "case_manager_role_denied":
        role = Role.CASE_MANAGER
        _set_role_permission(db, v2_org.id, role, "propose_matches", False)
    before = _state(db, ids["id"])

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: propose_matches"
    assert _state(db, ids["id"]) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", ["operations_default", "case_manager_role_denied"])
async def test_v2_role_without_propose_matches_cannot_propose(
    authed_client, db, v2_org, configured
):
    role = Role.OPERATIONS
    if configured == "case_manager_role_denied":
        role = Role.CASE_MANAGER
        _set_role_permission(db, v2_org.id, role, "propose_matches", False)
    count = _count(db, Match, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await _propose(client, authed_client, db, v2_org.id)

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: propose_matches"
    assert _count(db, Match, v2_org.id) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body,status", MATCH_READS)
async def test_v2_role_denied_propose_matches_still_reads(
    authed_client, db, v2_org, method, path, body, status
):
    ids = await _target(authed_client, db, v2_org.id, status)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "propose_matches", False)

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == 200, response.text


# =============================================================================
# Legacy user overrides and protected roles under v2
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body,status,code,after", MATCH_WRITES, ids=[_write_id(r) for r in MATCH_WRITES]
)
async def test_v2_ignores_legacy_user_revoke_of_match_permissions(
    authed_client, db, v2_org, method, path, body, status, code, after
):
    ids = await _target(authed_client, db, v2_org.id, status)

    async with _client_for(
        db, v2_org.id, role=Role.CASE_MANAGER, revoke=("view_matches", "propose_matches")
    ) as (user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == code, response.text
    assert _match_row(db, ids["id"]).status == after
    assert db.query(UserPermissionOverride).filter_by(user_id=user.id).count() == 2


@pytest.mark.asyncio
async def test_v2_ignores_legacy_user_revoke_for_propose_and_detail(authed_client, db, v2_org):
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(
        db, v2_org.id, role=Role.CASE_MANAGER, revoke=("view_matches", "propose_matches")
    ) as (_user, client):
        detail = await client.get(f"/matches/{ids['id']}")
        proposed = await _propose(client, authed_client, db, v2_org.id)

    assert detail.status_code == 200, detail.text
    assert proposed.status_code == 201, proposed.text


@pytest.mark.asyncio
@pytest.mark.parametrize("granted_by", ["legacy_user_grant", "role_grant"])
async def test_v2_operations_granted_propose_matches_can_edit_but_not_accept(
    authed_client, db, v2_org, granted_by
):
    # Accept moves the surrogate stage, which v2 checks against change_surrogate_status.
    ids = await _target(authed_client, db, v2_org.id, "proposed")
    grant = ("propose_matches",) if granted_by == "legacy_user_grant" else ()
    if granted_by == "role_grant":
        _set_role_permission(db, v2_org.id, Role.OPERATIONS, "propose_matches", True)

    async with _client_for(db, v2_org.id, role=Role.OPERATIONS, grant=grant) as (_user, client):
        notes = await client.patch(f"/matches/{ids['id']}/notes", json={"notes": "Granted"})
        accept = await client.put(f"/matches/{ids['id']}/accept", json={})

    assert notes.status_code == 200, notes.text
    assert accept.status_code == 400
    assert accept.json()["detail"] == "Stage change permission required"
    row = _match_row(db, ids["id"])
    assert (row.status, row.notes) == ("proposed", "Granted")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_v2_protected_roles_ignore_role_level_denials(authed_client, db, v2_org, role):
    ids = await _target(authed_client, db, v2_org.id, "proposed")
    for permission in ("view_matches", "propose_matches"):
        _set_role_permission(db, v2_org.id, role, permission, False)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        detail = await client.get(f"/matches/{ids['id']}")
        accepted = await client.put(f"/matches/{ids['id']}/accept", json={})

    assert detail.status_code == 200, detail.text
    assert accepted.status_code == 200, accepted.text


# =============================================================================
# v2 record scope on match parties
# =============================================================================


@pytest.mark.asyncio
async def test_v2_case_manager_cannot_reach_match_with_pre_approval_surrogate(
    authed_client, db, v2_org
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        accept = await client.put(f"/matches/{created['id']}/accept", json={})
        listed = await client.get("/matches/")

    for response in (detail, accept):
        assert response.status_code == 403
        assert response.json()["detail"] == "You don't have access to this surrogate"
    assert created["id"] not in {item["id"] for item in listed.json()["items"]}
    assert _match_row(db, created["id"]).status == "proposed"


@pytest.mark.asyncio
async def test_v2_case_manager_cannot_reach_match_with_pre_approval_donor(
    authed_client, db, v2_org
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=await _donor(authed_client))

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")

    assert detail.status_code == 403
    assert detail.json()["detail"] == "You don't have access to this donor"


@pytest.mark.asyncio
async def test_v2_intake_granted_view_matches_is_stopped_by_intended_parent_scope(
    authed_client, db, v2_org
):
    ids = await _target(authed_client, db, v2_org.id)
    _set_role_permission(db, v2_org.id, Role.INTAKE_SPECIALIST, "view_matches", True)
    _set_role_permission(db, v2_org.id, Role.INTAKE_SPECIALIST, "view_intended_parents", True)

    async with _client_for(db, v2_org.id, role=Role.INTAKE_SPECIALIST) as (_user, client):
        response = await client.get(f"/matches/{ids['id']}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have access to this intended_parent"


# =============================================================================
# AI match routes
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER])
async def test_v2_ai_bulk_tasks_allowed_for_roles_with_view_matches_and_create_tasks(
    authed_client, db, v2_org, role
):
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (user, client):
        response = await client.post("/ai/create-bulk-tasks", json=_ai_body("bulk", ids["id"]))

    assert response.status_code == 200, response.text
    assert db.query(Task).filter(Task.created_by_user_id == user.id).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/ai/parse-schedule", "/ai/parse-schedule/stream"])
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.OPERATIONS, Role.ADMIN, Role.DEVELOPER])
async def test_v2_ai_parse_schedule_allowed_for_roles_with_view_matches(
    authed_client, db, v2_org, monkeypatch, role, path
):
    _stub_schedule_parser(monkeypatch)
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.post(path, json=_ai_body("parse", ids["id"]))

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_v2_ai_bulk_tasks_denied_for_operations_before_match_access(
    authed_client, db, v2_org
):
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(db, v2_org.id, role=Role.OPERATIONS) as (user, client):
        response = await client.post("/ai/create-bulk-tasks", json=_ai_body("bulk", ids["id"]))
        missing = await client.post("/ai/create-bulk-tasks", json=_ai_body("bulk", uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: create_tasks"
    assert missing.json()["detail"] == "Missing permission: create_tasks"
    assert db.query(Task).filter(Task.created_by_user_id == user.id).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kind", AI_ROUTES)
@pytest.mark.parametrize("configured", ["intake_default", "case_manager_role_denied"])
async def test_v2_ai_routes_require_view_matches(
    authed_client, db, v2_org, configured, method, path, kind
):
    ids = await _target(authed_client, db, v2_org.id)
    role = Role.INTAKE_SPECIALIST
    if configured == "case_manager_role_denied":
        role = Role.CASE_MANAGER
        _set_role_permission(db, v2_org.id, role, "view_matches", False)
    count = _count(db, Task, v2_org.id)

    async with _client_for(db, v2_org.id, role=role) as (_user, client):
        response = await client.request(method, path, json=_ai_body(kind, ids["id"]))
        missing = await client.request(method, path, json=_ai_body(kind, uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_matches"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Match not found"
    assert _count(db, Task, v2_org.id) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kind", AI_ROUTES)
async def test_v2_ai_routes_ignore_legacy_user_revoke_of_view_matches(
    authed_client, db, v2_org, monkeypatch, method, path, kind
):
    _stub_schedule_parser(monkeypatch)
    ids = await _target(authed_client, db, v2_org.id)

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER, revoke=("view_matches",)) as (
        _user,
        client,
    ):
        response = await client.request(method, path, json=_ai_body(kind, ids["id"]))

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kind", AI_ROUTES)
async def test_v2_ai_routes_apply_party_record_scope(authed_client, db, v2_org, method, path, kind):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    count = _count(db, Task, v2_org.id)

    async with _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_user, client):
        response = await client.request(method, path, json=_ai_body(kind, created["id"]))

    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have access to this surrogate"
    assert _count(db, Task, v2_org.id) == count


# =============================================================================
# Cross-organization isolation (v2 requester)
# =============================================================================

_CROSS_ORG_ROUTES = [
    *((method, path, body) for method, path, body, _status in MATCH_READS[2:]),
    *((method, path, body) for method, path, body, _s, _c, _a in MATCH_WRITES),
    *((method, path, kind) for method, path, kind in AI_ROUTES),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,owner_version", [(Role.ADMIN, 2), (Role.CASE_MANAGER, 2), (Role.ADMIN, 1)]
)
@pytest.mark.parametrize("method,path,body", _CROSS_ORG_ROUTES)
async def test_v2_other_org_user_gets_404_for_every_match_route(
    authed_client, db, test_auth, role, owner_version, method, path, body
):
    if owner_version == 2:
        _activate_v2(db, test_auth.org.id)
    ids = await _target(authed_client, db, test_auth.org.id)
    if body in ("bulk", "parse"):
        body = _ai_body(body, ids["id"])
    before = _state(db, ids["id"])
    other_org = _v2_other_org(db)
    count = _count(db, Task, test_auth.org.id, other_org.id)

    async with _client_for(db, other_org.id, role=role) as (_user, client):
        response = await client.request(method, path.format(**ids), json=body)

    assert response.status_code == 404
    assert response.json()["detail"] == "Match not found"
    assert _state(db, ids["id"]) == before
    assert _count(db, Task, test_auth.org.id, other_org.id) == count


@pytest.mark.asyncio
async def test_v2_other_org_user_cannot_propose_with_foreign_parties(authed_client, db, v2_org):
    surrogate = await _ready_surrogate(authed_client, db, v2_org.id)
    ip = await _create_intended_parent(authed_client)
    other_org = _v2_other_org(db)
    count = _count(db, Match, v2_org.id, other_org.id)

    async with _client_for(db, other_org.id, role=Role.CASE_MANAGER) as (_user, client):
        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Surrogate not found"
    assert _count(db, Match, v2_org.id, other_org.id) == count


@pytest.mark.asyncio
async def test_v2_other_org_match_list_and_stats_exclude_foreign_matches(authed_client, db, v2_org):
    await _target(authed_client, db, v2_org.id)

    async with _client_for(db, _v2_other_org(db).id) as (_user, client):
        listed = await client.get("/matches/")
        stats = await client.get("/matches/stats")

    assert listed.json()["total"] == 0
    assert stats.json()["total"] == 0


# =============================================================================
# Mixed: v1 and v2 organizations in one database
# =============================================================================


@pytest.mark.asyncio
async def test_one_user_cannot_be_member_of_a_v1_and_a_v2_org(db, test_auth):
    # memberships.user_id is unique, so resolution cannot differ per org for one user.
    from sqlalchemy.exc import IntegrityError

    v2_org = _v2_other_org(db)

    with pytest.raises(IntegrityError, match="memberships_user_id_key"), db.begin_nested():
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=test_auth.user.id,
                organization_id=v2_org.id,
                role=Role.CASE_MANAGER.value,
                is_active=True,
            )
        )
        db.flush()


async def _mixed_orgs(authed_client, db, test_auth, status="accepted"):
    """A v1 org (the authed org) and a v2 org, each with one match; returns (v2_org, ids)."""
    v1_ids = await _target(authed_client, db, test_auth.org.id, status)
    v2_org = _v2_other_org(db)
    async with _client_for(db, v2_org.id, role=Role.DEVELOPER) as (_dev, developer):
        v2_ids = await _target(developer, db, v2_org.id, status)
    return v2_org, v1_ids, v2_ids


@pytest.mark.asyncio
async def test_mixed_orgs_legacy_revoke_follows_session_org(authed_client, db, test_auth):
    v2_org, v1_ids, v2_ids = await _mixed_orgs(authed_client, db, test_auth)
    revoke = ("propose_matches",)

    async with (
        _client_for(db, test_auth.org.id, role=Role.CASE_MANAGER, revoke=revoke) as (_a, v1),
        _client_for(db, v2_org.id, role=Role.CASE_MANAGER, revoke=revoke) as (_b, v2),
    ):
        v1_notes = await v1.patch(f"/matches/{v1_ids['id']}/notes", json={"notes": "v1"})
        v2_notes = await v2.patch(f"/matches/{v2_ids['id']}/notes", json={"notes": "v2"})
        v2_to_v1 = await v2.get(f"/matches/{v1_ids['id']}")
        v1_to_v2 = await v1.get(f"/matches/{v2_ids['id']}")

    assert v1_notes.status_code == 403
    assert v1_notes.json()["detail"] == "Missing permission: propose_matches"
    assert v2_notes.status_code == 200, v2_notes.text
    assert _match_row(db, v1_ids["id"]).notes != "v1"
    assert _match_row(db, v2_ids["id"]).notes == "v2"
    for response in (v2_to_v1, v1_to_v2):
        assert response.status_code == 404
        assert response.json()["detail"] == "Match not found"


@pytest.mark.asyncio
async def test_mixed_orgs_role_defaults_follow_session_org_version(authed_client, db, test_auth):
    # Operations has view_matches only under v2 defaults; v1 Operations has no match access.
    v2_org, v1_ids, v2_ids = await _mixed_orgs(authed_client, db, test_auth)

    async with (
        _client_for(db, test_auth.org.id, role=Role.OPERATIONS) as (_a, v1),
        _client_for(db, v2_org.id, role=Role.OPERATIONS) as (_b, v2),
    ):
        v1_detail = await v1.get(f"/matches/{v1_ids['id']}")
        v2_detail = await v2.get(f"/matches/{v2_ids['id']}")

    assert v1_detail.status_code == 403
    assert v1_detail.json()["detail"] == "Missing permission: view_matches"
    assert v2_detail.status_code == 200, v2_detail.text


@pytest.mark.asyncio
async def test_mixed_orgs_role_denial_stays_in_its_org(authed_client, db, test_auth):
    v2_org, v1_ids, v2_ids = await _mixed_orgs(authed_client, db, test_auth)
    _set_role_permission(db, v2_org.id, Role.CASE_MANAGER, "view_matches", False)

    async with (
        _client_for(db, test_auth.org.id, role=Role.CASE_MANAGER) as (_a, v1),
        _client_for(db, v2_org.id, role=Role.CASE_MANAGER) as (_b, v2),
    ):
        v1_detail = await v1.get(f"/matches/{v1_ids['id']}")
        v2_detail = await v2.get(f"/matches/{v2_ids['id']}")

    assert v1_detail.status_code == 200, v1_detail.text
    assert v2_detail.status_code == 403
    assert v2_detail.json()["detail"] == "Missing permission: view_matches"
