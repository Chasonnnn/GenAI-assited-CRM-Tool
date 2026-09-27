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

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import Match, Membership, Organization, StatusChangeRequest, User
from app.services import audit_service, match_lifecycle, pipeline_service
from app.services import status_change_request_service as approvals
from tests.test_match_events import _create_case
from tests.test_match_events import _create_intended_parent as _create_ip

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
        setup.flush()
        setup.add(
            Membership(
                organization_id=org_id, user_id=user_id, role=Role.DEVELOPER.value, is_active=True
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
    stage = pipeline_service.get_stage_by_system_role(setup, pipeline.id, "handoff")
    return _create_case(setup, org_id, user_id, stage)


def create_ip(db, org_id):
    ip = _create_ip(db, org_id)
    ready = pipeline_service.get_stage_by_key(db, ip.stage.pipeline_id, "ready_to_match")
    ip.stage_id = ready.id
    ip.stage = ready
    ip.status = ready.stage_key
    db.flush()
    return ip


def _proposal(setup, org_id, user_id, surrogate, ip, number, status="under_review"):
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


def test_decline_waiting_on_accept_can_decline_the_flagged_proposal(db_engine, monkeypatch):
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
                session, session.get(Match, ids[1]), "decline", actor_user_id=user_id, reason="No"
            )

        accepted, rejected = _run_while_first_holds_locks(
            db_engine, monkeypatch, _accept(user_id, ids[0]), reject
        )

        assert accepted == "applied"
        assert rejected == "applied"
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "accepted",
                "declined",
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
                status="cancellation_pending",
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
    """Crossed proposals remain open while independent accepts finish without deadlock."""
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
                "under_review",
                "accepted",
                "under_review",
            ]


def _donor_matches(db, org_id, user_id, kind, *, status="under_review"):
    from app.db.models import Donor

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, entity_type=f"{kind}_donor"
    )
    stage = pipeline_service.get_stage_by_system_role(
        db,
        pipeline.id,
        "matched" if status == "cancellation_pending" else "handoff",
        f"{kind}_donor",
    )
    donor = Donor(
        organization_id=org_id,
        donor_type=kind,
        donor_number="D10001",
        full_name="Concurrent donor",
        email=f"donor-{uuid.uuid4()}@example.com",
        email_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        stage_id=stage.id,
    )
    db.add(donor)
    db.flush()
    matches = []
    for number in ("M10001", "M10002"):
        ip = create_ip(db, org_id)
        if status == "cancellation_pending":
            matched = pipeline_service.get_stage_by_system_role(
                db, ip.stage.pipeline_id, "matched", "intended_parent"
            )
            ip.stage_id, ip.stage, ip.status = matched.id, matched, matched.stage_key
        match = Match(
            organization_id=org_id,
            donor_id=donor.id,
            match_kind="donor",
            intended_parent_id=ip.id,
            match_number=number,
            proposed_by_user_id=user_id,
            status=status,
        )
        db.add(match)
        db.flush()
        matches.append(match)
    return donor, matches


@pytest.mark.parametrize("kind,handoff", [("egg", "ready_to_match"), ("sperm", "available")])
def test_concurrent_donor_accepts_move_to_matched_once(db_engine, monkeypatch, kind, handoff):
    from app.db.models import Donor, DonorStatusHistory

    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            donor, matches = _donor_matches(setup, org_id, user_id, kind)
            setup.commit()
            donor_id, ids = donor.id, [m.id for m in matches]
        results = _run_while_first_holds_locks(
            db_engine, monkeypatch, _accept(user_id, ids[0]), _accept(user_id, ids[1])
        )
        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "accepted",
                "accepted",
            ]
            assert verify.get(Donor, donor_id).stage.stage_key == "matched"
            history = verify.query(DonorStatusHistory).filter_by(donor_id=donor_id).one()
            assert (history.old_status, history.new_status) == (handoff, "matched")
            assert history.changed_by_user_id == user_id


