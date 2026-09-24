"""Characterization of the current match lifecycle.

Pins observable behavior before the match engine refactor
(docs/match-lifecycle-refactor-plan.md, step 2). Expected values come from the
current code; do not update them to the planned design in a behavior-preserving
change.
"""

import re
import uuid
from collections import Counter
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    AuditLog,
    Donor,
    DonorStatusHistory,
    EntityActivityLog,
    IntendedParent,
    IntendedParentStatusHistory,
    Match,
    Membership,
    StatusChangeRequest,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import (
    dashboard_service,
    match_service,
    notification_service,
    session_service,
    workflow_triggers,
)
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor


@asynccontextmanager
async def _client_for(db, org_id, *, role=Role.ADMIN, revoke=(), grant=()):
    """Authenticated client for a new member of org_id with optional overrides."""
    user = User(
        id=uuid.uuid4(),
        email=f"match-char-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Match Characterization User",
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
            role=role.value,
            is_active=True,
        )
    )
    for override_type, permissions in (("revoke", revoke), ("grant", grant)):
        for permission in permissions:
            db.add(
                UserPermissionOverride(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    user_id=user.id,
                    permission=permission,
                    override_type=override_type,
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

    previous = app.dependency_overrides.get(get_db)
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
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


def _other_org(db):
    from app.db.models import Organization

    org = Organization(
        id=uuid.uuid4(),
        name="Other Match Org",
        slug=f"other-match-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


def _history(db, org_id) -> dict[str, Counter]:
    """Count history rows in an org; rows are append-only, so diffs isolate one action."""
    return {
        "audit": Counter(
            (row.event_type, row.target_type)
            for row in db.query(AuditLog.event_type, AuditLog.target_type).filter(
                AuditLog.organization_id == org_id
            )
        ),
        "surrogate_activity": Counter(
            row.activity_type
            for row in db.query(SurrogateActivityLog.activity_type).filter(
                SurrogateActivityLog.organization_id == org_id
            )
        ),
        "entity_activity": Counter(
            ("intended_parent" if row.intended_parent_id else "donor", row.activity_type)
            for row in db.query(
                EntityActivityLog.intended_parent_id, EntityActivityLog.activity_type
            ).filter(EntityActivityLog.organization_id == org_id)
        ),
        "stage_history": Counter(
            {
                "surrogate": db.query(SurrogateStatusHistory)
                .filter(SurrogateStatusHistory.organization_id == org_id)
                .count(),
                "intended_parent": db.query(IntendedParentStatusHistory)
                .filter(IntendedParentStatusHistory.organization_id == org_id)
                .count(),
                "donor": db.query(DonorStatusHistory)
                .filter(DonorStatusHistory.organization_id == org_id)
                .count(),
            }
        ),
    }


def _diff(before: dict[str, Counter], after: dict[str, Counter]) -> dict[str, dict]:
    return {key: dict(after[key] - before[key]) for key in before}


@contextmanager
def _locked_tables(db):
    """Record the table of every SELECT ... FOR UPDATE, in execution order."""
    locked: list[str] = []
    connection = db.connection()

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement:
            match = re.search(r"\bFROM\s+(\w+)", statement)
            locked.append(match.group(1) if match else statement)

    event.listen(connection, "before_cursor_execute", before_cursor_execute)
    try:
        yield locked
    finally:
        event.remove(connection, "before_cursor_execute", before_cursor_execute)


class _Spy:
    """Record calls to a module function, optionally delegating or raising."""

    def __init__(
        self,
        original=None,
        *,
        error: Exception | None = None,
        events: list[str] | None = None,
        name: str = "",
    ):
        self.original = original
        self.error = error
        self.events = events
        self.name = name
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.events is not None:
            self.events.append(self.name)
        if self.error is not None:
            raise self.error
        if self.original is not None:
            return self.original(*args, **kwargs)
        return None


def _spy_effects(monkeypatch) -> dict[str, _Spy]:
    """Spy on the after-commit effects the match router and service call."""
    spies = {
        "trigger_match_proposed": _Spy(),
        "trigger_match_accepted": _Spy(),
        "trigger_match_rejected": _Spy(),
        "push_dashboard_stats": _Spy(),
        "notify_match_cancel_request_pending": _Spy(),
        "notify_match_cancel_request_resolved": _Spy(),
    }
    for name in ("trigger_match_proposed", "trigger_match_accepted", "trigger_match_rejected"):
        monkeypatch.setattr(workflow_triggers, name, spies[name])
    monkeypatch.setattr(dashboard_service, "push_dashboard_stats", spies["push_dashboard_stats"])
    for name in ("notify_match_cancel_request_pending", "notify_match_cancel_request_resolved"):
        monkeypatch.setattr(notification_service, name, spies[name])
    return spies


def _reset(spies: dict[str, _Spy]) -> None:
    for spy in spies.values():
        spy.calls.clear()


def _call_counts(spies: dict[str, _Spy]) -> dict[str, int]:
    return {name: len(spy.calls) for name, spy in spies.items() if spy.calls}


def _snapshot(db, org_id):
    db.expire_all()
    return _history(db, org_id)


def _stage_slug(db, model, entity_id) -> str:
    db.expire_all()
    return db.get(model, uuid.UUID(str(entity_id))).stage.slug


def _ip_stage_key(db, ip_id) -> str:
    db.expire_all()
    ip = db.get(IntendedParent, uuid.UUID(str(ip_id)))
    return ip.status


def _match_row(db, match_id) -> Match:
    db.expire_all()
    return db.get(Match, uuid.UUID(str(match_id)))


def _insert_proposed_match(db, org_id, user_id, surrogate_id, intended_parent_id) -> Match:
    """Create a proposed match the API would refuse, to reach service-level guards."""
    match = Match(
        organization_id=org_id,
        match_number=match_service.generate_match_number(db, org_id),
        surrogate_id=uuid.UUID(str(surrogate_id)),
        intended_parent_id=uuid.UUID(str(intended_parent_id)),
        match_kind="surrogate",
        status="proposed",
        proposed_by_user_id=user_id,
    )
    db.add(match)
    db.commit()
    return match


def _set_reviewing(db, match_id):
    """Put a match in the legacy reviewing status; no request writes it any more."""
    row = _match_row(db, match_id)
    row.status = "reviewing"
    db.commit()


async def _enter_status(db, org_id, match, status):
    """Leave a match proposed, or store the legacy reviewing status."""
    if status == "reviewing":
        _set_reviewing(db, match["id"])
    assert _match_row(db, match["id"]).status == status


async def _request_cancel(client, match, reason=None):
    body = {} if reason is None else {"reason": reason}
    response = await client.post(f"/matches/{match['id']}/cancel-request", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# =============================================================================
# Propose
# =============================================================================


@pytest.mark.asyncio
async def test_propose_surrogate_match_writes_proposed_status_history_and_trigger(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    surrogate_stage = _stage_slug(db, Surrogate, surrogate["id"])
    ip_stage = _ip_stage_key(db, ip["id"])
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)
    with _locked_tables(db) as locks:
        created = await _case(authed_client, ip, surrogate=surrogate)

    assert created["status"] == "proposed"
    assert created["match_kind"] == "surrogate"
    assert re.fullmatch(r"M\d{5}", created["match_number"])
    assert created["proposed_by_user_id"] == str(test_auth.user.id)
    assert created["reviewed_by_user_id"] is None
    assert created["reviewed_at"] is None
    assert created["closed_at"] is None
    assert locks == []
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_proposed", "match"): 1},
        "surrogate_activity": {"match_proposed": 1},
        "entity_activity": {("intended_parent", "match_proposed"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {"trigger_match_proposed": 1}
    assert spies["trigger_match_proposed"].calls[0][0][1].id == uuid.UUID(created["id"])
    assert _stage_slug(db, Surrogate, surrogate["id"]) == surrogate_stage
    assert _ip_stage_key(db, ip["id"]) == ip_stage


@pytest.mark.asyncio
async def test_propose_donor_match_writes_proposed_status_without_workflow_trigger(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)
    created = await _case(authed_client, ip, donor=donor)

    assert created["status"] == "proposed"
    assert created["match_kind"] == "donor"
    assert created["surrogate_id"] is None
    assert created["donor_id"] == donor["id"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_proposed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_proposed"): 1,
            ("intended_parent", "match_proposed"): 1,
        },
        "stage_history": {},
    }
    assert _call_counts(spies) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_status", ["proposed", "reviewing", "accepted", "cancel_pending"])
async def test_repeat_proposal_for_open_surrogate_pair_returns_409(
    authed_client, db, test_auth, existing_status
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    if existing_status == "reviewing":
        _set_reviewing(db, created["id"])
    if existing_status in ("accepted", "cancel_pending"):
        await _accept(authed_client, created)
    if existing_status == "cancel_pending":
        await _request_cancel(authed_client, created)
    assert _match_row(db, created["id"]).status == existing_status
    count = db.query(Match).count()

    response = await authed_client.post(
        "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == f"Match already exists with status: {existing_status}"
    assert db.query(Match).count() == count


@pytest.mark.asyncio
@pytest.mark.parametrize("closed_by", ["reject", "cancel"])
async def test_repeat_proposal_after_closed_surrogate_pair_creates_new_match(
    authed_client, db, closed_by
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    first = await _case(authed_client, ip, surrogate=surrogate)
    if closed_by == "reject":
        response = await authed_client.put(
            f"/matches/{first['id']}/reject", json={"rejection_reason": "Not now"}
        )
        assert response.status_code == 200
    else:
        assert (await authed_client.delete(f"/matches/{first['id']}")).status_code == 204

    repeat = await _case(authed_client, ip, surrogate=surrogate)

    assert repeat["id"] != first["id"]
    assert repeat["status"] == "proposed"
    assert repeat["match_number"] != first["match_number"]


@pytest.mark.asyncio
@pytest.mark.parametrize("committed_status", ["accepted", "cancel_pending"])
async def test_propose_for_surrogate_with_committed_match_returns_400(
    authed_client, db, committed_status
):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    first = await _accept(authed_client, await _case(authed_client, first_ip, surrogate=surrogate))
    if committed_status == "cancel_pending":
        await _request_cancel(authed_client, first)
    count = db.query(Match).count()

    response = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate["id"], "intended_parent_id": second_ip["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Surrogate already has an accepted match"
    assert db.query(Match).count() == count


@pytest.mark.asyncio
async def test_propose_accepts_parties_at_any_stage(authed_client, db):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "new_unread"
    assert _ip_stage_key(db, ip["id"]) == "new"

    created = await _case(authed_client, ip, surrogate=surrogate)

    assert created["status"] == "proposed"


# =============================================================================
# View (GET never writes status or activity)
# =============================================================================


@pytest.mark.asyncio
async def test_get_by_non_proposer_keeps_proposed_status(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    before = _snapshot(db, test_auth.org.id)

    async with _client_for(db, test_auth.org.id) as (_viewer, other):
        with _locked_tables(db) as locks:
            response = await other.get(f"/matches/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "proposed"
    assert response.json()["reviewed_by_user_id"] is None
    row = _match_row(db, created["id"])
    assert row.status == "proposed"
    assert row.reviewed_by_user_id is None
    assert row.reviewed_at is None
    assert locks == []
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("phi_viewed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_get_by_proposer_keeps_proposed_status(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.get(f"/matches/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "proposed"
    assert _match_row(db, created["id"]).reviewed_by_user_id is None
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("phi_viewed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_get_by_non_proposer_keeps_donor_match_proposed(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=await _donor(authed_client))
    before = _snapshot(db, test_auth.org.id)

    async with _client_for(db, test_auth.org.id) as (_viewer, other):
        with _locked_tables(db) as locks:
            response = await other.get(f"/matches/{created['id']}")

    assert response.json()["status"] == "proposed"
    assert locks == []
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("phi_viewed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("current_status", ["reviewing", "accepted"])
async def test_get_by_non_proposer_on_reviewing_or_accepted_match_writes_no_transition(
    authed_client, db, test_auth, current_status
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    async with _client_for(db, test_auth.org.id) as (_viewer, other):
        if current_status == "reviewing":
            _set_reviewing(db, created["id"])
        else:
            await _accept(authed_client, created)
        reviewed_by = _match_row(db, created["id"]).reviewed_by_user_id
        before = _snapshot(db, test_auth.org.id)
        with _locked_tables(db) as locks:
            response = await other.get(f"/matches/{created['id']}")

    assert response.json()["status"] == current_status
    assert _match_row(db, created["id"]).reviewed_by_user_id == reviewed_by
    assert locks == []
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("phi_viewed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_get_by_non_proposer_keeps_proposed_when_a_party_is_archived(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    db.get(Surrogate, uuid.UUID(surrogate["id"])).is_archived = True
    db.commit()

    async with _client_for(db, test_auth.org.id) as (_viewer, other):
        response = await other.get(f"/matches/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "proposed"


# =============================================================================
# Accept
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["proposed", "reviewing"])
async def test_accept_surrogate_match_moves_surrogate_and_ip_to_matched(
    authed_client, db, test_auth, monkeypatch, from_status
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    await _enter_status(db, test_auth.org.id, created, from_status)
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.put(
            f"/matches/{created['id']}/accept", json={"notes": "Accepted by committee"}
        )

    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted["status"] == "accepted"
    assert accepted["reviewed_by_user_id"] == str(test_auth.user.id)
    assert accepted["surrogate_stage_slug"] == "matched"
    assert "Accepted by committee" in accepted["notes"]
    assert accepted["closed_at"] is None
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "matched"
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_accepted", "match"): 1},
        "surrogate_activity": {"match_accepted": 1, "note_added": 1},
        "entity_activity": {("intended_parent", "match_accepted"): 1},
        "stage_history": {"surrogate": 1, "intended_parent": 1},
    }
    assert _call_counts(spies) == {"trigger_match_accepted": 1, "push_dashboard_stats": 1}
    assert spies["push_dashboard_stats"].calls[0][0][1] == test_auth.org.id


@pytest.mark.asyncio
async def test_accept_cancels_other_open_proposals_for_same_surrogate(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    third_ip = await _create_intended_parent(authed_client)
    accepted = await _case(authed_client, first_ip, surrogate=surrogate)
    proposed = await _case(authed_client, second_ip, surrogate=surrogate)
    reviewing = await _case(authed_client, third_ip, surrogate=surrogate)
    _set_reviewing(db, reviewing["id"])
    before = _snapshot(db, test_auth.org.id)

    await _accept(authed_client, accepted)

    for other_id in (proposed["id"], reviewing["id"]):
        row = _match_row(db, other_id)
        assert row.status == "cancelled"
        assert row.closure_reason == "Another match accepted"
        assert row.closed_by_user_id == test_auth.user.id
        assert row.closed_at is not None
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_accepted", "match"): 1, ("match_cancelled", "match"): 2},
        "surrogate_activity": {"match_accepted": 1, "match_cancelled": 2, "note_added": 1},
        "entity_activity": {
            ("intended_parent", "match_accepted"): 1,
            ("intended_parent", "match_cancelled"): 2,
        },
        "stage_history": {"surrogate": 1, "intended_parent": 1},
    }
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type == "match_accepted", AuditLog.target_id == uuid.UUID(accepted["id"])
        )
        .one()
    )
    assert audit.details["cancelled_matches"] == 2


@pytest.mark.asyncio
async def test_accept_with_competing_proposals_locks_each_row_once_in_engine_order(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    accepted = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    competing = [
        await _case(
            authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
        )
        for _ in range(2)
    ]
    statements: list[str] = []
    connection = db.connection()

    def record(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement:
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        await _accept(authed_client, accepted)
    finally:
        event.remove(connection, "before_cursor_execute", record)

    assert [re.search(r"\bFROM\s+(\w+)", sql).group(1) for sql in statements] == [
        "matches",
        "surrogates",
        "intended_parents",
    ]
    assert "ORDER BY matches.id" in statements[0]
    for other in competing:
        assert _match_row(db, other["id"]).status == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("committed_status", ["accepted", "cancel_pending"])
async def test_accept_when_surrogate_has_other_committed_match_returns_400(
    authed_client, db, test_auth, committed_status
):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    first = await _accept(authed_client, await _case(authed_client, first_ip, surrogate=surrogate))
    if committed_status == "cancel_pending":
        await _request_cancel(authed_client, first)
    competing = _insert_proposed_match(
        db, test_auth.org.id, test_auth.user.id, surrogate["id"], second_ip["id"]
    )
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(f"/matches/{competing.id}/accept", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Surrogate already has an accepted match"
    assert _match_row(db, competing.id).status == "proposed"
    assert _match_row(db, first["id"]).status == committed_status
    assert _ip_stage_key(db, second_ip["id"]) == "new"
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("api_mutation_fallback", "api_route"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_accept_when_ip_already_matched_leaves_ip_stage_unchanged(
    authed_client, db, test_auth
):
    ip = await _create_intended_parent(authed_client)
    await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    second_surrogate = await _create_surrogate(authed_client)
    second = await _case(authed_client, ip, surrogate=second_surrogate)
    before = _snapshot(db, test_auth.org.id)

    accepted = await _accept(authed_client, second)

    assert accepted["status"] == "accepted"
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert _stage_slug(db, Surrogate, second_surrogate["id"]) == "matched"
    assert _diff(before, _snapshot(db, test_auth.org.id))["stage_history"] == {"surrogate": 1}


def _move_ip_to_stage(db, org_id, ip_id, stage_key):
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, entity_type="intended_parent"
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    ip = db.get(IntendedParent, uuid.UUID(str(ip_id)))
    ip.stage_id = stage.id
    ip.status = stage.stage_key
    db.commit()


@pytest.mark.asyncio
async def test_accept_when_ip_beyond_matched_preserves_ip_stage(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    _move_ip_to_stage(db, test_auth.org.id, ip["id"], "delivered")
    before = _snapshot(db, test_auth.org.id)

    accepted = await _accept(authed_client, created)

    assert accepted["status"] == "accepted"
    assert _ip_stage_key(db, ip["id"]) == "delivered"
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "matched"
    assert _diff(before, _snapshot(db, test_auth.org.id))["stage_history"] == {"surrogate": 1}


@pytest.mark.asyncio
async def test_accept_donor_match_moves_ip_but_not_donor_stage(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=donor)
    donor_stage = _stage_slug(db, Donor, donor["id"])
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        accepted = await _accept(authed_client, created)

    assert accepted["status"] == "accepted"
    assert _stage_slug(db, Donor, donor["id"]) == donor_stage
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert locks == ["matches", "donors", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_accepted", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_accepted"): 1,
            ("intended_parent", "match_accepted"): 1,
        },
        "stage_history": {"intended_parent": 1},
    }
    assert _call_counts(spies) == {"push_dashboard_stats": 1}


@pytest.mark.asyncio
async def test_accept_donor_match_keeps_other_open_donor_proposals(authed_client, db):
    donor = await _donor(authed_client)
    first = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    second = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)

    await _accept(authed_client, first)

    assert _match_row(db, second["id"]).status == "proposed"


@pytest.mark.asyncio
@pytest.mark.parametrize("current_status", ["rejected", "cancelled", "cancel_pending", "completed"])
async def test_accept_match_outside_proposed_or_reviewing_returns_400(
    authed_client, db, current_status
):
    ip = await _create_intended_parent(authed_client)
    if current_status == "completed":
        created = await _case(authed_client, ip, donor=await _donor(authed_client))
    else:
        created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if current_status == "rejected":
        await authed_client.put(f"/matches/{created['id']}/reject", json={"rejection_reason": "No"})
    elif current_status == "cancelled":
        await authed_client.delete(f"/matches/{created['id']}")
    else:
        await _accept(authed_client, created)
        if current_status == "cancel_pending":
            await _request_cancel(authed_client, created)
        else:
            response = await authed_client.put(
                f"/matches/{created['id']}/complete", json={"outcome": "Done"}
            )
            assert response.status_code == 200
    assert _match_row(db, created["id"]).status == current_status

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == f"Cannot accept match with status: {current_status}"
    assert _match_row(db, created["id"]).status == current_status


# =============================================================================
# Reject
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["proposed", "reviewing"])
async def test_reject_surrogate_match_writes_rejected_status_without_stage_changes(
    authed_client, db, test_auth, monkeypatch, from_status
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    await _enter_status(db, test_auth.org.id, created, from_status)
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.put(
            f"/matches/{created['id']}/reject",
            json={"rejection_reason": "Not compatible", "notes": "Discussed"},
        )

    assert response.status_code == 200, response.text
    rejected = response.json()
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Not compatible"
    assert rejected["closure_reason"] == "Not compatible"
    assert rejected["reviewed_by_user_id"] == str(test_auth.user.id)
    assert rejected["closed_at"] is not None
    assert "Discussed" in rejected["notes"]
    row = _match_row(db, created["id"])
    assert row.closed_by_user_id == test_auth.user.id
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "new_unread"
    assert _ip_stage_key(db, ip["id"]) == "new"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_rejected", "match"): 1},
        "surrogate_activity": {"match_rejected": 1},
        "entity_activity": {("intended_parent", "match_rejected"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {"trigger_match_rejected": 1}


@pytest.mark.asyncio
async def test_reject_by_non_proposer_is_allowed(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id) as (viewer, other):
        response = await other.put(
            f"/matches/{created['id']}/reject", json={"rejection_reason": "No"}
        )

    assert response.status_code == 200
    assert _match_row(db, created["id"]).closed_by_user_id == viewer.id


@pytest.mark.asyncio
async def test_reject_donor_match_fires_no_workflow_trigger(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=await _donor(authed_client))
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(
        f"/matches/{created['id']}/reject", json={"rejection_reason": "No"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert _call_counts(spies) == {}
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_rejected", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_rejected"): 1,
            ("intended_parent", "match_rejected"): 1,
        },
        "stage_history": {},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"rejection_reason": ""}, {"rejection_reason": None}])
async def test_reject_requires_non_empty_reason(authed_client, db, body):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    response = await authed_client.put(f"/matches/{created['id']}/reject", json=body)

    assert response.status_code == 422
    assert _match_row(db, created["id"]).status == "proposed"


@pytest.mark.asyncio
async def test_reject_accepts_whitespace_only_reason(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    response = await authed_client.put(
        f"/matches/{created['id']}/reject", json={"rejection_reason": "   "}
    )

    assert response.status_code == 200
    assert response.json()["rejection_reason"] == "   "


@pytest.mark.asyncio
async def test_reject_accepted_match_returns_400(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )

    response = await authed_client.put(
        f"/matches/{created['id']}/reject", json={"rejection_reason": "No"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot reject match with status: accepted"


# =============================================================================
# Cancel (DELETE, before acceptance)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("current_status", ["proposed", "reviewing"])
async def test_cancel_open_proposal_writes_cancelled_status(
    authed_client, db, test_auth, monkeypatch, current_status
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    if current_status == "reviewing":
        _set_reviewing(db, created["id"])
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.delete(f"/matches/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    row = _match_row(db, created["id"])
    assert row.status == "cancelled"
    assert row.closed_by_user_id == test_auth.user.id
    assert row.closed_at is not None
    assert row.closure_reason is None
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "new_unread"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_cancelled", "match"): 1},
        "surrogate_activity": {"match_cancelled": 1},
        "entity_activity": {("intended_parent", "match_cancelled"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {}


@pytest.mark.asyncio
async def test_cancel_accepted_match_returns_400(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )

    response = await authed_client.delete(f"/matches/{created['id']}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot cancel match with status: accepted"
    assert _match_row(db, created["id"]).status == "accepted"


# =============================================================================
# Cancellation request (accepted matches)
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_request_sets_cancel_pending_and_notifies(
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
    assert response.json()["status"] == "cancel_pending"
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
async def test_cancel_request_without_reason_stores_empty_reason(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )

    await _request_cancel(authed_client, created)

    request = (
        db.query(StatusChangeRequest)
        .filter(StatusChangeRequest.entity_id == uuid.UUID(created["id"]))
        .one()
    )
    assert request.reason == ""


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
async def test_second_cancel_request_returns_400_not_409(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )
    await _request_cancel(authed_client, created)

    response = await authed_client.post(f"/matches/{created['id']}/cancel-request", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Only accepted matches can be cancelled"
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

    response = await authed_client.post(f"/matches/{created['id']}/cancel-request", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A pending cancellation request already exists for this match"
    )
    assert _match_row(db, created["id"]).status == "accepted"


# =============================================================================
# Complete
# =============================================================================


@pytest.mark.asyncio
async def test_complete_accepted_surrogate_match_without_stage_change(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _accept(authed_client, await _case(authed_client, ip, surrogate=surrogate))
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        response = await authed_client.put(
            f"/matches/{created['id']}/complete",
            json={"outcome": "  Delivered  ", "reason": "  Journey complete  "},
        )

    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["status"] == "completed"
    assert completed["outcome"] == "Delivered"
    assert completed["closure_reason"] == "Journey complete"
    assert completed["closed_at"] is not None
    assert _match_row(db, created["id"]).closed_by_user_id == test_auth.user.id
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "matched"
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_completed", "match"): 1},
        "surrogate_activity": {"match_completed": 1},
        "entity_activity": {("intended_parent", "match_completed"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,status_code,detail",
    [
        ({}, 422, None),
        ({"outcome": ""}, 422, None),
        ({"outcome": "   "}, 400, "Completion outcome is required"),
    ],
)
async def test_complete_requires_outcome(authed_client, db, body, status_code, detail):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )

    response = await authed_client.put(f"/matches/{created['id']}/complete", json=body)

    assert response.status_code == status_code
    if detail:
        assert response.json()["detail"] == detail
    assert _match_row(db, created["id"]).status == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("current_status", ["proposed", "cancel_pending"])
async def test_complete_requires_accepted_status(authed_client, db, current_status):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if current_status == "cancel_pending":
        await _accept(authed_client, created)
        await _request_cancel(authed_client, created)

    response = await authed_client.put(
        f"/matches/{created['id']}/complete", json={"outcome": "Done"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only accepted matches can be completed"
    assert _match_row(db, created["id"]).status == current_status


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

    response = await authed_client.put(
        f"/matches/{rejected['id']}/reject", json={"rejection_reason": "No"}
    )
    assert response.status_code == 200
    assert (await authed_client.delete(f"/matches/{cancelled['id']}")).status_code == 204
    await _accept(authed_client, accepted)
    requested = await _request_cancel(authed_client, accepted)

    assert requested["status"] == "cancel_pending"
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
    assert _match_row(db, created["id"]).status == "proposed"
    assert _ip_stage_key(db, ip["id"]) == "new"


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

    response = await authed_client.put(
        f"/matches/{rejected['id']}/reject", json={"rejection_reason": "No"}
    )
    assert response.status_code == 200
    assert (await authed_client.delete(f"/matches/{cancelled['id']}")).status_code == 204
    requested = await _request_cancel(authed_client, accepted)
    assert requested["status"] == "cancel_pending"
    viewed = await authed_client.get(f"/matches/{accepted['id']}")
    assert viewed.status_code == 200


@pytest.mark.asyncio
async def test_disabled_expansion_blocks_donor_repeat_pair_after_closure_with_503(
    authed_client, db, monkeypatch
):
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    first = await _case(authed_client, ip, donor=donor)
    await authed_client.delete(f"/matches/{first['id']}")
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    count = db.query(Match).count()

    response = await authed_client.post(
        "/matches/", json={"donor_id": donor["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 503
    assert db.query(Match).count() == count


# =============================================================================
# Permissions (v1 organization: propose_matches gates every mutation)
# =============================================================================

MATCH_MUTATIONS = [
    ("PUT", "/matches/{id}/accept", {}),
    ("PUT", "/matches/{id}/reject", {"rejection_reason": "No"}),
    ("POST", "/matches/{id}/cancel-request", {}),
    ("DELETE", "/matches/{id}", None),
    ("PUT", "/matches/{id}/complete", {"outcome": "Done"}),
    ("PATCH", "/matches/{id}/notes", {"notes": "Changed"}),
]


@pytest.mark.asyncio
async def test_user_without_propose_matches_cannot_propose(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    count = db.query(Match).count()

    async with _client_for(db, test_auth.org.id, revoke=("propose_matches",)) as (_user, client):
        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

    assert response.status_code == 403
    assert db.query(Match).count() == count


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", MATCH_MUTATIONS)
async def test_user_without_propose_matches_is_denied_every_mutation(
    authed_client, db, test_auth, method, path, body
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if "cancel-request" in path or "complete" in path:
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
    assert response.json()["status"] == "proposed"
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
    assert _match_row(db, created["id"]).status == "proposed"


@pytest.mark.asyncio
async def test_intake_specialist_role_cannot_view_or_mutate_match(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, role=Role.INTAKE_SPECIALIST) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        accept = await client.put(f"/matches/{created['id']}/accept", json={})

    assert detail.status_code == 403
    assert accept.status_code == 403
    assert _match_row(db, created["id"]).status == "proposed"


# =============================================================================
# Cross-organization isolation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/matches/{id}", None),
        ("GET", "/matches/{id}/events", None),
        ("GET", "/matches/{id}/attempts", None),
        *MATCH_MUTATIONS,
    ],
)
async def test_other_org_user_gets_404_for_match_routes(
    authed_client, db, test_auth, method, path, body
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if "cancel-request" in path or "complete" in path:
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
async def test_other_org_user_cannot_propose_with_foreign_parties(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    count = db.query(Match).count()
    other_org = _other_org(db)

    async with _client_for(db, other_org.id) as (_user, client):
        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

    assert response.status_code == 404
    assert db.query(Match).count() == count


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "donor"])
@pytest.mark.parametrize("foreign_side", ["intended_parent", "participant"])
async def test_propose_with_one_foreign_party_returns_404(
    authed_client, db, test_auth, kind, foreign_side
):
    create_party = _donor if kind == "donor" else _create_surrogate
    async with _client_for(db, _other_org(db).id, role=Role.DEVELOPER) as (_user, foreign):
        foreign_ip = await _create_intended_parent(foreign)
        foreign_party = await create_party(foreign)
    local_ip = await _create_intended_parent(authed_client)
    local_party = await create_party(authed_client)
    if foreign_side == "intended_parent":
        ip, party = foreign_ip, local_party
    else:
        ip, party = local_ip, foreign_party
    count = db.query(Match).count()

    response = await authed_client.post(
        "/matches/", json={f"{kind}_id": party["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 404
    assert db.query(Match).count() == count


async def _foreign_accepted_match(db) -> dict:
    async with _client_for(db, _other_org(db).id, role=Role.DEVELOPER) as (_user, foreign):
        return await _accept(
            foreign,
            await _case(
                foreign,
                await _create_intended_parent(foreign),
                surrogate=await _create_surrogate(foreign),
            ),
        )


@pytest.mark.asyncio
async def test_create_attempt_on_foreign_match_returns_404(authed_client, db):
    from app.db.models import MatchAttempt

    match = await _foreign_accepted_match(db)
    count = db.query(MatchAttempt).count()

    response = await authed_client.post(
        f"/matches/{match['id']}/attempts", json={"attempt_type": "embryo_transfer"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Match not found"
    assert db.query(MatchAttempt).count() == count


@pytest.mark.asyncio
async def test_ai_routes_return_404_for_foreign_match(authed_client, db):
    match = await _foreign_accepted_match(db)
    count = db.query(Task).count()

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
    assert db.query(Task).count() == count


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
async def test_match_mutations_require_csrf_header(authed_client, db, method, path, body):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    if body == "propose":
        body = {"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    count = db.query(Match).count()

    response = await authed_client.request(
        method, path.format(id=created["id"]), json=body, headers={CSRF_HEADER: "invalid"}
    )

    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    assert db.query(Match).count() == count
    assert _match_row(db, created["id"]).status == "proposed"


# =============================================================================
# After-commit effects: stage callbacks, ordering, and failure
# =============================================================================


def _spy_ordered_effects(monkeypatch, events: list[str], failing: str | None = None):
    """Record the order of every after-commit effect of accept and approval."""
    from app.services import note_service, surrogate_events

    targets = {
        "dispatch_note_added": (note_service, "dispatch_note_added"),
        "handle_status_changed": (surrogate_events, "handle_status_changed"),
        "push_dashboard_stats": (dashboard_service, "push_dashboard_stats"),
        "trigger_match_accepted": (workflow_triggers, "trigger_match_accepted"),
        "notify_match_cancel_request_resolved": (
            notification_service,
            "notify_match_cancel_request_resolved",
        ),
    }
    spies = {}
    for name, (module, attribute) in targets.items():
        error = RuntimeError(f"{name} failed") if name == failing else None
        spies[name] = _Spy(error=error, events=events, name=name)
        monkeypatch.setattr(module, attribute, spies[name])
    return spies


@pytest.mark.asyncio
async def test_accept_dispatches_surrogate_stage_callbacks_before_later_effects(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    events: list[str] = []
    spies = _spy_ordered_effects(monkeypatch, events)

    await _accept(authed_client, created)

    assert events == [
        "dispatch_note_added",
        "handle_status_changed",
        "push_dashboard_stats",
        "trigger_match_accepted",
    ]
    stage = spies["handle_status_changed"].calls[0][1]
    assert stage["surrogate"].id == uuid.UUID(surrogate["id"])
    assert stage["new_stage"].slug == "matched"
    assert stage["old_slug"] == "new_unread"
    assert stage["user_id"] == test_auth.user.id
    assert stage["request_id"] is None
    assert stage["approved_by_user_id"] is None
    assert stage["is_undo"] is False
    assert stage["trigger_workflows"] is True
    note = spies["dispatch_note_added"].calls[0][1]
    assert note["org_id"] == test_auth.org.id
    from app.db.models import EntityNote

    note_row = db.get(EntityNote, note["note_id"])
    assert note_row.entity_id == uuid.UUID(surrogate["id"])
    assert "Match accepted" in note_row.content


@pytest.mark.asyncio
async def test_accept_donor_match_dispatches_no_stage_callbacks(
    authed_client, db, test_auth, monkeypatch
):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        donor=await _donor(authed_client),
    )
    events: list[str] = []
    _spy_ordered_effects(monkeypatch, events)

    await _accept(authed_client, created)

    assert events == ["push_dashboard_stats"]


@asynccontextmanager
async def _committed_org(db_engine, monkeypatch):
    """Committed org whose requests use the real per-request session from get_db.

    The shared test session cannot show whether a change was committed before an
    effect ran, so these requests use real sessions and a separate verifying
    session. Audit writes are disabled: audit rows are immutable and would block
    cleanup (same approach as test_concurrent_acceptances_reserve_one_surrogate).
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.db.models import Organization
    from app.services import audit_service

    monkeypatch.setattr(audit_service, "log_event", lambda **kwargs: None)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with Session(db_engine) as setup:
        setup.add(
            Organization(
                id=org_id, name="Committed match QA", slug=f"committed-{org_id}", ai_enabled=True
            )
        )
        setup.add(
            User(
                id=user_id,
                email=f"committed-{user_id}@example.com",
                display_name="Committed QA",
                is_active=True,
                token_version=1,
            )
        )
        setup.flush()
        setup.add(
            Membership(
                id=uuid.uuid4(),
                user_id=user_id,
                organization_id=org_id,
                role=Role.DEVELOPER.value,
                is_active=True,
            )
        )
        token = create_session_token(
            user_id=user_id,
            org_id=org_id,
            role=Role.DEVELOPER.value,
            token_version=1,
            mfa_verified=True,
            mfa_required=True,
        )
        session_service.create_session(
            db=setup, user_id=user_id, org_id=org_id, token=token, request=None
        )
        setup.commit()

    previous = app.dependency_overrides.pop(get_db, None)
    csrf_token = generate_csrf_token()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as client:
            yield org_id, user_id, client
    finally:
        if previous is not None:
            app.dependency_overrides[get_db] = previous
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
            cleanup.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def _committed_state(db_engine, match_id=None, surrogate_id=None, ip_id=None) -> dict:
    """Read committed rows through a separate session."""
    from sqlalchemy.orm import Session

    state = {}
    with Session(db_engine) as verify:
        if match_id:
            match = verify.get(Match, uuid.UUID(str(match_id)))
            state["match"] = match.status if match else None
            state["requests"] = sorted(
                row.status
                for row in verify.query(StatusChangeRequest).filter(
                    StatusChangeRequest.entity_id == uuid.UUID(str(match_id))
                )
            )
        if surrogate_id:
            state["surrogate_stage"] = verify.get(
                Surrogate, uuid.UUID(str(surrogate_id))
            ).stage.slug
        if ip_id:
            state["ip_stage"] = verify.get(IntendedParent, uuid.UUID(str(ip_id))).status
    return state


@pytest.mark.asyncio
async def test_failing_proposed_trigger_returns_created_after_match_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_proposed", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

        assert response.status_code == 201, response.text
        assert response.json()["status"] == "proposed"
        from sqlalchemy.orm import Session

        with Session(db_engine) as verify:
            statuses = [
                row.status
                for row in verify.query(Match).filter(
                    Match.organization_id == org_id,
                    Match.surrogate_id == uuid.UUID(surrogate["id"]),
                )
            ]
        assert statuses == ["proposed"]


@pytest.mark.asyncio
async def test_failing_accepted_trigger_returns_success_after_accept_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        created = await _case(client, ip, surrogate=surrogate)
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_accepted", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"
        assert _committed_state(db_engine, created["id"], surrogate["id"], ip["id"]) == {
            "match": "accepted",
            "requests": [],
            "surrogate_stage": "matched",
            "ip_stage": "matched",
        }


@pytest.mark.asyncio
async def test_failing_dashboard_push_after_accept_still_runs_trigger(db_engine, monkeypatch):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        created = await _case(client, await _create_intended_parent(client), surrogate=surrogate)
        events: list[str] = []
        spies = _spy_ordered_effects(monkeypatch, events, failing="push_dashboard_stats")

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert events == [
            "dispatch_note_added",
            "handle_status_changed",
            "push_dashboard_stats",
            "trigger_match_accepted",
        ]
        assert len(spies["trigger_match_accepted"].calls) == 1
        assert _committed_state(db_engine, created["id"], surrogate["id"])["match"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", ["dispatch_note_added", "handle_status_changed"])
async def test_failing_accept_stage_callback_still_runs_later_effects(
    db_engine, monkeypatch, failing
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        created = await _case(client, ip, surrogate=surrogate)
        events: list[str] = []
        _spy_ordered_effects(monkeypatch, events, failing=failing)

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert events == [
            "dispatch_note_added",
            "handle_status_changed",
            "push_dashboard_stats",
            "trigger_match_accepted",
        ]
        assert _committed_state(db_engine, created["id"], surrogate["id"], ip["id"]) == {
            "match": "accepted",
            "requests": [],
            "surrogate_stage": "matched",
            "ip_stage": "matched",
        }


@pytest.mark.asyncio
async def test_failing_rejected_trigger_returns_success_after_reject_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        created = await _case(
            client, await _create_intended_parent(client), surrogate=await _create_surrogate(client)
        )
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_rejected", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.put(
            f"/matches/{created['id']}/reject", json={"rejection_reason": "No"}
        )

        assert response.status_code == 200, response.text
        assert _committed_state(db_engine, created["id"])["match"] == "rejected"


@pytest.mark.asyncio
async def test_failing_cancel_request_notification_returns_success_after_request_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        created = await _accept(
            client,
            await _case(
                client,
                await _create_intended_parent(client),
                surrogate=await _create_surrogate(client),
            ),
        )
        monkeypatch.setattr(
            notification_service,
            "notify_match_cancel_request_pending",
            _Spy(error=RuntimeError("notify down")),
        )

        response = await client.post(f"/matches/{created['id']}/cancel-request", json={})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancel_pending"
        state = _committed_state(db_engine, created["id"])
        assert state == {"match": "cancel_pending", "requests": ["pending"]}


def _effect_failures(db, match_id) -> list[dict]:
    db.expire_all()
    return [
        row.details
        for row in db.query(AuditLog)
        .filter(
            AuditLog.event_type == "match_effect_failed",
            AuditLog.target_type == "match",
            AuditLog.target_id == uuid.UUID(str(match_id)),
        )
        .order_by(AuditLog.created_at)
    ]


@pytest.mark.asyncio
async def test_failing_effect_is_recorded_on_the_match_and_later_effects_run(
    authed_client, db, test_auth, monkeypatch
):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    events: list[str] = []
    spies = _spy_ordered_effects(monkeypatch, events, failing="push_dashboard_stats")

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert events[-2:] == ["push_dashboard_stats", "trigger_match_accepted"]
    assert len(spies["trigger_match_accepted"].calls) == 1
    assert _match_row(db, created["id"]).status == "accepted"
    assert _effect_failures(db, created["id"]) == [
        {
            "match_id": created["id"],
            "action": "accept",
            "effect": "dashboard_push",
            "error_class": "RuntimeError",
        }
    ]
    feed = await authed_client.get(f"/matches/{created['id']}/work")
    assert feed.status_code == 200, feed.text
    assert "Match Effect Failed" in {item["event_type"] for item in feed.json()["activity"]}


@pytest.mark.asyncio
async def test_each_failing_effect_is_recorded_separately(authed_client, db, monkeypatch):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    events: list[str] = []
    _spy_ordered_effects(monkeypatch, events)
    monkeypatch.setattr(
        workflow_triggers, "trigger_match_accepted", _Spy(error=ValueError("workflow down"))
    )
    monkeypatch.setattr(
        dashboard_service, "push_dashboard_stats", _Spy(error=RuntimeError("socket down"))
    )

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert [(row["effect"], row["error_class"]) for row in _effect_failures(db, created["id"])] == [
        ("dashboard_push", "RuntimeError"),
        ("workflow_trigger_match_accepted", "ValueError"),
    ]


# =============================================================================
# AI routes enforce match access like the matches router
# =============================================================================


@pytest.mark.asyncio
async def test_ai_bulk_tasks_require_view_matches(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (user, client):
        denied = await client.get(f"/matches/{created['id']}")
        response = await client.post(
            "/ai/create-bulk-tasks",
            json={
                "request_id": str(uuid.uuid4()),
                "match_id": created["id"],
                "tasks": [{"title": "Schedule consult"}],
            },
        )

    assert denied.status_code == 403
    assert response.status_code == 403
    assert response.json()["detail"] == denied.json()["detail"]
    assert db.query(Task).filter(Task.created_by_user_id == user.id).count() == 0


@pytest.mark.asyncio
async def test_ai_parse_schedule_requires_view_matches(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (_user, client):
        response = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": created["id"]}
        )
        missing = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": str(uuid.uuid4())}
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_matches"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Match not found"


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked", ["view_intended_parents", "view_surrogates"])
async def test_ai_routes_require_record_scope_on_both_parties(
    authed_client, db, test_auth, revoked
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    count = db.query(Task).count()

    async with _client_for(db, test_auth.org.id, revoke=(revoked,)) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        bulk = await client.post(
            "/ai/create-bulk-tasks",
            json={
                "request_id": str(uuid.uuid4()),
                "match_id": created["id"],
                "tasks": [{"title": "Scoped task"}],
            },
        )
        parsed = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": created["id"]}
        )

    assert detail.status_code in (403, 404)
    for response in (bulk, parsed):
        assert (response.status_code, response.json()["detail"]) == (
            detail.status_code,
            detail.json()["detail"],
        )
    assert db.query(Task).count() == count
