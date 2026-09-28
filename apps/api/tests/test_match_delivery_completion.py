"""A surrogate entering the Delivered stage completes her accepted match.

Every stage-change path completes the match in the same transaction as the
stage move. Undoing that Delivered entry restores the match; other moves out
of Delivered do not.
"""

import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import Role
from app.db.models import (
    IntendedParent,
    Match,
    MatchAttempt,
    StatusChangeRequest,
    Surrogate,
    SurrogateStatusHistory,
)
from app.services import match_lifecycle, match_queries, pipeline_service
from tests.match_fixtures import seed_attempt
from tests.test_match_cancel_request import (
    _create_accepted_match,
    _create_intended_parent,
    _create_surrogate,
)
from tests.test_match_events import _create_case
from tests.test_match_events import _create_intended_parent as _insert_ip
from tests.test_match_lifecycle_characterization import (
    _client_for,
    _diff,
    _match_row,
    _other_org,
    _snapshot,
)
from tests.test_match_lifecycle_concurrency import (
    _WAIT,
    _attempt,
    _blocks_another_backend,
    _committed_org,
)
from tests.test_match_permissions_v2_characterization import _activate_v2

COMPLETED_HISTORY = {
    "audit": {("match_completed", "match"): 1},
    "surrogate_activity": {"match_completed": 1},
    "entity_activity": {("intended_parent", "match_completed"): 1},
}
UNDONE_HISTORY = {
    "audit": {("match_completion_undone", "match"): 1},
    "surrogate_activity": {"match_completion_undone": 1},
    "entity_activity": {("intended_parent", "match_completion_undone"): 1},
}


def _stage(db, org_id, role=None, key=None):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    if role:
        return pipeline_service.get_stage_by_system_role(db, pipeline.id, role)
    return pipeline_service.get_stage_by_key(db, pipeline.id, key)


async def _move(client, surrogate_id, stage, **body):
    return await client.patch(
        f"/surrogates/{surrogate_id}/status", json={"stage_id": str(stage.id), **body}
    )


def _assert_completed(row: Match, *, actor, outcome, recorded_after):
    assert row.status == "completed"
    assert row.closed_at is not None and row.closed_at >= recorded_after
    assert row.closed_by_user_id == actor
    assert row.closure_reason is None
    assert row.outcome == outcome


def _assert_accepted(row: Match):
    assert (row.status, row.closed_at, row.closed_by_user_id, row.outcome, row.closure_reason) == (
        "accepted",
        None,
        None,
        None,
        None,
    )


def _history_only(db, org_id, before) -> dict:
    return {
        key: value
        for key, value in _diff(before, _snapshot(db, org_id)).items()
        if value and key != "stage_history"
    }


def _match_events(diff: dict) -> dict:
    """Keep only match history rows from a history diff."""
    return {
        key: {k: v for k, v in counter.items() if "match_" in str(k)}
        for key, counter in diff.items()
        if any("match_" in str(k) for k in counter)
    }


# =============================================================================
# Entry paths
# =============================================================================