@pytest.mark.parametrize("kind,handoff", [("egg", "ready_to_match"), ("sperm", "available")])
def test_concurrent_donor_cancellations_return_to_handoff_once(
    db_engine, monkeypatch, kind, handoff
):
    from app.db.models import Donor, DonorStatusHistory

    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            donor, matches = _donor_matches(
                setup, org_id, user_id, kind, status="cancellation_pending"
            )
            requests = []
            for match in matches:
                request = StatusChangeRequest(
                    organization_id=org_id,
                    entity_type="match",
                    entity_id=match.id,
                    target_status="cancelled",
                    effective_at=datetime.now(UTC),
                    reason="Ended",
                    requested_by_user_id=user_id,
                    requested_at=datetime.now(UTC),
                    status="pending",
                )
                setup.add(request)
                requests.append(request)
            setup.commit()
            donor_id, ids = donor.id, [m.id for m in matches]
            request_ids = [r.id for r in requests]

        def approve(request_id):
            def run(db):
                approvals.approve_request(
                    db=db,
                    request_id=request_id,
                    org_id=org_id,
                    admin_user_id=user_id,
                    admin_role=Role.DEVELOPER,
                )

            return run

        results = _run_while_first_holds_locks(
            db_engine, monkeypatch, approve(request_ids[0]), approve(request_ids[1])
        )
        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "cancelled",
                "cancelled",
            ]
            assert verify.get(Donor, donor_id).stage.stage_key == handoff
            history = verify.query(DonorStatusHistory).filter_by(donor_id=donor_id).one()
            assert (history.old_status, history.new_status) == ("matched", handoff)
            assert history.changed_by_user_id == user_id


def test_v2_donor_accept_racing_cancellation_approval_keeps_lock_order(db_engine, monkeypatch):
    from app.db.models import Donor
    from app.db.models.permission_policy import OrganizationPermissionPolicy

    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            donor, matches = _donor_matches(
                setup, org_id, user_id, "egg", status="cancellation_pending"
            )
            # A new donor for the same IP must move to Matched while the IP's
            # other donor match is awaiting cancellation approval.
            handoff = pipeline_service.get_stage_by_system_role(
                setup, donor.stage.pipeline_id, "handoff", "egg_donor"
            )
            new_donor = Donor(
                organization_id=org_id,
                donor_type="egg",
                donor_number="D10002",
                full_name="Second concurrent donor",
                email=f"donor-{uuid.uuid4()}@example.com",
                email_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                stage_id=handoff.id,
            )
            setup.add(new_donor)
            setup.flush()
            matches[1].donor_id = new_donor.id
            matches[1].intended_parent_id = matches[0].intended_parent_id
            matches[1].status = "under_review"
            request = StatusChangeRequest(
                organization_id=org_id,
                entity_type="match",
                entity_id=matches[0].id,
                target_status="cancelled",
                effective_at=datetime.now(UTC),
                reason="Ended",
                requested_by_user_id=user_id,
                requested_at=datetime.now(UTC),
                status="pending",
            )
            setup.add(request)
            setup.add(OrganizationPermissionPolicy(organization_id=org_id, version=2))
            setup.commit()
            donor_id, ids, request_id = new_donor.id, [m.id for m in matches], request.id

        def approve(db):
            approvals.approve_request(
                db=db,
                request_id=request_id,
                org_id=org_id,
                admin_user_id=user_id,
                admin_role=Role.DEVELOPER,
            )

        results = _run_while_first_holds_locks(
            db_engine, monkeypatch, _accept(user_id, ids[1]), approve
        )
        assert results == ["applied", "applied"]
        with Session(db_engine) as verify:
            assert [verify.get(Match, match_id).status for match_id in ids] == [
                "cancelled",
                "accepted",
            ]
            assert verify.get(Donor, donor_id).stage.stage_key == "matched"
