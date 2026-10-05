"""Policy activation wins before concurrent mutations take domain row locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from queue import Queue
from time import monotonic, sleep
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import Role
from app.db.models import (
    AIActionApproval,
    AutomationWorkflow,
    EntityNote,
    Match,
    Membership,
    OrganizationPermissionPolicy,
    StatusChangeRequest,
    Surrogate,
    WorkflowExecution,
)
from app.db.session import SessionLocal
from app.services import (
    ai_action_approval_service,
    ai_action_executor,
    audit_service,
    match_lifecycle,
    permission_policy_service,
    pipeline_service,
    record_scope_service,
    status_change_request_service,
)
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter
from app.services.workflow_engine_core import WorkflowEngineCore
from tests.test_ai_action_transactions import committed_approval as committed_approval
from tests.test_ai_action_transactions import observation_engine as observation_engine
from tests.test_match_lifecycle_concurrency import (
    _committed_org,
    _proposal,
    _surrogate,
    create_ip,
)


def _race_activation(
    db_engine,
    observation_engine,
    org_id,
    model,
    row_id,
    operation,
    *,
    revoke=False,
    activation_change=None,
):
    """Use a real uncommitted policy change; mutation must leave its domain row unlocked."""
    ready = Queue()

    def mutate():
        # Keep the observed backend through real commits; an engine-bound session
        # can return its connection and resume on another PID from the pool.
        with db_engine.connect() as connection, SessionLocal(bind=connection) as db:
            db.execute(text("SET LOCAL statement_timeout = '10s'"))
            ready.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                result = operation(db)
                db.commit()
                return result
            except HTTPException as exc:
                db.rollback()
                return exc.status_code

    with (
        SessionLocal(bind=observation_engine) as activation,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        permission_policy_service.lock_configuration(activation, org_id)
        activation.add(OrganizationPermissionPolicy(organization_id=org_id, version=2))
        if revoke:
            activation.query(Membership).filter_by(organization_id=org_id).update(
                {"is_active": False}
            )
        if activation_change:
            activation_change(activation)
        activation.flush()
        future = pool.submit(mutate)
        pid = ready.get(timeout=5)
        waiting, row_available = False, False
        try:
            deadline = monotonic() + 5
            while monotonic() < deadline and not future.done():
                activation.execute(text("SELECT pg_stat_clear_snapshot()"))
                waiting = activation.scalar(
                    text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                )
                if waiting:
                    break
                sleep(0.01)
            if waiting:
                try:
                    with activation.begin_nested():
                        activation.execute(
                            select(model.id).where(model.id == row_id).with_for_update(nowait=True)
                        ).one()
                    row_available = True
                except OperationalError as exc:
                    assert exc.orig.sqlstate == "55P03"
        finally:
            activation.commit()
        result = future.result(timeout=10)
    assert waiting, "mutation completed while policy activation held the organization lock"
    assert row_available, "mutation held a domain row while waiting for the organization lock"
    return result


def test_core_action_waiting_on_activation_obeys_workflow_pause(
    db_engine,
    observation_engine,
    committed_approval,
):
    seeded = committed_approval
    org_id, user_id = seeded.session.org_id, seeded.session.user_id
    action = {"action_type": "add_note", "content": "Must not execute after pause"}
    with SessionLocal(bind=db_engine) as db:
        workflow = AutomationWorkflow(
            organization_id=org_id,
            name="Activation pause",
            scope="org",
            subject_type="surrogate",
            trigger_type="surrogate_created",
            actions=[action],
            is_enabled=True,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        db.add(workflow)
        db.flush()
        execution = WorkflowExecution(
            organization_id=org_id,
            workflow_id=workflow.id,
            event_id=uuid4(),
            depth=0,
            event_source="system",
            trigger_event={},
            entity_type="surrogate",
            entity_id=seeded.surrogate_id,
            subject_type="surrogate",
            subject_id=seeded.surrogate_id,
            status="running",
            authority_snapshot=None,
        )
        db.add(execution)
        db.commit()
        workflow_id, execution_id = workflow.id, execution.id

    def pause(activation):
        activation.query(AutomationWorkflow).filter_by(
            id=workflow_id, organization_id=org_id
        ).update({"is_enabled": False})

    def mutate(db):
        workflow = db.get(AutomationWorkflow, workflow_id)
        execution = db.get(WorkflowExecution, execution_id)
        record = db.get(Surrogate, seeded.surrogate_id)
        assert workflow.is_enabled
        # Prior workflow actions commit and release the initial execution lock.
        db.commit()
        return WorkflowEngineCore(DefaultWorkflowDomainAdapter())._execute_authorized_action(
            workflow=workflow,
            execution=execution,
            db=db,
            action=action,
            entity=record,
            entity_type="surrogate",
            event_id=execution.event_id,
            depth=0,
            workflow_scope="org",
            workflow_creator_user_id=user_id,
            workflow_execution_id=execution_id,
            subject_type="surrogate",
            subject_id=record.id,
        )

    result = _race_activation(
        db_engine,
        observation_engine,
        org_id,
        Surrogate,
        seeded.surrogate_id,
        mutate,
        activation_change=pause,
    )
    assert result["success"] is False
    assert result["error"] == "Workflow execution is paused"
    with SessionLocal(bind=db_engine) as db:
        assert db.query(EntityNote).filter_by(entity_id=seeded.surrogate_id).count() == 0


@pytest.mark.parametrize(
    "entrypoint", ["approval", "executor", "workflow", "status_review", "mutation_scope"]
)
def test_mutation_rechecks_policy_after_activation(
    db_engine,
    observation_engine,
    committed_approval,
    entrypoint,
):
    seeded = committed_approval
    org_id, user_id = seeded.session.org_id, seeded.session.user_id
    row_model, row_id = AIActionApproval, seeded.approval_id
    if entrypoint == "mutation_scope":
        row_model, row_id = Surrogate, seeded.surrogate_id
    if entrypoint == "status_review":
        with SessionLocal(bind=db_engine) as db:
            request = StatusChangeRequest(
                organization_id=org_id,
                entity_type="surrogate",
                entity_id=seeded.surrogate_id,
                target_stage_id=seeded.target_stage_id,
                effective_at=datetime.now(UTC),
                reason="Synthetic review",
                requested_by_user_id=user_id,
            )
            db.add(request)
            db.commit()
            row_model, row_id = StatusChangeRequest, request.id

    def mutate(db):
        if entrypoint == "mutation_scope":
            return record_scope_service.require_mutation_scope(
                db, seeded.session, "surrogate", seeded.surrogate_id
            )
        if entrypoint == "approval":
            return ai_action_approval_service.approve_action_for_session(
                db,
                approval_id=seeded.approval_id,
                session=seeded.session,
            )
        if entrypoint == "executor":
            return ai_action_executor.execute_action(
                db,
                db.get(AIActionApproval, seeded.approval_id),
                user_id,
                org_id,
                seeded.surrogate_id,
                {"approve_ai_actions", "edit_surrogate_notes"},
            )
        if entrypoint == "workflow":
            return DefaultWorkflowDomainAdapter().execute_action(
                db,
                {"action_type": "add_note", "content": "Synthetic action"},
                db.get(Surrogate, seeded.surrogate_id),
                "surrogate",
                uuid4(),
                0,
                workflow_execution_id=uuid4(),
                workflow_creator_user_id=user_id,
            )
        return status_change_request_service.approve_request(
            db,
            row_id,
            org_id,
            user_id,
            admin_role=Role.DEVELOPER,
        )

    result = _race_activation(
        db_engine,
        observation_engine,
        org_id,
        row_model,
        row_id,
        mutate,
        revoke=entrypoint != "workflow",
    )
    with SessionLocal(bind=db_engine) as db:
        notes = db.query(EntityNote).filter_by(entity_id=seeded.surrogate_id).all()
        if entrypoint == "workflow":
            assert result["success"] is True
            assert len(notes) == 1
            assert notes[0].author_id == SYSTEM_USER_ID
        else:
            assert (
                result == 403
                if entrypoint != "executor"
                else result["error_code"] == "permission_denied"
            )
            assert notes == []
            assert db.get(AIActionApproval, seeded.approval_id).status == "pending"
            assert db.get(Surrogate, seeded.surrogate_id).stage_id == seeded.initial_stage_id
            if entrypoint == "status_review":
                assert db.get(StatusChangeRequest, row_id).status == "pending"


@pytest.mark.parametrize("entrypoint", ["accept", "delivery", "withdraw_cancel"])
def test_match_mutation_waits_for_activation_before_domain_locks(
    db_engine,
    observation_engine,
    monkeypatch,
    entrypoint,
):
    with _committed_org(db_engine, monkeypatch) as (org_id, user_id):
        monkeypatch.setattr(audit_service, "log_event", lambda *args, **kwargs: None)
        with SessionLocal(bind=db_engine) as db:
            surrogate = _surrogate(db, org_id, user_id)
            match = _proposal(
                db,
                org_id,
                user_id,
                surrogate,
                create_ip(db, org_id),
                "M10001",
                status={
                    "accept": "under_review",
                    "delivery": "accepted",
                    "withdraw_cancel": "cancellation_pending",
                }[entrypoint],
            )
            match_id, surrogate_id = match.id, surrogate.id
            row_model, row_id = Match, match_id
            if entrypoint == "withdraw_cancel":
                request = StatusChangeRequest(
                    organization_id=org_id,
                    entity_type="match",
                    entity_id=match_id,
                    target_status="cancelled",
                    effective_at=datetime.now(UTC),
                    reason="Synthetic cancellation",
                    requested_by_user_id=user_id,
                )
                db.add(request)
                db.flush()
                row_model, row_id = StatusChangeRequest, request.id
            db.commit()

        def mutate(db):
            if entrypoint == "accept":
                match_lifecycle.transition(
                    db,
                    db.get(Match, match_id),
                    "accept",
                    actor_user_id=user_id,
                    actor_role=Role.DEVELOPER,
                    dispatch_effects=False,
                )
            elif entrypoint == "delivery":
                record = db.get(Surrogate, surrogate_id)
                pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
                stage = pipeline_service.get_stage_by_key(db, pipeline.id, "delivered")
                match_lifecycle.complete_on_delivery(
                    db, record, stage, actor_user_id=user_id, now=datetime.now(UTC)
                )
            else:
                status_change_request_service.cancel_request(db, row_id, org_id, user_id)

        _race_activation(db_engine, observation_engine, org_id, row_model, row_id, mutate)
        with SessionLocal(bind=db_engine) as db:
            assert db.get(Match, match_id).status == (
                "completed" if entrypoint == "delivery" else "accepted"
            )
            if entrypoint == "withdraw_cancel":
                assert db.get(StatusChangeRequest, row_id).status == "cancelled"