@pytest.mark.asyncio
async def test_manual_delivered_change_completes_accepted_match(authed_client, db, test_auth):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    delivered.label, delivered.slug = "Baby Born", "birth_complete"
    db.commit()
    match = await _create_accepted_match(authed_client)
    attempts = [
        seed_attempt(db, match["id"], status=status).id
        for status in ("planned", "in_progress", "completed")
    ]
    db.commit()
    before = _snapshot(db, test_auth.org.id)
    started = datetime.now(UTC)

    response = await _move(authed_client, match["surrogate_id"], delivered)

    assert response.status_code == 200, response.text
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=test_auth.user.id, outcome="Baby Born", recorded_after=started)
    history = (
        db.query(SurrogateStatusHistory)
        .filter_by(surrogate_id=uuid.UUID(match["surrogate_id"]))
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert history.to_stage_id == delivered.id
    assert row.closed_at == history.recorded_at
    assert [db.get(MatchAttempt, a).status for a in attempts] == [
        "cancelled",
        "cancelled",
        "completed",
    ]
    assert _match_events(_history_only(db, test_auth.org.id, before)) == COMPLETED_HISTORY
    assert (
        match_queries.get_accepted_match_for_surrogate(
            db, test_auth.org.id, uuid.UUID(match["surrogate_id"])
        )
        is None
    )
    ip = db.get(IntendedParent, uuid.UUID(match["intended_parent_id"]))
    assert ip.status == "matched"
    read = await authed_client.get(f"/matches/{match['id']}")
    assert read.status_code == 200, read.text
    assert (read.json()["status"], read.json()["outcome"]) == ("completed", "Baby Born")
    assert read.json()["allowed_actions"] == []


@pytest.mark.asyncio
async def test_manual_delivered_change_locks_the_match_before_writing_the_surrogate(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    statements: list[str] = []
    connection = db.connection()

    def record(conn, cursor, statement, parameters, context, executemany):
        if re.search(r"FOR (NO KEY )?UPDATE", statement):
            statements.append("lock " + re.search(r"\bFROM\s+(\w+)", statement).group(1))
        elif statement.lstrip().upper().startswith("UPDATE"):
            statements.append("update " + statement.split()[1])

    event.listen(connection, "before_cursor_execute", record)
    try:
        response = await _move(authed_client, match["surrogate_id"], delivered)
    finally:
        event.remove(connection, "before_cursor_execute", record)

    assert response.status_code == 200, response.text
    assert "lock matches" in statements and "update surrogates" in statements
    assert statements.index("lock matches") < statements.index("update surrogates")
    assert statements.index("lock matches") < statements.index("update matches")


@pytest.mark.asyncio
async def test_backdated_delivered_change_closes_the_match_at_record_time(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    surrogate = db.get(Surrogate, uuid.UUID(match["surrogate_id"]))
    surrogate.created_at -= timedelta(days=10)
    db.commit()
    started = datetime.now(UTC)
    effective = (started - timedelta(days=3)).date().isoformat()

    response = await _move(
        authed_client,
        match["surrogate_id"],
        delivered,
        effective_at=effective,
        reason="Recorded late",
    )

    assert response.status_code == 200, response.text
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=test_auth.user.id, outcome="Delivered", recorded_after=started)
    history = (
        db.query(SurrogateStatusHistory)
        .filter_by(surrogate_id=uuid.UUID(match["surrogate_id"]), to_stage_id=delivered.id)
        .one()
    )
    assert history.effective_at < started - timedelta(days=2)
    assert row.closed_at == history.recorded_at


@pytest.mark.asyncio
async def test_bulk_delivered_change_completes_each_accepted_match(authed_client, db, test_auth):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    matches = [await _create_accepted_match(authed_client) for _ in range(2)]
    plain = await _create_surrogate(authed_client)
    before = _snapshot(db, test_auth.org.id)

    response = await authed_client.post(
        "/surrogates/bulk-change-stage",
        json={
            "surrogate_ids": [m["surrogate_id"] for m in matches] + [plain["id"]],
            "stage_id": str(delivered.id),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 3
    for match in matches:
        assert _match_row(db, match["id"]).status == "completed"
    assert _match_events(_history_only(db, test_auth.org.id, before)) == {
        key: {k: 2 * v for k, v in value.items()} for key, value in COMPLETED_HISTORY.items()
    }


@pytest.mark.asyncio
async def test_approved_delivered_request_completes_match_and_credits_the_approver(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    async with _client_for(db, test_auth.org.id, role=Role.CASE_MANAGER) as (requester, _):
        now = datetime.now(UTC)
        request = StatusChangeRequest(
            organization_id=test_auth.org.id,
            entity_type="surrogate",
            entity_id=uuid.UUID(match["surrogate_id"]),
            target_stage_id=delivered.id,
            effective_at=now,
            reason="Delivered",
            requested_by_user_id=requester.id,
            requested_at=now,
            status="pending",
        )
        db.add(request)
        db.commit()

        response = await authed_client.post(f"/status-change-requests/{request.id}/approve")

    assert response.status_code == 200, response.text
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=test_auth.user.id, outcome="Delivered", recorded_after=now)
    assert db.get(Surrogate, uuid.UUID(match["surrogate_id"])).stage_id == delivered.id


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_workflow_delivered_change_completes_match_without_a_user_actor(
    authed_client, db, test_auth, version
):
    from app.services import workflow_record_actions

    if version == 2:
        _activate_v2(db, test_auth.org.id)
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    surrogate = db.get(Surrogate, uuid.UUID(match["surrogate_id"]))
    started = datetime.now(UTC)

    result = workflow_record_actions.update_field(
        db,
        {"action_type": "update_field", "field": "stage_id", "value": str(delivered.id)},
        surrogate,
        uuid.uuid4(),
        0,
        None,
        workflow_actor_id=SYSTEM_USER_ID if version == 2 else None,
        execution_permissions=frozenset({"change_surrogate_status"}) if version == 2 else None,
        v2_authority=version == 2,
    )

    assert result["success"] is True, result
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=None, outcome="Delivered", recorded_after=started)
    assert db.get(Surrogate, surrogate.id).stage_id == delivered.id


@pytest.mark.asyncio
async def test_ai_status_action_completes_match(authed_client, db, test_auth):
    from app.services import ai_action_executor

    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    started = datetime.now(UTC)

    result = ai_action_executor.UpdateStatusExecutor().execute(
        {"stage_id": str(delivered.id)},
        db,
        test_auth.user.id,
        test_auth.org.id,
        uuid.UUID(match["surrogate_id"]),
    )
    db.commit()

    assert result["success"] is True, result
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=test_auth.user.id, outcome="Delivered", recorded_after=started)


@pytest.mark.asyncio
async def test_undo_of_an_ai_delivered_change_does_not_depend_on_the_database_clock(
    authed_client, db, test_auth, monkeypatch
):
    from app.services import ai_action_executor

    class _AppClockBehindDatabase(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) - timedelta(seconds=5)

    delivered = _stage(db, test_auth.org.id, role="delivered")
    matched = _stage(db, test_auth.org.id, role="matched")
    match = await _create_accepted_match(authed_client)
    # Keep the earlier stage history older than the skewed clock.
    for history in db.query(SurrogateStatusHistory).filter_by(
        surrogate_id=uuid.UUID(match["surrogate_id"])
    ):
        history.recorded_at -= timedelta(minutes=1)
    db.commit()
    monkeypatch.setattr(ai_action_executor, "datetime", _AppClockBehindDatabase)

    result = ai_action_executor.UpdateStatusExecutor().execute(
        {"stage_id": str(delivered.id)},
        db,
        test_auth.user.id,
        test_auth.org.id,
        uuid.UUID(match["surrogate_id"]),
    )
    db.commit()
    assert result["success"] is True, result
    assert _match_row(db, match["id"]).status == "completed"

    response = await _move(authed_client, match["surrogate_id"], matched)

    assert response.status_code == 200, response.text
    _assert_accepted(_match_row(db, match["id"]))


# =============================================================================
# Undo and other moves out of Delivered
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", ["matched", "anatomy_scanned"])
async def test_undo_of_delivered_restores_the_completed_match(
    authed_client, db, test_auth, previous
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    previous_stage = _stage(db, test_auth.org.id, key=previous)
    match = await _create_accepted_match(authed_client)
    if previous != "matched":
        assert (
            await _move(authed_client, match["surrogate_id"], previous_stage)
        ).status_code == 200
    assert (await _move(authed_client, match["surrogate_id"], delivered)).status_code == 200
    assert _match_row(db, match["id"]).status == "completed"
    before = _snapshot(db, test_auth.org.id)

    response = await _move(authed_client, match["surrogate_id"], previous_stage)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"
    undo = (
        db.query(SurrogateStatusHistory)
        .filter_by(surrogate_id=uuid.UUID(match["surrogate_id"]), to_stage_id=previous_stage.id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert undo.is_undo is True
    _assert_accepted(_match_row(db, match["id"]))
    assert _match_events(_history_only(db, test_auth.org.id, before)) == UNDONE_HISTORY
    assert db.get(Surrogate, uuid.UUID(match["surrogate_id"])).stage_id == previous_stage.id


@pytest.mark.asyncio
async def test_later_moves_out_of_delivered_keep_the_match_completed(authed_client, db, test_auth):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    matched = _stage(db, test_auth.org.id, role="matched")
    anatomy = _stage(db, test_auth.org.id, key="anatomy_scanned")
    match = await _create_accepted_match(authed_client)
    surrogate_id = uuid.UUID(match["surrogate_id"])
    assert (await _move(authed_client, surrogate_id, delivered)).status_code == 200
    history = (
        db.query(SurrogateStatusHistory)
        .filter_by(surrogate_id=surrogate_id, to_stage_id=delivered.id)
        .one()
    )
    history.recorded_at -= timedelta(minutes=10)
    db.commit()

    refused = await _move(authed_client, surrogate_id, matched, reason="Back to matched")
    assert refused.status_code == 403
    assert refused.json()["detail"] == "Cannot set to Matched without an accepted Match."
    moved = await _move(authed_client, surrogate_id, anatomy, reason="Recorded too early")

    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "applied"
    assert _match_row(db, match["id"]).status == "completed"


@pytest.mark.asyncio
async def test_undo_keeps_the_match_completed_when_the_surrogate_has_another_accepted_match(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    anatomy = _stage(db, test_auth.org.id, key="anatomy_scanned")
    match = await _create_accepted_match(authed_client)
    surrogate_id = uuid.UUID(match["surrogate_id"])
    assert (await _move(authed_client, surrogate_id, anatomy)).status_code == 200
    assert (await _move(authed_client, surrogate_id, delivered)).status_code == 200
    other_ip = await _create_intended_parent(authed_client)
    other = Match(
        organization_id=test_auth.org.id,
        match_number=match_lifecycle.generate_match_number(db, test_auth.org.id),
        surrogate_id=surrogate_id,
        intended_parent_id=uuid.UUID(other_ip["id"]),
        status="accepted",
        proposed_by_user_id=test_auth.user.id,
    )
    db.add(other)
    db.commit()
    before = _snapshot(db, test_auth.org.id)

    response = await _move(authed_client, surrogate_id, anatomy)

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "completed"
    assert _match_row(db, other.id).status == "accepted"
    assert _match_events(_history_only(db, test_auth.org.id, before)) == {}


# =============================================================================
# No-ops and isolation
# =============================================================================


@pytest.mark.asyncio
async def test_delivered_without_an_accepted_match_changes_no_match(authed_client, db, test_auth):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    lone = await _create_surrogate(authed_client)
    proposed_for = await _create_surrogate(authed_client)
    proposal = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": proposed_for["id"],
            "intended_parent_id": (await _create_intended_parent(authed_client))["id"],
        },
    )
    assert proposal.status_code == 201, proposal.text
    before = _snapshot(db, test_auth.org.id)

    for surrogate in (lone, proposed_for):
        response = await _move(authed_client, surrogate["id"], delivered)
        assert response.status_code == 200, response.text

    assert _match_row(db, proposal.json()["id"]).status == "under_review"
    assert _match_events(_history_only(db, test_auth.org.id, before)) == {}


@pytest.mark.asyncio
async def test_delivered_leaves_a_cancellation_pending_match_untouched(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    requested = await authed_client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
    assert requested.status_code == 200, requested.text
    before = _snapshot(db, test_auth.org.id)

    response = await _move(authed_client, match["surrogate_id"], delivered)

    assert response.status_code == 200, response.text
    row = _match_row(db, match["id"])
    assert (row.status, row.closed_at, row.outcome) == ("cancellation_pending", None, None)
    request = db.query(StatusChangeRequest).filter_by(entity_id=row.id).one()
    assert request.status == "pending"
    assert _match_events(_history_only(db, test_auth.org.id, before)) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resolution,event",
    [("reject", "match_cancel_request_rejected"), ("cancel", "match_cancel_request_withdrawn")],
)
async def test_cancellation_resolved_after_delivery_completes_the_restored_match(
    authed_client, db, test_auth, resolution, event
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    requested = await authed_client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
    assert requested.status_code == 200, requested.text
    assert (await _move(authed_client, match["surrogate_id"], delivered)).status_code == 200
    request = (
        db.query(StatusChangeRequest)
        .filter_by(entity_id=uuid.UUID(match["id"]), status="pending")
        .one()
    )
    before = _snapshot(db, test_auth.org.id)
    started = datetime.now(UTC)

    response = await authed_client.post(
        f"/status-change-requests/{request.id}/{resolution}", json={}
    )

    assert response.status_code == 200, response.text
    row = _match_row(db, match["id"])
    _assert_completed(row, actor=test_auth.user.id, outcome="Delivered", recorded_after=started)
    assert _match_events(_history_only(db, test_auth.org.id, before))["audit"] == {
        (event, "match"): 1,
        ("match_completed", "match"): 1,
    }
    assert (
        match_queries.get_accepted_match_for_surrogate(
            db, test_auth.org.id, uuid.UUID(match["surrogate_id"])
        )
        is None
    )


@pytest.mark.asyncio
async def test_delivered_completion_and_undo_work_with_match_expansion_off(
    authed_client, db, test_auth, monkeypatch
):
    from app.core.config import settings

    delivered = _stage(db, test_auth.org.id, role="delivered")
    matched = _stage(db, test_auth.org.id, role="matched")
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    match = await _create_accepted_match(authed_client)

    completed = await _move(authed_client, match["surrogate_id"], delivered)
    assert completed.status_code == 200, completed.text
    assert _match_row(db, match["id"]).status == "completed"
    undone = await _move(authed_client, match["surrogate_id"], matched)

    assert undone.status_code == 200, undone.text
    _assert_accepted(_match_row(db, match["id"]))


@pytest.mark.asyncio
async def test_delivered_completion_stays_inside_the_surrogates_organization(
    authed_client, db, test_auth
):
    delivered = _stage(db, test_auth.org.id, role="delivered")
    match = await _create_accepted_match(authed_client)
    other_org = _other_org(db)
    async with _client_for(db, other_org.id) as (other_user, other_client):
        other_matched = _stage(db, other_org.id, role="matched")
        other_surrogate = _create_case(db, other_org.id, other_user.id, other_matched)
        other_ip = _insert_ip(db, other_org.id)
        other_match = Match(
            organization_id=other_org.id,
            match_number="M10001",
            surrogate_id=other_surrogate.id,
            intended_parent_id=other_ip.id,
            status="accepted",
            proposed_by_user_id=other_user.id,
        )
        db.add(other_match)
        db.commit()

        foreign = await _move(other_client, match["surrogate_id"], delivered)
        assert foreign.status_code == 404
        _assert_accepted(_match_row(db, match["id"]))

        response = await _move(authed_client, match["surrogate_id"], delivered)

    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "completed"
    _assert_accepted(_match_row(db, other_match.id))


# =============================================================================
# Concurrency with the match engine
# =============================================================================


def _committed_accepted_match(db_engine, org_id, user_id):
    with Session(db_engine) as setup:
        matched = pipeline_service.get_stage_by_system_role(
            setup, pipeline_service.get_or_create_default_pipeline(setup, org_id).id, "matched"
        )
        surrogate = _create_case(setup, org_id, user_id, matched)
        ip = _insert_ip(setup, org_id)
        match = Match(
            organization_id=org_id,
            surrogate_id=surrogate.id,
            intended_parent_id=ip.id,
            match_number="M10001",
            proposed_by_user_id=user_id,
            status="accepted",
        )
        setup.add(match)
        setup.commit()
        return match.id, surrogate.id


def _deliver(user_id, surrogate_id):
    from app.services import surrogate_status_service

    def run(session):
        surrogate = session.get(Surrogate, surrogate_id)
        delivered = pipeline_service.get_stage_by_system_role(
            session, surrogate.stage.pipeline_id, "delivered"
        )
        surrogate_status_service.change_status(
            session, surrogate, delivered.id, user_id, Role.DEVELOPER
        )

    return run


def _request_cancel(user_id, match_id):
    def run(session):
        match_lifecycle.transition(
            session,
            session.get(Match, match_id),
            "request_cancel",
            actor_user_id=user_id,
            reason="Ended",
        )

    return run


def _run_holding(db_engine, monkeypatch, target, name, first, second):
    """Run ``first`` until it holds the locks taken by ``target.name``, then start
    ``second`` and keep the locks until ``second`` waits on them."""
    role = threading.local()
    locked = threading.Event()
    original = getattr(target, name)

    def lock_then_hold(*args, **kwargs):
        result = original(*args, **kwargs)
        if getattr(role, "first", False):
            locked.set()
            deadline = monotonic() + _WAIT
            while not _blocks_another_backend(args[0]):
                assert monotonic() < deadline, "second transaction never waited on the first"
                sleep(0.01)
        return result

    monkeypatch.setattr(target, name, lock_then_hold)

    def run_first():
        role.first = True
        with Session(db_engine) as session:
            return _attempt(session, first)

    def run_second():
        assert locked.wait(_WAIT)
        with Session(db_engine) as session:
            return _attempt(session, second)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_first), pool.submit(run_second)]
        return [future.result(timeout=_WAIT * 3) for future in futures]


def test_delivered_waiting_on_cancel_request_leaves_the_match_pending(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        match_id, surrogate_id = _committed_accepted_match(db_engine, org_id, user_id)

        results = _run_holding(
            db_engine,
            monkeypatch,
            match_lifecycle,
            "_lock",
            _request_cancel(user_id, match_id),
            _deliver(user_id, surrogate_id),
        )

        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert verify.get(Match, match_id).status == "cancellation_pending"
            assert verify.get(Surrogate, surrogate_id).stage.stage_key == "delivered"


def test_cancel_request_waiting_on_delivered_is_refused_after_completion(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        match_id, surrogate_id = _committed_accepted_match(db_engine, org_id, user_id)

        results = _run_holding(
            db_engine,
            monkeypatch,
            match_lifecycle,
            "_lock_surrogate_matches",
            _deliver(user_id, surrogate_id),
            _request_cancel(user_id, match_id),
        )

        assert results == ["applied", "Only accepted matches can be cancelled"]
        with Session(db_engine) as verify:
            assert verify.get(Match, match_id).status == "completed"
            assert verify.get(Surrogate, surrogate_id).stage.stage_key == "delivered"


def _committed_pending_cancellation(db_engine, org_id, user_id):
    match_id, surrogate_id = _committed_accepted_match(db_engine, org_id, user_id)
    with Session(db_engine) as setup:
        now = datetime.now(UTC)
        setup.get(Match, match_id).status = "cancellation_pending"
        request = StatusChangeRequest(
            organization_id=org_id,
            entity_type="match",
            entity_id=match_id,
            target_status="cancelled",
            effective_at=now,
            reason="Ended",
            requested_by_user_id=user_id,
            requested_at=now,
            status="pending",
        )
        setup.add(request)
        setup.commit()
        return match_id, surrogate_id, request.id


def _reject_cancel(user_id, match_id, request_id):
    def run(session):
        match_lifecycle.transition(
            session,
            session.get(Match, match_id),
            "reject_cancel",
            actor_user_id=user_id,
            request=session.get(StatusChangeRequest, request_id),
        )

    return run


@pytest.mark.parametrize("delivered_first", [False, True])
def test_delivered_racing_a_rejected_cancellation_completes_the_match(
    db_engine, monkeypatch, delivered_first
):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        match_id, surrogate_id, request_id = _committed_pending_cancellation(
            db_engine, org_id, user_id
        )
        deliver = _deliver(user_id, surrogate_id)
        reject = _reject_cancel(user_id, match_id, request_id)
        if delivered_first:
            args = (match_lifecycle, "_lock_surrogate_matches", deliver, reject)
        else:
            args = (match_lifecycle, "_lock", reject, deliver)

        results = _run_holding(db_engine, monkeypatch, *args)

        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert verify.get(Match, match_id).status == "completed"
            assert verify.get(Surrogate, surrogate_id).stage.stage_key == "delivered"
