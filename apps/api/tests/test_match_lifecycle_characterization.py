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
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import (
    dashboard_service,
    match_lifecycle,
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


_ROW_LOCK = re.compile(r"FOR (NO KEY )?UPDATE")


@contextmanager
def _locked_tables(db):
    """Record first domain-table locks; activation races own the organization-lock contract."""
    locked: list[str] = []
    connection = db.connection()

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if _ROW_LOCK.search(statement):
            match = re.search(r"\bFROM\s+(\w+)", statement)
            table = match.group(1) if match else statement
            if table != "organizations" and table not in locked:
                locked.append(table)

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
        "trigger_match_declined": _Spy(),
        "trigger_match_cancelled": _Spy(),
        "push_dashboard_stats": _Spy(),
        "notify_match_cancel_request_pending": _Spy(),
        "notify_match_cancel_request_resolved": _Spy(),
    }
    for name in (
        "trigger_match_proposed",
        "trigger_match_accepted",
        "trigger_match_declined",
        "trigger_match_cancelled",
    ):
        monkeypatch.setattr(workflow_triggers, name, spies[name])
    monkeypatch.setattr(
        dashboard_service, "push_dashboard_stats_or_raise", spies["push_dashboard_stats"]
    )
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
        match_number=match_lifecycle.generate_match_number(db, org_id),
        surrogate_id=uuid.UUID(str(surrogate_id)),
        intended_parent_id=uuid.UUID(str(intended_parent_id)),
        match_kind="surrogate",
        status="under_review",
        proposed_by_user_id=user_id,
    )
    db.add(match)
    db.commit()
    return match


def _set_reviewing(db, match_id):
    """Keep the single review state for the characterization setup."""
    row = _match_row(db, match_id)
    row.status = "under_review"
    db.commit()


async def _enter_status(db, org_id, match, status):
    """Assert the requested source state."""
    if status == "under_review":
        _set_reviewing(db, match["id"])
    assert _match_row(db, match["id"]).status == status


