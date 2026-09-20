"""AI approval invariants using real commits and independent PostgreSQL sessions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from queue import Queue
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.core.csrf import CSRF_HEADER
from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import (
    AIActionApproval,
    AIConversation,
    AIMessage,
    AuditLog,
    AutomationWorkflow,
    EmailLog,
    EntityNote,
    Job,
    Membership,
    Notification,
    Organization,
    Pipeline,
    PipelineStage,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
    User,
    UserIntegration,
    WorkflowExecution,
)
from app.db.session import SessionLocal
from app.routers.ai_actions import reject_action
from app.schemas.auth import UserSession
from app.services import (
    ai_action_approval_service,
    ai_action_executor,
    ai_email_service,
    audit_service,
    gmail_service,
    job_service,
    permission_service,
    workflow_triggers,
)


@pytest.fixture
def committed_approval(db_engine, request):
    """No outer savepoint: competing sessions must see committed fixture data."""
    org_id, user_id = uuid4(), uuid4()
    try:
        with SessionLocal(bind=db_engine) as db:
            user = User(
                id=user_id, email=f"approval-{user_id}@example.test", display_name="Reviewer"
            )
            db.add_all(
                [
                    Organization(id=org_id, name="Approval QA", slug=f"approval-{org_id}"),
                    user,
                ]
            )
            db.flush()
            db.add(Membership(user_id=user_id, organization_id=org_id, role=Role.DEVELOPER.value))
            pipeline = Pipeline(organization_id=org_id, name="QA pipeline", is_default=True)
            db.add(pipeline)
            db.flush()
            stages = [
                PipelineStage(
                    pipeline_id=pipeline.id,
                    slug=slug,
                    label=label,
                    color="#000000",
                    stage_type="intake",
                    order=order,
                    is_active=True,
                    is_intake_stage=order == 1,
                )
                for order, slug, label in [(1, "new_unread", "New"), (2, "contacted", "Contacted")]
            ]
            db.add_all(stages)
            db.flush()
            email = f"surrogate-{uuid4()}@example.test"
            surrogate = Surrogate(
                organization_id=org_id,
                surrogate_number="S10001",
                stage_id=stages[0].id,
                status_label=stages[0].label,
                owner_type="user",
                owner_id=user_id,
                created_by_user_id=user_id,
                full_name="Synthetic approval subject",
                email=email,
                email_hash=hash_email(email),
            )
            db.add(surrogate)
            db.flush()
            conversation = AIConversation(
                organization_id=org_id,
                user_id=user_id,
                entity_type="surrogate",
                entity_id=surrogate.id,
            )
            db.add(conversation)
            db.flush()
            message = AIMessage(
                conversation_id=conversation.id, role="assistant", content="Proposal"
            )
            db.add(message)
            db.flush()
            action_type = getattr(request, "param", "add_note")
            payloads = {
                "add_note": {"content": "Reviewed synthetic note"},
                "create_task": {"title": "Reviewed task", "due_date": "2026-10-13"},
                "update_status": {"stage_id": str(stages[1].id)},
                "send_email": {
                    "to": email,
                    "subject": "Reviewed subject",
                    "body": "Reviewed body",
                    "idempotency_key": "untrusted-proposal-key",
                },
            }
            if action_type == "send_email":
                db.add(
                    UserIntegration(
                        user_id=user_id,
                        integration_type="gmail",
                        account_email=user.email,
                        access_token_encrypted="synthetic-token-not-used",
                    )
                )
            approval = AIActionApproval(
                message_id=message.id,
                action_index=0,
                action_type=action_type,
                action_payload=payloads[action_type],
                status="pending",
            )
            db.add(approval)
            db.commit()
            seeded = SimpleNamespace(
                approval_id=approval.id,
                surrogate_id=surrogate.id,
                initial_stage_id=stages[0].id,
                target_stage_id=stages[1].id,
                action_type=action_type,
                session=UserSession(
                    user_id=user_id,
                    org_id=org_id,
                    role=Role.DEVELOPER,
                    email=user.email,
                    display_name=user.display_name,
                ),
            )
        yield seeded
    finally:
        with SessionLocal(bind=db_engine) as db:
            # Only this disposable fixture's immutable audit rows need bypassing.
            db.execute(text("SET LOCAL session_replication_role = replica"))
            db.query(AuditLog).filter(AuditLog.organization_id == org_id).delete()
            db.execute(text("SET LOCAL session_replication_role = origin"))
            db.query(Organization).filter(Organization.id == org_id).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            db.commit()


def _assert_no_domain_changes(db, seeded):
    surrogate = db.get(Surrogate, seeded.surrogate_id)
    assert surrogate.stage_id == seeded.initial_stage_id
    assert surrogate.last_contacted_at is None
    assert surrogate.last_contact_method is None
    assert db.query(EntityNote).filter(EntityNote.entity_id == surrogate.id).count() == 0
    for model in (Task, SurrogateActivityLog, SurrogateStatusHistory):
        assert db.query(model).filter(model.surrogate_id == surrogate.id).count() == 0
    assert (
        db.query(Notification).filter(Notification.organization_id == seeded.session.org_id).count()
        == 0
    )
    assert (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.organization_id == seeded.session.org_id)
        .count()
        == 0
    )


@pytest.mark.parametrize("committed_approval", ["add_note", "send_email"], indirect=True)
@pytest.mark.parametrize("competing_operation", ["approve", "reject"])
def test_competing_decisions_have_one_winner(db_engine, committed_approval, competing_operation):
    seeded = committed_approval
    ready = Queue()

    def decide(operation):
        with SessionLocal(bind=db_engine) as db:
            db.execute(text("SET LOCAL statement_timeout = '15s'"))
            # Keep a stale identity-map entry: locking must also refresh its state.
            cached = db.get(AIActionApproval, seeded.approval_id)
            assert cached.status == "pending"
            ready.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                if operation == "approve":
                    return ai_action_approval_service.approve_action_for_session(
                        db, approval_id=seeded.approval_id, session=seeded.session
                    )["status"]
                return reject_action(seeded.approval_id, db=db, session=seeded.session)["status"]
            except HTTPException as exc:
                assert exc.status_code == 400
                assert "already processed" in exc.detail
                return "already_processed"

    # Queue both operations behind a real row lock. In the broken implementation,
    # they execute before blocking on UPDATE; in the fixed one they block on SELECT.
    with SessionLocal(bind=db_engine) as blocker, ThreadPoolExecutor(max_workers=2) as pool:
        blocker.query(AIActionApproval).filter(
            AIActionApproval.id == seeded.approval_id
        ).with_for_update().one()
        futures = [pool.submit(decide, operation) for operation in ("approve", competing_operation)]
        try:
            pids = [ready.get(timeout=10), ready.get(timeout=10)]
            with db_engine.connect() as monitor:
                deadline = monotonic() + 10
                while monotonic() < deadline:
                    waiting = monitor.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE pid IN (:first, :second) AND wait_event_type = 'Lock'"
                        ),
                        {"first": pids[0], "second": pids[1]},
                    )
                    monitor.rollback()
                    if waiting == 2:
                        break
                    sleep(0.01)
                else:
                    pytest.fail("Both database sessions must reach their contended operation")
        finally:
            blocker.rollback()
        results = [future.result(timeout=15) for future in futures]

    assert results.count("already_processed") == 1
    with SessionLocal(bind=db_engine) as db:
        status = db.get(AIActionApproval, seeded.approval_id).status
        assert status in {"executed", "approved", "rejected"}
        expected_notes = 1 if status == "executed" else 0
        assert (
            db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).count()
            == expected_notes
        )
        audits = db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).all()
        assert [entry.event_type for entry in audits] == [
            "ai_action_approved" if status in {"executed", "approved"} else "ai_action_rejected"
        ]
        assert db.query(Job).filter(Job.organization_id == seeded.session.org_id).count() == (
            1 if status == "approved" else 0
        )


@pytest.mark.parametrize("failure_boundary", ["audit", "commit"])
def test_note_approval_failure_rolls_back_before_workflow(
    db_engine, committed_approval, monkeypatch, failure_boundary
):
    seeded = committed_approval
    with SessionLocal(bind=db_engine) as db:
        db.add(
            AutomationWorkflow(
                organization_id=seeded.session.org_id,
                name="Note follow-up",
                scope="org",
                subject_type="surrogate",
                trigger_type="note_added",
                trigger_config={},
                conditions=[],
                actions=[
                    {
                        "action_type": "send_notification",
                        "title": "Reviewed note saved",
                        "recipients": "all_admins",
                    }
                ],
                is_enabled=True,
                created_by_user_id=seeded.session.user_id,
                updated_by_user_id=seeded.session.user_id,
            )
        )
        db.commit()

    def fail(*args, **kwargs):
        raise RuntimeError("injected transaction failure")

    with SessionLocal(bind=db_engine) as db:
        with monkeypatch.context() as patch:
            if failure_boundary == "audit":
                patch.setattr(audit_service, "log_ai_action_approved", fail)
            else:
                patch.setattr(db, "commit", fail)
            with pytest.raises(RuntimeError, match="injected transaction failure"):
                ai_action_approval_service.approve_action_for_session(
                    db, approval_id=seeded.approval_id, session=seeded.session
                )
        assert not db.in_transaction()

    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "pending"
        _assert_no_domain_changes(db, seeded)
        assert db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).count() == 0
        result = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        assert result["status"] == "executed"

    with SessionLocal(bind=db_engine) as db:
        assert db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).count() == 1
        notification = (
            db.query(Notification)
            .filter(Notification.organization_id == seeded.session.org_id)
            .one()
        )
        assert notification.user_id == seeded.session.user_id
        assert notification.title == "Reviewed note saved"
        execution = (
            db.query(WorkflowExecution)
            .filter(WorkflowExecution.organization_id == seeded.session.org_id)
            .one()
        )
        assert execution.status == "success"
        assert db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).count() == 1


@pytest.mark.parametrize(
    "committed_approval", ["add_note", "create_task", "update_status"], indirect=True
)
def test_unexpected_executor_failure_is_retryable(db_engine, committed_approval, monkeypatch):
    seeded = committed_approval
    executor = ai_action_executor.EXECUTORS[seeded.action_type]
    execute = executor.execute

    def fail_after_write(*args, **kwargs):
        execute(*args, **kwargs)
        raise RuntimeError("injected executor failure")

    with SessionLocal(bind=db_engine) as db:
        with monkeypatch.context() as patch:
            patch.setattr(executor, "execute", fail_after_write)
            with pytest.raises(RuntimeError, match="injected executor failure"):
                ai_action_approval_service.approve_action_for_session(
                    db, approval_id=seeded.approval_id, session=seeded.session
                )
        assert not db.in_transaction()

    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "pending"
        _assert_no_domain_changes(db, seeded)
        assert db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).count() == 0
        result = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        assert result["status"] == "executed"

    with SessionLocal(bind=db_engine) as db:
        if seeded.action_type == "add_note":
            assert (
                db.query(EntityNote)
                .filter(EntityNote.entity_id == seeded.surrogate_id)
                .one()
                .content
                == "Reviewed synthetic note"
            )
            # Preserve the canonical note entry and existing AI-attributed entry.
            expected_activities = 2
        elif seeded.action_type == "create_task":
            task = db.query(Task).filter(Task.surrogate_id == seeded.surrogate_id).one()
            assert task.title == "Reviewed task"
            assert task.due_date.isoformat() == "2026-10-13"
            expected_activities = 1
        else:
            assert db.get(Surrogate, seeded.surrogate_id).stage_id == seeded.target_stage_id
            history = (
                db.query(SurrogateStatusHistory)
                .filter(SurrogateStatusHistory.surrogate_id == seeded.surrogate_id)
                .one()
            )
            assert history.from_stage_id == seeded.initial_stage_id
            assert history.to_stage_id == seeded.target_stage_id
            expected_activities = 1
        assert (
            db.query(SurrogateActivityLog)
            .filter(SurrogateActivityLog.surrogate_id == seeded.surrogate_id)
            .count()
            == expected_activities
        )
        assert (
            db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).one().event_type
            == "ai_action_approved"
        )


def test_workflow_failure_does_not_reopen_committed_approval(
    db_engine, committed_approval, monkeypatch, caplog
):
    seeded = committed_approval
    calls = []

    def fail_workflow(side_effect_db, note):
        # A different session must see the approval already committed.
        with SessionLocal(bind=db_engine) as observer:
            calls.append(observer.get(AIActionApproval, seeded.approval_id).status)
        side_effect_db.add(
            EntityNote(
                organization_id=note.organization_id,
                entity_type=note.entity_type,
                entity_id=note.entity_id,
                author_id=note.author_id,
                content="Must roll back",
            )
        )
        side_effect_db.flush()
        raise RuntimeError("synthetic-sensitive-workflow-failure")

    monkeypatch.setattr(workflow_triggers, "trigger_note_added", fail_workflow)
    with SessionLocal(bind=db_engine) as db:
        result = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        assert result["status"] == "executed"
        with pytest.raises(HTTPException) as error:
            ai_action_approval_service.approve_action_for_session(
                db, approval_id=seeded.approval_id, session=seeded.session
            )
        assert error.value.status_code == 400
    assert calls == ["executed"]
    assert "synthetic-sensitive-workflow-failure" not in caplog.text
    with SessionLocal(bind=db_engine) as db:
        assert db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).count() == 1
        assert db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).count() == 1


@pytest.mark.parametrize("operation", ["approve", "reject"])
@pytest.mark.parametrize("denial", ["other_org", "other_owner"])
def test_decision_denied_without_mutation(db_engine, committed_approval, operation, denial):
    seeded = committed_approval
    updates = (
        {"org_id": uuid4()}
        if denial == "other_org"
        else {
            "user_id": uuid4(),
            "role": Role.INTAKE_SPECIALIST,
        }
    )
    session = seeded.session.model_copy(update=updates)
    with SessionLocal(bind=db_engine) as blocker, SessionLocal(bind=db_engine) as db:
        if denial == "other_org":
            blocker.query(AIActionApproval).filter(
                AIActionApproval.id == seeded.approval_id
            ).with_for_update().one()
            # A foreign tenant must be filtered before attempting to lock this row.
            db.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(HTTPException) as error:
            if operation == "approve":
                ai_action_approval_service.approve_action_for_session(
                    db, approval_id=seeded.approval_id, session=session
                )
            else:
                reject_action(seeded.approval_id, db=db, session=session)
        assert error.value.status_code == (404 if denial == "other_org" else 403)
    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "pending"
        _assert_no_domain_changes(db, seeded)
        assert db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).count() == 0


def test_invalid_action_is_terminal_and_audited(db_engine, committed_approval):
    seeded = committed_approval
    with SessionLocal(bind=db_engine) as db:
        db.get(AIActionApproval, seeded.approval_id).action_payload = {"content": " "}
        db.commit()
        result = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        assert result["status"] == "failed"
        assert result["error"] == "Note content is required"
        with pytest.raises(HTTPException) as error:
            ai_action_approval_service.approve_action_for_session(
                db, approval_id=seeded.approval_id, session=seeded.session
            )
        assert error.value.status_code == 400
    with SessionLocal(bind=db_engine) as db:
        _assert_no_domain_changes(db, seeded)
        assert (
            db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).one().event_type
            == "ai_action_failed"
        )


def test_action_permission_denial_is_terminal_and_audited(
    db_engine, committed_approval, monkeypatch
):
    seeded = committed_approval
    monkeypatch.setattr(
        permission_service, "get_effective_permissions", lambda *args: {"approve_ai_actions"}
    )
    with SessionLocal(bind=db_engine) as db:
        result = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        assert result["status"] == "failed"
        assert result["success"] is False
    with SessionLocal(bind=db_engine) as db:
        _assert_no_domain_changes(db, seeded)
        assert (
            db.query(AuditLog).filter(AuditLog.target_id == seeded.approval_id).one().event_type
            == "ai_action_denied"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["approve", "reject"])
async def test_decisions_require_csrf(authed_client, operation):
    authed_client.headers.pop(CSRF_HEADER, None)
    response = await authed_client.post(f"/ai/actions/{uuid4()}/{operation}")
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
def test_email_approval_commits_intent_without_sending(db_engine, committed_approval, monkeypatch):
    from app.services import gmail_service

    seeded = committed_approval
    calls = []

    async def send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message_id": "synthetic-gmail-id"}

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        response = ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
    assert calls == []
    assert response["success"] is True
    assert response["status"] == "approved"
    with SessionLocal(bind=db_engine) as db:
        approval = db.get(AIActionApproval, seeded.approval_id)
        assert approval.executed_at is None
        job = db.query(Job).filter(Job.organization_id == seeded.session.org_id).one()
        email = db.query(EmailLog).filter(EmailLog.organization_id == seeded.session.org_id).one()
        assert job.job_type == "ai_send_email"
        assert job.payload == {"approval_id": str(approval.id)}
        assert email.job_id == job.id
        assert email.idempotency_key == f"ai:{approval.id}"
        assert email.actor_user_id == seeded.session.user_id
        assert email.status == "pending"
        _assert_no_domain_changes(db, seeded)
        assert db.query(AuditLog).filter(AuditLog.target_id == approval.id).count() == 1


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.parametrize("boundary", ["enqueue", "audit", "commit"])
def test_email_admission_failure_is_atomic(db_engine, committed_approval, monkeypatch, boundary):
    seeded = committed_approval

    def fail(*args, **kwargs):
        raise RuntimeError("injected admission failure")

    with SessionLocal(bind=db_engine) as db:
        with monkeypatch.context() as patch:
            owner, method = {
                "enqueue": (job_service, "enqueue_job"),
                "audit": (audit_service, "log_ai_action_approved"),
                "commit": (db, "commit"),
            }[boundary]
            patch.setattr(owner, method, fail)
            with pytest.raises(RuntimeError, match="injected admission failure"):
                ai_action_approval_service.approve_action_for_session(
                    db, approval_id=seeded.approval_id, session=seeded.session
                )
    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "pending"
        for model in (Job, EmailLog, AuditLog):
            assert (
                db.query(model).filter(model.organization_id == seeded.session.org_id).count() == 0
            )
        _assert_no_domain_changes(db, seeded)


@pytest.fixture
def queued_email(db_engine, committed_approval):
    seeded = committed_approval
    with SessionLocal(bind=db_engine) as db:
        ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        seeded.job_id = db.query(Job).filter(Job.organization_id == seeded.session.org_id).one().id
    return seeded


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.parametrize("outcome", ["sent", "failed", "timeout", "crash"])
@pytest.mark.asyncio
async def test_email_worker_replay_never_resends(db_engine, queued_email, monkeypatch, outcome):
    seeded, calls = queued_email, []

    async def send(**kwargs):
        with SessionLocal(bind=db_engine) as observer:
            assert observer.get(AIActionApproval, seeded.approval_id).status == "approved"
            email = observer.query(EmailLog).filter(EmailLog.job_id == seeded.job_id).one()
            assert email.status == "unknown"
        calls.append(kwargs)
        assert kwargs["max_attempts"] == 1
        assert kwargs["body"] == "Reviewed body"
        assert kwargs["expected_sender"] == seeded.session.email
        if outcome == "crash":
            raise KeyboardInterrupt("synthetic worker crash")
        if outcome == "timeout":
            raise TimeoutError("sensitive provider details")
        return {
            "success": outcome == "sent",
            "message_id": "gmail-receipt",
            "error": "sensitive failure",
        }

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        # Subsequent proposal edits must not alter what was explicitly approved.
        db.get(AIActionApproval, seeded.approval_id).action_payload = {"body": "Unreviewed edit"}
        db.commit()
        if outcome == "crash":
            with pytest.raises(KeyboardInterrupt):
                await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        else:
            await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
    for _ in range(2):
        with SessionLocal(bind=db_engine) as db:
            await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
    assert len(calls) == 1
    with SessionLocal(bind=db_engine) as db:
        approval = db.get(AIActionApproval, seeded.approval_id)
        expected_status = {"sent": "executed", "failed": "failed"}.get(outcome, "delivery_unknown")
        assert approval.status == expected_status
        assert "sensitive" not in (approval.error_message or "")
        notes = db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).all()
        if outcome == "sent":
            assert len(notes) == 1
            assert "Reviewed body" in notes[0].content
            assert "Unreviewed" not in notes[0].content
            assert db.get(Surrogate, seeded.surrogate_id).last_contact_method == "email"
            assert sorted(
                row.activity_type
                for row in db.query(SurrogateActivityLog)
                .filter(SurrogateActivityLog.surrogate_id == seeded.surrogate_id)
                .all()
            ) == ["email_sent", "note_added"]
        else:
            assert notes == []
            _assert_no_domain_changes(db, seeded)
            assert (
                db.query(AuditLog)
                .filter(
                    AuditLog.target_id == seeded.approval_id,
                    AuditLog.event_type == "ai_action_failed",
                )
                .count()
                == 1
            )


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.asyncio
async def test_email_receipt_survives_local_audit_failure(db_engine, queued_email, monkeypatch):
    seeded, calls, workflows = queued_email, [], []

    async def send(**kwargs):
        calls.append(1)
        return {"success": True, "message_id": "gmail-receipt"}

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    def workflow(db, note):
        with SessionLocal(bind=db_engine) as observer:
            workflows.append(observer.get(AIActionApproval, seeded.approval_id).status)

    monkeypatch.setattr(gmail_service, "send_email", send)
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", workflow)
    with SessionLocal(bind=db_engine) as db:
        with monkeypatch.context() as patch:
            patch.setattr(audit_service, "log_event", fail)
            with pytest.raises(RuntimeError, match="injected audit failure"):
                await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
            db.rollback()
    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "approved"
        assert db.query(EmailLog).filter(EmailLog.job_id == seeded.job_id).one().status == "sent"
        _assert_no_domain_changes(db, seeded)
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).count() == 1
    assert calls == [1]
    assert workflows == ["executed"]


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.parametrize("legacy_status", ["pending", "sent"])
@pytest.mark.parametrize("legacy_key", ["approval", "proposal"])
@pytest.mark.asyncio
async def test_old_email_log_recovers_without_resend(
    db_engine, committed_approval, monkeypatch, legacy_status, legacy_key
):
    seeded = committed_approval

    async def no_send(**kwargs):
        pytest.fail("A legacy log is not permission to resend")

    monkeypatch.setattr(gmail_service, "send_email", no_send)
    with SessionLocal(bind=db_engine) as db:
        db.add(
            EmailLog(
                organization_id=seeded.session.org_id,
                idempotency_key=f"ai:{seeded.approval_id}"
                if legacy_key == "approval"
                else "untrusted-proposal-key",
                recipient_email="legacy@example.test",
                subject="Legacy subject",
                body="Legacy body",
                status=legacy_status,
                external_id="legacy-receipt" if legacy_status == "sent" else None,
                sent_at=datetime.now(UTC) if legacy_status == "sent" else None,
            )
        )
        db.commit()
        ai_action_approval_service.approve_action_for_session(
            db, approval_id=seeded.approval_id, session=seeded.session
        )
        job = db.query(Job).filter(Job.organization_id == seeded.session.org_id).one()
        await ai_email_service.process_email(db, job)
        assert db.get(AIActionApproval, seeded.approval_id).status == (
            "executed"
            if legacy_status == "sent" and legacy_key == "approval"
            else "delivery_unknown"
        )


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.asyncio
async def test_lost_provider_receipt_is_not_permission_to_resend(
    db_engine, queued_email, monkeypatch
):
    seeded, calls = queued_email, []

    async def send(**kwargs):
        calls.append(1)
        return {"success": True, "message_id": "receipt-that-will-not-persist"}

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        commit = db.commit

        def fail_receipt_commit():
            if calls:
                raise RuntimeError("injected lost receipt")
            commit()

        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", fail_receipt_commit)
            with pytest.raises(RuntimeError, match="injected lost receipt"):
                await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        db.rollback()
    with SessionLocal(bind=db_engine) as db:
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert db.get(AIActionApproval, seeded.approval_id).status == "delivery_unknown"
        _assert_no_domain_changes(db, seeded)
    assert calls == [1]


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
def test_duplicate_workers_keep_one_provider_attempt(db_engine, queued_email, monkeypatch):
    import asyncio

    seeded, calls = queued_email, []
    started, release = Event(), Event()

    async def send(**kwargs):
        calls.append(1)
        started.set()
        assert release.wait(10)
        return {"success": True, "message_id": "gmail-concurrent"}

    def process():
        with SessionLocal(bind=db_engine) as db:
            asyncio.run(ai_email_service.process_email(db, db.get(Job, seeded.job_id)))

    monkeypatch.setattr(gmail_service, "send_email", send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        original = pool.submit(process)
        try:
            assert started.wait(10)
            pool.submit(process).result(timeout=10)
            with SessionLocal(bind=db_engine) as db:
                assert db.get(AIActionApproval, seeded.approval_id).status == "delivery_unknown"
        finally:
            release.set()
        original.result(timeout=10)
    with SessionLocal(bind=db_engine) as db:
        assert db.get(AIActionApproval, seeded.approval_id).status == "executed"
        assert db.query(EntityNote).filter(EntityNote.entity_id == seeded.surrogate_id).count() == 1
    assert calls == [1]


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.parametrize(
    "denial", ["foreign_org", "foreign_job", "unapproved", "revoked", "inactive_user"]
)
@pytest.mark.asyncio
async def test_email_worker_requires_bound_approval(db_engine, queued_email, monkeypatch, denial):
    seeded = queued_email

    async def no_send(**kwargs):
        pytest.fail("Worker must not send without a tenant-bound active approval")

    monkeypatch.setattr(gmail_service, "send_email", no_send)
    with SessionLocal(bind=db_engine) as db:
        job = db.get(Job, seeded.job_id)
        if denial in {"foreign_org", "foreign_job"}:
            forged = SimpleNamespace(
                id=uuid4() if denial == "foreign_job" else job.id,
                organization_id=uuid4() if denial == "foreign_org" else job.organization_id,
                payload=job.payload,
            )
            with pytest.raises(ValueError, match="not found in job organization"):
                await ai_email_service.process_email(db, forged)
        else:
            if denial == "unapproved":
                db.get(AIActionApproval, seeded.approval_id).status = "pending"
            elif denial == "inactive_user":
                db.get(User, seeded.session.user_id).is_active = False
            else:
                db.query(Membership).filter(
                    Membership.user_id == seeded.session.user_id
                ).one().is_active = False
            db.commit()
            await ai_email_service.process_email(db, job)
            assert db.get(AIActionApproval, seeded.approval_id).status == (
                "pending" if denial == "unapproved" else "failed"
            )
        _assert_no_domain_changes(db, seeded)


@pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True)
@pytest.mark.parametrize("log_status", ["pending", "unknown", "sent"])
@pytest.mark.parametrize("recovery", ["failure", "stale"])
def test_exhausted_email_job_settles_approval(db_engine, queued_email, log_status, recovery):
    from app.worker import WORKER_STALE_CLAIM_RETRY_SAFE_JOB_TYPES

    seeded = queued_email
    with SessionLocal(bind=db_engine) as db:
        job = job_service.claim_job_for_dispatch(db, seeded.job_id)
        job.attempts = job.max_attempts
        job.claimed_at = datetime.now(UTC) - timedelta(hours=1)
        email = db.query(EmailLog).filter(EmailLog.job_id == job.id).one()
        email.status = log_status
        email.error = ai_email_service.DELIVERY_UNKNOWN if log_status == "unknown" else None
        if log_status == "sent":
            email.sent_at, email.external_id = datetime.now(UTC), "saved-receipt"
        db.commit()
        if recovery == "failure":
            job_service.fail_claimed_job(
                db, job_id=job.id, claim_token=job.claim_token, error="synthetic failure"
            )
        else:
            job_service.recover_stale_worker_claims(
                db,
                stale_before=datetime.now(UTC) - timedelta(minutes=5),
                recovered_at=datetime.now(UTC),
                retry_safe_job_types=WORKER_STALE_CLAIM_RETRY_SAFE_JOB_TYPES,
                limit=100,
            )
        assert (
            db.get(AIActionApproval, seeded.approval_id).status
            == {
                "pending": "failed",
                "unknown": "delivery_unknown",
                "sent": "executed",
            }[log_status]
        )
