"""Concurrent match transitions under the engine lock order.

The engine locks the status-change request, then matches, then the surrogate or
donor, then the intended parent. These tests run two transitions on separate
connections that share a surrogate and check that both finish without a
deadlock or lock timeout and leave one consistent outcome.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import Match, Organization, StatusChangeRequest, User
from app.services import audit_service, match_lifecycle, pipeline_service
from app.services import status_change_request_service as approvals
from tests.test_match_events import _create_case
from tests.test_match_events import _create_intended_parent as create_ip


@contextmanager
def _committed_org(db_engine, monkeypatch):
    # Committed fixtures for two connections; audit rows are immutable and would block cleanup.
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


def _run_together(db_engine, *operations):
    barrier = Barrier(len(operations))

    def run(operation):
        with Session(db_engine) as session:
            session.execute(text("SET LOCAL lock_timeout = '10s'"))
            barrier.wait(timeout=10)
            try:
                operation(session)
                return "applied"
            except ValueError as exc:
                session.rollback()
                return str(exc)

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run, operations))


def test_accept_and_reject_of_competing_proposals_finish_without_deadlock(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            pipeline = pipeline_service.get_or_create_default_pipeline(setup, org_id)
            stage = pipeline_service.get_stage_by_system_role(setup, pipeline.id, "matched")
            surrogate = _create_case(setup, org_id, user_id, stage)
            ids = []
            for number in ("M10001", "M10002"):
                case = Match(
                    organization_id=org_id,
                    surrogate_id=surrogate.id,
                    intended_parent_id=create_ip(setup, org_id).id,
                    match_number=number,
                    proposed_by_user_id=user_id,
                )
                setup.add(case)
                setup.flush()
                ids.append(case.id)
            setup.commit()

        def accept(session):
            match = session.get(Match, ids[0])
            match_lifecycle.transition(
                session, match, "accept", actor_user_id=user_id, actor_role=Role.DEVELOPER
            )

        def reject(session):
            match = session.get(Match, ids[1])
            match_lifecycle.transition(
                session, match, "reject", actor_user_id=user_id, reason="Not proceeding"
            )

        accepted, rejected = _run_together(db_engine, accept, reject)

        assert accepted == "applied"
        with Session(db_engine) as verify:
            statuses = [verify.get(Match, match_id).status for match_id in ids]
        if rejected == "applied":
            assert statuses == ["accepted", "rejected"]
        else:
            assert rejected == "Cannot reject match with status: cancelled"
            assert statuses == ["accepted", "cancelled"]


def test_accept_during_cancellation_approval_keeps_one_committed_match(db_engine, monkeypatch):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        with Session(db_engine) as setup:
            pipeline = pipeline_service.get_or_create_default_pipeline(setup, org_id)
            stage = pipeline_service.get_stage_by_system_role(setup, pipeline.id, "matched")
            surrogate = _create_case(setup, org_id, user_id, stage)
            pending = Match(
                organization_id=org_id,
                surrogate_id=surrogate.id,
                intended_parent_id=create_ip(setup, org_id).id,
                match_number="M10001",
                proposed_by_user_id=user_id,
                status="cancel_pending",
            )
            proposed = Match(
                organization_id=org_id,
                surrogate_id=surrogate.id,
                intended_parent_id=create_ip(setup, org_id).id,
                match_number="M10002",
                proposed_by_user_id=user_id,
            )
            setup.add_all([pending, proposed])
            setup.flush()
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

        def accept(session):
            match = session.get(Match, proposed_id)
            match_lifecycle.transition(
                session, match, "accept", actor_user_id=user_id, actor_role=Role.DEVELOPER
            )

        approved, accepted = _run_together(db_engine, approve, accept)

        assert approved == "applied"
        assert accepted in ("applied", "Surrogate already has an accepted match")
        with Session(db_engine) as verify:
            assert verify.get(Match, pending_id).status == "cancelled"
            assert verify.get(StatusChangeRequest, request_id).status == "approved"
            expected = "accepted" if accepted == "applied" else "proposed"
            assert verify.get(Match, proposed_id).status == expected