async def _request_cancel(client, match, reason="Family withdrew"):
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

    assert created["status"] == "under_review"
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
async def test_propose_donor_match_writes_under_review_status_and_workflow_trigger(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)
    created = await _case(authed_client, ip, donor=donor)

    assert created["status"] == "under_review"
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
    assert _call_counts(spies) == {"trigger_match_proposed": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_status", ["under_review", "accepted", "cancellation_pending"])
async def test_repeat_proposal_for_open_surrogate_pair_returns_409(
    authed_client, db, test_auth, existing_status
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    if existing_status == "under_review":
        _set_reviewing(db, created["id"])
    if existing_status in ("accepted", "cancellation_pending"):
        await _accept(authed_client, created)
    if existing_status == "cancellation_pending":
        await _request_cancel(authed_client, created)
    assert _match_row(db, created["id"]).status == existing_status
    count = db.query(Match).filter_by(organization_id=test_auth.org.id).count()

    response = await authed_client.post(
        "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == f"Match already exists with status: {existing_status}"
    assert db.query(Match).filter_by(organization_id=test_auth.org.id).count() == count


@pytest.mark.asyncio
async def test_repeat_proposal_after_closed_surrogate_pair_creates_new_match(authed_client, db):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    first = await _case(authed_client, ip, surrogate=surrogate)
    response = await authed_client.put(
        f"/matches/{first['id']}/decline", json={"reason": "Not now"}
    )
    assert response.status_code == 200

    repeat = await _case(authed_client, ip, surrogate=surrogate)

    assert repeat["id"] != first["id"]
    assert repeat["status"] == "under_review"
    assert repeat["match_number"] != first["match_number"]


@pytest.mark.asyncio
@pytest.mark.parametrize("committed_status", ["accepted", "cancellation_pending"])
async def test_propose_for_surrogate_with_committed_match_stays_open_and_flagged(
    authed_client, db, test_auth, committed_status
):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    first = await _accept(authed_client, await _case(authed_client, first_ip, surrogate=surrogate))
    if committed_status == "cancellation_pending":
        await _request_cancel(authed_client, first)
    count = db.query(Match).filter_by(organization_id=test_auth.org.id).count()

    response = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate["id"], "intended_parent_id": second_ip["id"]},
    )

    assert response.status_code == 201
    assert response.json()["surrogate_has_accepted_match"] is True
    assert response.json()["status"] == "under_review"
    assert db.query(Match).filter_by(organization_id=test_auth.org.id).count() == count + 1


@pytest.mark.asyncio
async def test_propose_accepts_parties_at_any_stage(authed_client, db):
    surrogate = await _create_surrogate(authed_client, ready=False)
    ip = await _create_intended_parent(authed_client, ready=False)
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "new_unread"
    assert _ip_stage_key(db, ip["id"]) == "new"

    created = await _case(authed_client, ip, surrogate=surrogate)

    assert created["status"] == "under_review"


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
    assert response.json()["status"] == "under_review"
    assert response.json()["reviewed_by_user_id"] is None
    row = _match_row(db, created["id"])
    assert row.status == "under_review"
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
    assert response.json()["status"] == "under_review"
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

    assert response.json()["status"] == "under_review"
    assert locks == []
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("phi_viewed", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {},
        "stage_history": {},
    }


@pytest.mark.asyncio
async def test_get_by_non_proposer_on_accepted_match_writes_no_transition(
    authed_client, db, test_auth
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    async with _client_for(db, test_auth.org.id) as (_viewer, other):
        await _accept(authed_client, created)
        reviewed_by = _match_row(db, created["id"]).reviewed_by_user_id
        before = _snapshot(db, test_auth.org.id)
        with _locked_tables(db) as locks:
            response = await other.get(f"/matches/{created['id']}")

    assert response.json()["status"] == "accepted"
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
    assert response.json()["status"] == "under_review"


# =============================================================================
# Accept
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["under_review"])
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
async def test_accept_keeps_other_open_proposals_for_same_surrogate(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    third_ip = await _create_intended_parent(authed_client)
    accepted = await _case(authed_client, first_ip, surrogate=surrogate)
    proposed = await _case(authed_client, second_ip, surrogate=surrogate)
    reviewing = await _case(authed_client, third_ip, surrogate=surrogate)
    _set_reviewing(db, reviewing["id"])
    before = _snapshot(db, test_auth.org.id)

    spies = _spy_effects(monkeypatch)
    await _accept(authed_client, accepted)
    assert _call_counts(spies) == {"trigger_match_accepted": 1, "push_dashboard_stats": 1}

    for other_id in (proposed["id"], reviewing["id"]):
        row = _match_row(db, other_id)
        assert row.status == "under_review"
        assert row.closure_reason is None
        assert row.closed_by_user_id is None
        assert row.closed_at is None
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_accepted", "match"): 1},
        "surrogate_activity": {"match_accepted": 1, "note_added": 1},
        "entity_activity": {
            ("intended_parent", "match_accepted"): 1,
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
    assert "declined_matches" not in audit.details


@pytest.mark.asyncio
async def test_accept_with_competing_proposals_locks_tables_in_engine_order(
    authed_client, db, test_auth, monkeypatch
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
    # Notification dedupe takes separate row locks after the engine commits.
    monkeypatch.setattr(
        "app.services.match_effects.surrogate_conflict_notifications", lambda *args: []
    )
    statements: list[str] = []
    connection = db.connection()

    def record(conn, cursor, statement, parameters, context, executemany):
        if _ROW_LOCK.search(statement):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        await _accept(authed_client, accepted)
    finally:
        event.remove(connection, "before_cursor_execute", record)

    first_locks = {}
    for sql in statements:
        first_locks.setdefault(re.search(r"\bFROM\s+(\w+)", sql).group(1), sql)
    assert list(first_locks) == [
        "organizations",
        "matches",
        "surrogates",
        "intended_parents",
    ]
    assert "ORDER BY matches.id" in first_locks["matches"]
    assert first_locks["matches"].rstrip().endswith("FOR UPDATE")
    assert all(
        sql.rstrip().endswith("FOR NO KEY UPDATE")
        for table, sql in first_locks.items()
        if table != "matches"
    )
    for other in competing:
        assert _match_row(db, other["id"]).status == "under_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("committed_status", ["accepted", "cancellation_pending"])
async def test_accept_when_surrogate_has_other_committed_match_returns_400(
    authed_client, db, test_auth, committed_status
):
    surrogate = await _create_surrogate(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    first = await _accept(authed_client, await _case(authed_client, first_ip, surrogate=surrogate))
    if committed_status == "cancellation_pending":
        await _request_cancel(authed_client, first)
    competing = _insert_proposed_match(
        db, test_auth.org.id, test_auth.user.id, surrogate["id"], second_ip["id"]
    )
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(f"/matches/{competing.id}/accept", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Surrogate has an accepted match"
    assert _match_row(db, competing.id).status == "under_review"
    assert _match_row(db, first["id"]).status == committed_status
    assert _ip_stage_key(db, second_ip["id"]) == "ready_to_match"
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
async def test_accept_when_ip_beyond_matched_is_blocked(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    _move_ip_to_stage(db, test_auth.org.id, ip["id"], "delivered")
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 400
    assert "Intended parent at Delivered is not eligible to accept" in response.json()["detail"]
    assert _match_row(db, created["id"]).status == "under_review"
    assert _ip_stage_key(db, ip["id"]) == "delivered"
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "ready_to_match"
    assert _diff(before, _snapshot(db, test_auth.org.id))["stage_history"] == {}


@pytest.mark.asyncio
async def test_accept_donor_match_moves_donor_and_ip_to_matched(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=donor)
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    with _locked_tables(db) as locks:
        accepted = await _accept(authed_client, created)

    assert accepted["status"] == "accepted"
    assert _stage_slug(db, Donor, donor["id"]) == "matched"
    assert _ip_stage_key(db, ip["id"]) == "matched"
    assert locks == ["matches", "donors", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_accepted", "match"): 1, ("donor_status_changed", "donor"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_accepted"): 1,
            ("intended_parent", "match_accepted"): 1,
        },
        "stage_history": {"donor": 1, "intended_parent": 1},
    }
    assert _call_counts(spies) == {"push_dashboard_stats": 1, "trigger_match_accepted": 1}


@pytest.mark.asyncio
async def test_accept_donor_match_keeps_other_open_donor_proposals(authed_client, db):
    donor = await _donor(authed_client)
    first = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    second = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)

    await _accept(authed_client, first)

    assert _match_row(db, second["id"]).status == "under_review"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_status", ["declined", "cancelled", "cancellation_pending", "completed"]
)
async def test_accept_match_outside_proposed_or_reviewing_returns_400(
    authed_client, db, current_status
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    if current_status == "declined":
        await authed_client.put(f"/matches/{created['id']}/decline", json={"reason": "No"})
    elif current_status == "cancelled":
        await _accept(authed_client, created)
        await _request_cancel(authed_client, created)
        request = (
            db.query(StatusChangeRequest)
            .filter(StatusChangeRequest.entity_id == uuid.UUID(created["id"]))
            .one()
        )
        response = await authed_client.post(f"/status-change-requests/{request.id}/approve")
        assert response.status_code == 200
    else:
        await _accept(authed_client, created)
        if current_status == "cancellation_pending":
            await _request_cancel(authed_client, created)
        else:
            row = _match_row(db, created["id"])
            row.status, row.closed_at = "completed", datetime.now(UTC)
            db.commit()
    assert _match_row(db, created["id"]).status == current_status

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == f"Cannot accept match with status: {current_status}"
    assert _match_row(db, created["id"]).status == current_status


# =============================================================================
# Reject
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["under_review"])
async def test_decline_surrogate_match_writes_declined_status_without_stage_changes(
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
            f"/matches/{created['id']}/decline",
            json={"reason": "  Not compatible  ", "notes": "Discussed"},
        )

    assert response.status_code == 200, response.text
    rejected = response.json()
    assert rejected["status"] == "declined"
    assert rejected["decline_reason"] == "Not compatible"
    assert rejected["closure_reason"] == "Not compatible"
    assert rejected["reviewed_by_user_id"] == str(test_auth.user.id)
    assert rejected["closed_at"] is not None
    assert "Discussed" in rejected["notes"]
    row = _match_row(db, created["id"])
    assert row.closed_by_user_id == test_auth.user.id
    assert _stage_slug(db, Surrogate, surrogate["id"]) == "ready_to_match"
    assert _ip_stage_key(db, ip["id"]) == "ready_to_match"
    assert locks == ["matches", "surrogates", "intended_parents"]
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_declined", "match"): 1},
        "surrogate_activity": {"match_declined": 1},
        "entity_activity": {("intended_parent", "match_declined"): 1},
        "stage_history": {},
    }
    assert _call_counts(spies) == {"trigger_match_declined": 1}


@pytest.mark.asyncio
async def test_decline_by_non_proposer_is_allowed(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id) as (viewer, other):
        response = await other.put(f"/matches/{created['id']}/decline", json={"reason": "No"})

    assert response.status_code == 200
    assert _match_row(db, created["id"]).closed_by_user_id == viewer.id


@pytest.mark.asyncio
async def test_decline_donor_match_fires_workflow_trigger(
    authed_client, db, test_auth, monkeypatch
):
    spies = _spy_effects(monkeypatch)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, donor=await _donor(authed_client))
    _reset(spies)
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(f"/matches/{created['id']}/decline", json={"reason": "No"})

    assert response.status_code == 200
    assert response.json()["status"] == "declined"
    assert _call_counts(spies) == {"trigger_match_declined": 1}
    assert _diff(before, _snapshot(db, test_auth.org.id)) == {
        "audit": {("match_declined", "match"): 1},
        "surrogate_activity": {},
        "entity_activity": {
            ("donor", "match_declined"): 1,
            ("intended_parent", "match_declined"): 1,
        },
        "stage_history": {},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": None}])
async def test_decline_requires_non_empty_reason(authed_client, db, body):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    response = await authed_client.put(f"/matches/{created['id']}/decline", json=body)

    assert response.status_code == 422
    assert _match_row(db, created["id"]).status == "under_review"


@pytest.mark.asyncio
async def test_decline_rejects_whitespace_only_reason(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    response = await authed_client.put(f"/matches/{created['id']}/decline", json={"reason": "   "})

    assert response.status_code == 422
    assert _match_row(db, created["id"]).status == "under_review"


@pytest.mark.asyncio
async def test_decline_accepted_match_returns_400(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    created = await _accept(
        authed_client,
        await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client)),
    )

    response = await authed_client.put(f"/matches/{created['id']}/decline", json={"reason": "No"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot decline match with status: accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("accepted", [False, True])
async def test_delete_match_is_removed_without_changing_history(
    authed_client, db, test_auth, accepted
):
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    if accepted:
        match = await _accept(authed_client, match)
    before = _snapshot(db, test_auth.org.id)
    response = await authed_client.delete(f"/matches/{match['id']}")
    assert response.status_code == 405
    assert _match_row(db, match["id"]).status == match["status"]
    assert _snapshot(db, test_auth.org.id) == before


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


# =============================================================================
# After-commit effects: stage callbacks, ordering, and failure
# =============================================================================


def _spy_ordered_effects(monkeypatch, events: list[str], failing: str | None = None):
    """Record the order of every after-commit effect of accept and approval."""
    from app.services import note_service, surrogate_events

    targets = {
        "dispatch_note_added": (note_service, "dispatch_note_added"),
        "handle_status_changed": (surrogate_events, "handle_status_changed"),
        "push_dashboard_stats": (dashboard_service, "push_dashboard_stats_or_raise"),
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
