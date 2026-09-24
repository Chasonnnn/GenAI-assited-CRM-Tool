"""Concurrent match transitions under the engine lock order.

The engine locks the status-change request, then matches FOR UPDATE, then the
surrogate or donor and the intended parent FOR NO KEY UPDATE. These tests run
two transitions on separate connections and check that both finish without a
deadlock or lock timeout and leave one consistent outcome.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from time import monotonic, sleep

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import Match, Organization, StatusChangeRequest, User
from app.services import audit_service, match_lifecycle, pipeline_service
from app.services import status_change_request_service as approvals
from tests.test_match_events import _create_case
from tests.test_match_events import _create_intended_parent as create_ip

_WAIT = 10


@contextmanager
def _committed_org(db_engine, monkeypatch):
    # Two connections need committed fixtures. Cleanup deletes the organization, and
    # the audit_logs_no_delete trigger blocks that cascade, so audit writes are stubbed.
    monkeypatch.setattr(audit_service, "log_event", lambda **kwargs: None)
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    with Session(db_engine) as setup:
        setup.add(Organization(id=org_id, name="Engine lock QA", slug=f"engine-lock-{org_id}"))
        setup.add(
            User(
                id=user_id,
                email=f"engine-lock-{user_id}@example.com",
                display_name="Engine Lock QA",
                is_active=True,
                token_version=1,
            )
        )
        setup.commit()
    try:
        yield org_id, user_id
    finally:
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
            cleanup.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def _attempt(session, operation):
    session.execute(text("SET LOCAL lock_timeout = '10s'"))
    try:
        operation(session)
        return "applied"
    except ValueError as exc:
        session.rollback()
        return str(exc)


def _blocks_another_backend(db) -> bool:
    # Activity statistics are snapshotted per transaction; clear the snapshot to poll.
    db.execute(text("SELECT pg_stat_clear_snapshot()"))
    return bool(
        db.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE pg_backend_pid() = ANY(pg_blocking_pids(pid))"
            )
        ).scalar_one()
    )


def _run_while_first_holds_locks(db_engine, monkeypatch, first, second):
    """Start ``second`` only after ``first`` holds all engine locks, and keep them
    held until ``second`` waits on one of them."""
    role = threading.local()
    locked = threading.Event()
    original = match_lifecycle._lock

    def lock_then_hold(db, match, **kwargs):
        result = original(db, match, **kwargs)
        if getattr(role, "first", False):
            locked.set()
            deadline = monotonic() + _WAIT
            while not _blocks_another_backend(db):
                assert monotonic() < deadline, "second transition never waited on the first"
                sleep(0.01)
        return result

    monkeypatch.setattr(match_lifecycle, "_lock", lock_then_hold)

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


def _surrogate(setup, org_id, user_id):
    pipeline = pipeline_service.get_or_create_default_pipeline(setup, org_id)
    stage = pipeline_service.get_stage_by_system_role(setup, pipeline.id, "matched")
    return _create_case(setup, org_id, user_id, stage)


def _proposal(setup, org_id, user_id, surrogate, ip, number, status="proposed"):
    match = Match(
        organization_id=org_id,
        surrogate_id=surrogate.id,
        intended_parent_id=ip.id,
        match_number=number,
        proposed_by_user_id=user_id,
        status=status,
    )
    setup.add(match)
    setup.flush()
    return match


def _accept(user_id, match_id):
    def run(session):
        match_lifecycle.transition(
            session,
            session.get(Match, match_id),
            "accept",
            actor_user_id=user_id,
            actor_role=Role.DEVELOPER,
        )

    return run


def test_reject_waiting_on_accept_sees_the_competing_proposal_cancelled(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            surrogate = _surrogate(setup, org_id, user_id)
            ids = [
                _proposal(setup, org_id, user_id, surrogate, create_ip(setup, org_id), number).id
                for number in ("M10001", "M10002")
            ]
            setup.commit()

        def reject(session):
            match_lifecycle.transition(
                session, session.get(Match, ids[1]), "reject", actor_user_id=user_id, reason="No"
            )

        accepted, rejected = _run_while_first_holds_locks(
            db_engine, monkeypatch, _accept(user_id, ids[0]), reject
        )

        assert accepted == "applied"
        assert rejected == "Cannot reject match with status: cancelled"
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "accepted",
                "cancelled",
            ]


def test_accept_waiting_on_cancellation_approval_accepts_after_it(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            surrogate = _surrogate(setup, org_id, user_id)
            pending = _proposal(
                setup,
                org_id,
                user_id,
                surrogate,
                create_ip(setup, org_id),
                "M10001",
                status="cancel_pending",
            )
            proposed = _proposal(
                setup, org_id, user_id, surrogate, create_ip(setup, org_id), "M10002"
            )
            now = datetime.now(UTC)
            request = StatusChangeRequest(
                organization_id=org_id,
                entity_type="match",
                entity_id=pending.id,
                target_status="cancelled",
                effective_at=now,
                reason="Ended",
                requested_by_user_id=user_id,
                requested_at=now,
                status="pending",
            )
            setup.add(request)
            setup.commit()
            pending_id, proposed_id, request_id = pending.id, proposed.id, request.id

        def approve(session):
            approvals.approve_request(
                db=session,
                request_id=request_id,
                org_id=org_id,
                admin_user_id=user_id,
                admin_role=Role.DEVELOPER,
            )

        approved, accepted = _run_while_first_holds_locks(
            db_engine, monkeypatch, approve, _accept(user_id, proposed_id)
        )

        assert (approved, accepted) == ("applied", "applied")
        with Session(db_engine) as verify:
            assert verify.get(Match, pending_id).status == "cancelled"
            assert verify.get(StatusChangeRequest, request_id).status == "approved"
            assert verify.get(Match, proposed_id).status == "accepted"


def test_cross_intended_parent_accepts_finish_without_deadlock(db_engine, monkeypatch):
    """Each accept cancels a competing proposal whose intended parent the other accept
    holds. History for that proposal takes FOR KEY SHARE on the other intended parent,
    which FOR UPDATE party locks would block in both directions."""
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            ip_a, ip_b = create_ip(setup, org_id), create_ip(setup, org_id)
            s1, s2 = _surrogate(setup, org_id, user_id), _surrogate(setup, org_id, user_id)
            ids = [
                _proposal(setup, org_id, user_id, surrogate, ip, number).id
                for surrogate, ip, number in (
                    (s1, ip_a, "M10001"),
                    (s1, ip_b, "M10002"),
                    (s2, ip_b, "M10003"),
                    (s2, ip_a, "M10004"),
                )
            ]
            setup.commit()

        both_locked = threading.Barrier(2)
        original = match_lifecycle._lock

        def lock_then_meet(db, match, **kwargs):
            result = original(db, match, **kwargs)
            both_locked.wait(timeout=_WAIT)
            return result

        monkeypatch.setattr(match_lifecycle, "_lock", lock_then_meet)

        def run(match_id):
            with Session(db_engine) as session:
                return _attempt(session, _accept(user_id, match_id))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, ids[0]), pool.submit(run, ids[2])]
            results = [future.result(timeout=_WAIT * 3) for future in futures]

        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "accepted",
                "cancelled",
                "accepted",
                "cancelled",
            ]
