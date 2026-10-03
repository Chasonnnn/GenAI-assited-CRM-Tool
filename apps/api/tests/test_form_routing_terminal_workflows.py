"""Ending a legacy approval never makes form routing depend on its decision."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Form, Job, Notification, Organization, Task
from app.jobs.handlers.workflows import process_workflow_approval_expiry, process_workflow_resume
from app.schemas.permission_policy import PermissionPolicyChanges
from app.services import form_routing_service, permission_policy_service, task_service
from app.services.form_routing_maintenance_service import repair_routing_window
from app.services.workflow_engine import engine
from tests.test_form_routing import routing_submission
from tests.test_form_routing_maintenance import _paused_submission
from tests.test_forms import _create_surrogate

NOTICE = {"action_type": "send_notification", "recipients": "creator", "requires_approval": True}
RETIRED = [{"action_type": "auto_match_submission"}, {"action_type": "create_intake_lead"}]


async def _terminate(db, execution, task, path):
    if path == "expiry_sweep":
        task.due_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        await process_workflow_approval_expiry(
            db, SimpleNamespace(organization_id=task.organization_id)
        )
        job = (
            db.query(Job)
            .filter_by(
                organization_id=task.organization_id,
                job_type="workflow_resume",
                idempotency_key=f"{execution.id}:{task.workflow_action_index}",
            )
            .one()
        )
        await process_workflow_resume(db, job)
    elif path == "denied_job":
        task_service.resolve_workflow_approval(
            db, task.id, task.organization_id, "deny", task.owner_id
        )
        job = (
            db.query(Job)
            .filter_by(
                organization_id=task.organization_id,
                job_type="workflow_resume",
                idempotency_key=f"{execution.id}:{task.workflow_action_index}",
            )
            .one()
        )
        await process_workflow_resume(db, job)
    else:
        engine.continue_execution(db, execution.id, task, "approve")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,expected",
    [
        ("denied_core", "canceled"),
        ("expired_core", "expired"),
        ("denied_job", "canceled"),
        ("expiry_sweep", "expired"),
        ("missing_entity", "failed"),
        ("missing_donor", "failed"),
        ("missing_payload", "failed"),
        ("invalid_snapshot", "failed"),
        ("missing_approver", "failed"),
        ("task_creation_failed", "failed"),
        ("unexpected_status", "failed"),
    ],
)
async def test_terminal_legacy_approval_routes_submission(
    db, test_org, test_user, monkeypatch, path, expected
):
    actions = [NOTICE, *RETIRED]
    if path in {"missing_approver", "task_creation_failed"}:
        actions = [NOTICE, NOTICE, *RETIRED]
    task_status = {"denied_core": "denied", "expired_core": "expired"}.get(path, "completed")
    if path in {"denied_job", "expiry_sweep", "unexpected_status"}:
        task_status = "pending"
    submission, _, execution, task = _paused_submission(
        db, test_org, test_user, actions, current_actions=[NOTICE], task_status=task_status
    )
    if path == "missing_entity":
        monkeypatch.setattr(engine.adapter, "get_entity", lambda *_: None)
    elif path == "missing_donor":
        execution.subject_type, execution.subject_id = "egg_donor", uuid4()
    elif path == "missing_payload":
        task.workflow_action_payload = None
    elif path == "invalid_snapshot":
        execution.trigger_event = {"_form_submission_workflow_actions": [NOTICE, None, *RETIRED]}
    elif path == "missing_approver":
        monkeypatch.setattr(
            engine, "_resolve_approval_context", lambda **_: (None, None, "No approver")
        )
    elif path == "task_creation_failed":
        monkeypatch.setattr(engine.adapter, "create_approval_task", lambda **_: None)
    db.commit()

    await _terminate(db, execution, task, path)
    db.refresh(execution)
    db.refresh(submission)
    assert execution.status == expected
    assert execution.paused_task_id is None and execution.paused_at_action_index is None
    assert submission.match_status == "routing_review" and submission.routing_review_step == "match"
    review = db.query(Task).filter_by(form_submission_id=submission.id, task_type="review").one()
    assert review.organization_id == test_org.id and review.status == "pending"
    audit_count = db.query(AuditLog).filter_by(target_id=submission.id).count()
    engine.continue_execution(db, execution.id, task, "approve")
    assert db.query(Task).filter_by(form_submission_id=submission.id).one().id == review.id
    assert db.query(AuditLog).filter_by(target_id=submission.id).count() == audit_count


@pytest.mark.parametrize(
    "shape", ["none", "before", "snapshot_overrides_live", "linked", "foreign", "foreign_form"]
)
def test_terminal_legacy_approval_does_not_route_ineligible_submission(
    db, test_org, test_user, default_stage, shape
):
    actions, index = [NOTICE, *RETIRED], 0
    if shape in {"none", "snapshot_overrides_live"}:
        actions = [NOTICE]
    elif shape == "before":
        actions, index = [*RETIRED, NOTICE], 2
    submission, workflow, execution, task = _paused_submission(
        db,
        test_org,
        test_user,
        actions,
        current_actions=[NOTICE],
        index=index,
        task_status="denied",
    )
    if shape == "snapshot_overrides_live":
        workflow.actions = [NOTICE, *RETIRED]
    elif shape == "linked":
        submission.surrogate_id = _create_surrogate(db, test_org.id, test_user.id, default_stage).id
    elif shape in {"foreign", "foreign_form"}:
        other = Organization(name="Other", slug=uuid4().hex)
        db.add(other)
        db.flush()
        foreign_form, foreign_submission = routing_submission(db, other.id, test_user.id)
        if shape == "foreign":
            execution.entity_id = execution.subject_id = foreign_submission.id
            submission = foreign_submission
        else:
            submission.form_id = foreign_form.id
    db.commit()
    engine.continue_execution(db, execution.id, task, "deny")
    db.refresh(submission)
    assert submission.match_status == "workflow_pending" and submission.routing_review_step is None
    assert db.query(Task).filter_by(form_submission_id=submission.id).count() == 0
    assert db.query(AuditLog).filter_by(target_id=submission.id).count() == 0


@pytest.mark.parametrize("source", ["snapshot", "live"])
def test_terminal_legacy_approval_routes_paused_retired_action(db, test_org, test_user, source):
    submission, workflow, execution, task = _paused_submission(
        db, test_org, test_user, [RETIRED[0]], current_actions=[], task_status="denied"
    )
    if source == "live":
        execution.trigger_event = {}
        workflow.actions = [RETIRED[0]]
    form = db.get(Form, submission.form_id)
    form.routing_exact_match = "auto"
    db.commit()
    engine.continue_execution(db, execution.id, task, "deny")
    db.refresh(submission)
    assert (
        submission.match_status == "routing_review"
        and submission.routing_review_step == "create_lead"
    )
    assert db.query(Task).filter_by(form_submission_id=submission.id).one().status == "pending"


@pytest.mark.parametrize("status", ["denied", "expired", "completed"])
def test_terminal_routing_failure_keeps_execution_closed(
    db, test_org, test_user, monkeypatch, status
):
    notice = {**NOTICE, "recipients": [str(test_user.id)]}
    submission, _, execution, task = _paused_submission(
        db,
        test_org,
        test_user,
        [notice, notice, *RETIRED],
        current_actions=[notice, notice],
        task_status=status,
    )
    monkeypatch.setattr(engine.adapter, "create_approval_task", lambda **_: None)
    original_audit = form_routing_service._audit

    def fail_audit(*args, **kwargs):
        original_audit(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("routing audit unavailable")

    monkeypatch.setattr(form_routing_service, "_audit", fail_audit)
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as resume_db:
        with pytest.raises(RuntimeError, match="routing audit unavailable"):
            engine.continue_execution(
                resume_db, execution.id, resume_db.get(Task, task.id), "approve"
            )
    db.expire_all()
    assert (
        execution.status
        == {"denied": "canceled", "expired": "expired", "completed": "failed"}[status]
    )
    assert execution.paused_task_id is None and execution.paused_at_action_index is None
    assert submission.match_status == "workflow_pending" and submission.routing_review_step is None
    assert db.query(Task).filter_by(form_submission_id=submission.id).count() == 0
    assert db.query(AuditLog).filter_by(target_id=submission.id).count() == 0
    monkeypatch.setattr(form_routing_service, "_audit", original_audit)
    execute = Mock(side_effect=AssertionError("Approved action ran again"))
    monkeypatch.setattr(engine.adapter, "execute_action", execute)
    engine.continue_execution(db, execution.id, task, "approve")
    execute.assert_not_called()
    assert db.query(Notification).filter_by(entity_id=submission.id).count() == (
        status == "completed"
    )


@pytest.mark.parametrize("path", ["owner_change", "repair"])
def test_cancellation_batch_routes_only_its_organization(
    db, test_org, test_user, default_stage, path
):
    other = Organization(name="Other", slug=uuid4().hex)
    db.add(other)
    db.flush()
    record = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    now = datetime.now(UTC)
    rows = []
    for org in (test_org, test_org, other):
        actions = RETIRED if path == "repair" else [NOTICE, *RETIRED]
        submission, workflow, execution, task = _paused_submission(
            db, org, test_user, actions, current_actions=[NOTICE]
        )
        execution.executed_at = now - timedelta(minutes=5)
        # Routing is attached to the canceled execution, independent of submission age.
        submission.submitted_at = now - timedelta(days=120)
        task.surrogate_id = record.id
        rows.append((submission, workflow, execution, task))
    db.commit()
    if path == "owner_change":
        assert (
            task_service.invalidate_pending_approvals_for_surrogate(
                db, record.id, "Owner changed", test_user.id
            )
            == 2
        )
    else:
        result = repair_routing_window(
            db,
            org_id=test_org.id,
            window_start=now - timedelta(minutes=10),
            released_at=now,
            apply=True,
        )
        assert set(result["submission_ids"]) == {str(row[0].id) for row in rows[:2]}
    for i, (submission, _, execution, task) in enumerate(rows):
        for row in (submission, execution, task):
            db.refresh(row)
        if i < 2:
            assert execution.status == "canceled"
            assert (
                submission.match_status == "routing_review"
                and submission.routing_review_step == "match"
            )
            assert (
                db.query(Task).filter_by(form_submission_id=submission.id).one().status == "pending"
            )
        else:
            assert execution.status == "paused" and task.status == "pending"
            assert submission.match_status == "workflow_pending"
            assert db.query(Task).filter_by(form_submission_id=submission.id).count() == 0


@pytest.mark.parametrize("fail_routing", [False, True])
def test_policy_cancellations_share_routing_transaction(
    db, test_org, test_user, monkeypatch, fail_routing
):
    rows = [
        _paused_submission(db, test_org, test_user, [NOTICE, *RETIRED], current_actions=[NOTICE])
        for _ in range(2)
    ]
    other = Organization(name="Other", slug=uuid4().hex)
    db.add(other)
    db.flush()
    foreign_submission, _, foreign_execution, _ = _paused_submission(
        db, other, test_user, [NOTICE, *RETIRED], current_actions=[NOTICE]
    )
    changes = PermissionPolicyChanges(
        execution_resolutions=[
            {"item_type": "workflow", "id": workflow.id, "action": "pause"}
            for _, workflow, _, _ in rows
        ]
    )
    reviewed = permission_policy_service.preview(db, test_org.id, changes)
    assert reviewed.ready
    original_audit = form_routing_service._audit
    calls = 0

    def fail_second_routing(*args, **kwargs):
        nonlocal calls
        original_audit(*args, **kwargs)
        args[0].flush()
        calls += 1
        if calls == 2:
            raise RuntimeError("Second routing failed")

    if fail_routing:
        monkeypatch.setattr(form_routing_service, "_audit", fail_second_routing)
        with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as policy_db:
            with pytest.raises(RuntimeError, match="Second routing failed"):
                permission_policy_service.activate(
                    policy_db, test_org.id, test_user.id, changes, reviewed.digest
                )
    else:
        result = permission_policy_service.activate(
            db, test_org.id, test_user.id, changes, reviewed.digest
        )
        assert result.version == 2
    db.expire_all()
    assert permission_policy_service.get_version(db, test_org.id) == (1 if fail_routing else 2)
    assert db.query(AuditLog).filter_by(
        organization_id=test_org.id, target_type="permission_policy"
    ).count() == (0 if fail_routing else 1)
    for submission, _, execution, _ in rows:
        assert execution.status == "canceled"
        assert execution.paused_task_id is None and execution.paused_at_action_index is None
        assert submission.match_status == ("workflow_pending" if fail_routing else "routing_review")
        assert db.query(Task).filter_by(form_submission_id=submission.id).count() == (
            0 if fail_routing else 1
        )
        assert db.query(Notification).filter_by(
            entity_type="form", entity_id=submission.form_id
        ).count() == (0 if fail_routing else 1)
    assert (
        foreign_execution.status == "paused"
        and foreign_submission.match_status == "workflow_pending"
    )


def test_deferred_routing_requires_callbacks_before_writing():
    db = Mock()
    with pytest.raises(ValueError, match="callback"):
        form_routing_service.route_submission(
            db, org_id=uuid4(), submission_id=uuid4(), commit=False
        )
    assert db.mock_calls == []
