"""Release repair is repeatable and isolated to the selected organization."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.constants import SYSTEM_USER_ID
from app.db.models import (
    AuditLog,
    AutomationWorkflow,
    Job,
    Organization,
    Task,
    WorkflowExecution,
)
from app.services import workflow_service
from app.services.form_routing_maintenance_service import repair_routing_window
from app.services.workflow_engine import engine
from tests.test_form_routing import routing_submission


def test_release_repair_routes_missing_jobs_and_preserves_history(db, test_org, test_user):
    released_at = datetime.now(UTC) - timedelta(hours=1)
    window_start = released_at - timedelta(hours=1)
    fixtures = {}
    for state in (
        "missing",
        "old_completed",
        "new_completed",
        "new_failed",
        "rejected",
        "foreign",
        "old",
        "after_release",
    ):
        org = test_org
        if state == "foreign":
            org = Organization(name="Other organization", slug=f"foreign-{uuid4().hex}")
            db.add(org)
            db.flush()
        form, submission = routing_submission(db, org.id, test_user.id)
        submission.submitted_at = released_at - timedelta(minutes=30)
        if state == "old":
            submission.submitted_at = released_at - timedelta(days=120)
        elif state == "after_release":
            submission.submitted_at = released_at + timedelta(minutes=10)
        fixtures[state] = (org, form, submission)
        if state == "rejected":
            submission.status = "rejected"
        if state in {"old_completed", "new_completed", "new_failed"}:
            db.add(
                Job(
                    organization_id=org.id,
                    job_type="form_submission_workflow",
                    payload={"submission_id": str(submission.id)},
                    status="failed" if state == "new_failed" else "completed",
                    completed_at=released_at
                    + timedelta(minutes=-10 if state == "old_completed" else 10),
                )
            )
    # A foreign job for this submission must not suppress its same-org repair.
    db.add(
        Job(
            organization_id=fixtures["foreign"][0].id,
            job_type="form_submission_workflow",
            payload={"submission_id": str(fixtures["missing"][2].id)},
            status="completed",
            completed_at=datetime.now(UTC),
        )
    )
    original = [
        {"action_type": "auto_match_submission"},
        {"action_type": "send_notification", "title": "Received"},
    ]
    workflows = []
    for state in ("missing", "old_completed", "foreign"):
        org, form, submission = fixtures[state]
        workflow = AutomationWorkflow(
            organization_id=org.id,
            name=f"Recreated routing {state}",
            scope="org",
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": str(form.id)},
            actions=original[:1] if state == "old_completed" else original,
            is_enabled=True,
            is_system_workflow=True,
            system_key=f"shared_intake_routing:{form.id}",
        )
        db.add(workflow)
        db.flush()
        workflows.append(workflow)
    history = []
    for status in ("success", "running"):
        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflows[0].id,
            event_id=uuid4(),
            depth=0,
            event_source="system",
            entity_type="form_submission",
            entity_id=fixtures["missing"][2].id,
            subject_type="form_submission",
            subject_id=fixtures["missing"][2].id,
            status=status,
            trigger_event={},
            actions_executed=[{"success": True}],
            matched_conditions=True,
        )
        db.add(execution)
        history.append(execution)
    db.commit()
    result = repair_routing_window(
        db, org_id=test_org.id, window_start=window_start, released_at=released_at
    )
    assert result["workflows"] == 2 and result["submissions"] == 3
    assert set(result["workflow_ids"]) == {str(w.id) for w in workflows[:2]}
    assert set(result["submission_ids"]) == {
        str(fixtures[state][2].id) for state in ("missing", "old_completed", "new_failed")
    }
    assert workflows[0].actions == original
    assert all(
        submission.match_status == "workflow_pending" for _, _, submission in fixtures.values()
    )
    assert (
        repair_routing_window(
            db, org_id=test_org.id, window_start=window_start, released_at=released_at, apply=True
        )
        == result
    )
    for state, (_, _, submission) in fixtures.items():
        db.refresh(submission)
        repaired = state in {"missing", "old_completed", "new_failed"}
        assert submission.match_status == ("routing_review" if repaired else "workflow_pending")
        assert submission.routing_review_step == ("match" if repaired else None)
        assert db.query(Task).filter(
            Task.form_submission_id == submission.id, Task.task_type == "review"
        ).count() == int(repaired)
    db.refresh(workflows[0])
    db.refresh(workflows[1])
    db.refresh(workflows[2])
    assert workflows[0].actions == original[1:]
    assert workflows[0].system_key is None
    assert workflows[0].is_system_workflow is False
    assert workflows[1].actions == []
    assert workflows[1].is_enabled is False
    assert workflows[2].actions == original
    audit_entries = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "workflow_config_changed",
        )
        .order_by(AuditLog.created_at, AuditLog.id)
        .all()
    )
    assert len(audit_entries) == 2
    assert audit_entries[1].prev_hash == audit_entries[0].entry_hash
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "workflow_config_changed",
            AuditLog.target_id == workflows[0].id,
        )
        .count()
        == 1
    )
    for execution in history:
        db.refresh(execution)
        assert execution.actions_executed == [{"success": True}]
        assert execution.trigger_event == (
            {} if execution.status == "success" else {"_form_submission_workflow_actions": original}
        )
    assert repair_routing_window(
        db, org_id=test_org.id, window_start=window_start, released_at=released_at, apply=True
    ) == {
        "workflows": 0,
        "submissions": 0,
        "executions": 0,
        "workflow_ids": [],
        "submission_ids": [],
        "execution_ids": [],
    }


def _paused_submission(
    db, org, user, actions, *, current_actions=None, index=0, task_status="pending"
):
    form, submission = routing_submission(db, org.id, user.id)
    workflow = AutomationWorkflow(
        organization_id=org.id,
        name=f"Old release {uuid4()}",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=actions if current_actions is None else current_actions,
        created_by_user_id=user.id,
    )
    db.add(workflow)
    db.flush()
    execution = WorkflowExecution(
        organization_id=org.id,
        workflow_id=workflow.id,
        event_id=uuid4(),
        depth=0,
        event_source="system",
        trigger_event={"_form_submission_workflow_actions": actions},
        entity_type="form_submission",
        entity_id=submission.id,
        subject_type="form_submission",
        subject_id=submission.id,
        status="paused",
        paused_at_action_index=index,
        matched_conditions=True,
        actions_executed=[
            {"action_type": action["action_type"], "success": True} for action in actions[:index]
        ],
    )
    db.add(execution)
    db.flush()
    task = Task(
        organization_id=org.id,
        title="Approval",
        task_type="workflow_approval",
        status=task_status,
        is_completed=task_status == "completed",
        completed_at=datetime.now(UTC) if task_status == "completed" else None,
        completed_by_user_id=user.id if task_status == "completed" else None,
        owner_type="user",
        owner_id=user.id,
        created_by_user_id=user.id,
        workflow_execution_id=execution.id,
        workflow_action_index=index,
        workflow_action_type=actions[index]["action_type"],
        workflow_action_payload=actions[index],
    )
    db.add(task)
    db.flush()
    execution.paused_task_id = task.id
    db.commit()
    return submission, workflow, execution, task


@pytest.mark.parametrize("action_type", ["auto_match_submission", "create_intake_lead"])
@pytest.mark.parametrize("task_status", ["pending", "completed"])
def test_rollout_approval_resume_cancels_legacy_workflow_and_routes_submission(
    db, test_org, test_user, action_type, task_status, caplog
):
    submission, _, execution, task = _paused_submission(
        db,
        test_org,
        test_user,
        [{"action_type": action_type}, {"action_type": "send_notification"}],
        task_status=task_status,
    )
    engine.continue_execution(db, execution.id, task, "approved")
    db.refresh(execution)
    db.refresh(submission)
    assert execution.status == "canceled"
    assert execution.paused_task_id is None
    assert execution.paused_at_action_index is None
    assert execution.actions_executed == []
    assert submission.match_status == "routing_review"
    assert submission.routing_review_step == "match"
    assert submission.intake_lead_id is None
    assert (
        db.query(Task).filter_by(form_submission_id=submission.id, task_type="review").count() == 1
    )
    db.refresh(task)
    assert task.status == "completed"
    if task_status == "pending":
        assert task.is_completed and task.completed_at
        assert task.completed_by_user_id == SYSTEM_USER_ID
    else:
        assert task.completed_by_user_id == test_user.id
    assert "Canceled retired routing execution" in caplog.text
    engine.continue_execution(db, execution.id, task, "approved")
    assert (
        db.query(Task).filter_by(form_submission_id=submission.id, task_type="review").count() == 1
    )


def test_release_repair_validates_before_writing(db, test_org):
    window_start = datetime.now(UTC) - timedelta(hours=1)
    with pytest.raises(ValueError, match="timezone"):
        repair_routing_window(
            db,
            org_id=test_org.id,
            window_start=window_start,
            released_at=datetime(2026, 10, 3),
            apply=True,
        )
    with pytest.raises(ValueError, match="Organization not found"):
        repair_routing_window(
            db, org_id=uuid4(), window_start=window_start, released_at=datetime.now(UTC), apply=True
        )


@pytest.mark.parametrize("action_type", ["auto_match_submission", "create_intake_lead"])
@pytest.mark.parametrize("index", [0, 1])
def test_preserved_snapshot_skips_retired_actions_without_new_approvals(
    db, test_org, test_user, action_type, index
):
    notice = {
        "action_type": "send_notification",
        "title": "Received",
        "recipients": "creator",
        "requires_approval": True,
    }
    retired = {"action_type": action_type, "requires_approval": True}
    submission, _, execution, task = _paused_submission(
        db,
        test_org,
        test_user,
        [notice, retired],
        current_actions=[notice],
        index=index,
        task_status="completed",
    )
    engine.continue_execution(db, execution.id, task, "approved")
    db.refresh(execution)
    db.refresh(submission)
    assert execution.status == "success"
    assert execution.paused_task_id is None and execution.paused_at_action_index is None
    assert execution.actions_executed[-1] == {
        "action_type": action_type,
        "success": True,
        "skipped": True,
        "description": "Skipped retired routing action",
    }
    assert all(action["success"] for action in execution.actions_executed)
    assert db.query(Task).filter_by(workflow_execution_id=execution.id).count() == 1
    assert submission.intake_lead_id is None
    assert submission.match_status == "workflow_pending"


def test_repair_cancels_paused_routing_only_inside_window_and_organization(db, test_org, test_user):
    released_at = datetime.now(UTC) - timedelta(hours=1)
    window_start = released_at - timedelta(hours=1)
    retired = {"action_type": "create_intake_lead", "requires_approval": True}
    notice = {"action_type": "send_notification", "title": "Received"}
    fixtures = {}
    for state in ("inside", "stripped", "old", "after_release", "foreign"):
        org = test_org
        if state == "foreign":
            org = Organization(name="Foreign", slug=uuid4().hex)
            db.add(org)
            db.flush()
        submission, workflow, execution, task = _paused_submission(
            db,
            org,
            test_user,
            [notice, retired],
            index=1,
            current_actions=[notice] if state == "stripped" else None,
        )
        instant = released_at - timedelta(minutes=30)
        if state == "old":
            instant = window_start - timedelta(days=120)
        elif state == "after_release":
            instant = released_at + timedelta(minutes=30)
        submission.submitted_at = execution.executed_at = instant
        fixtures[state] = (submission, execution, task)
    db.commit()
    inventory = repair_routing_window(
        db, org_id=test_org.id, window_start=window_start, released_at=released_at
    )
    expected = {str(fixtures[s][1].id) for s in ("inside", "stripped")}
    assert set(inventory["execution_ids"]) == expected
    result = repair_routing_window(
        db, org_id=test_org.id, window_start=window_start, released_at=released_at, apply=True
    )
    assert set(result["execution_ids"]) == expected
    for state, (submission, execution, task) in fixtures.items():
        for row in (submission, execution, task):
            db.refresh(row)
        repaired = state in {"inside", "stripped"}
        assert execution.status == ("canceled" if repaired else "paused")
        assert task.status == ("completed" if repaired else "pending")
        assert submission.match_status == ("routing_review" if repaired else "workflow_pending")
        if repaired:
            assert execution.paused_task_id is None and execution.paused_at_action_index is None
            assert (
                task.is_completed
                and task.completed_at
                and task.completed_by_user_id == SYSTEM_USER_ID
            )
            assert execution.error_message == "Workflow routing retired"
    again = repair_routing_window(
        db, org_id=test_org.id, window_start=window_start, released_at=released_at, apply=True
    )
    assert again["execution_ids"] == [] and again["submission_ids"] == []


@pytest.mark.parametrize("window_start", [datetime(2026, 10, 3), datetime(2026, 10, 4, tzinfo=UTC)])
def test_repair_rejects_invalid_window_before_database_access(window_start):
    db = Mock()
    with pytest.raises(ValueError, match="timezone|after"):
        repair_routing_window(
            db,
            org_id=uuid4(),
            window_start=window_start,
            released_at=datetime(2026, 10, 3, tzinfo=UTC),
            apply=True,
        )
    assert db.mock_calls == []


@pytest.mark.parametrize("start", [None, "2026-10-03T10:00:00", "2026-10-04T10:00:00Z"])
def test_repair_cli_requires_valid_window_before_opening_session(monkeypatch, capsys, start):
    from app.db import session
    from scripts.repair_form_routing import main

    connect = Mock()
    monkeypatch.setattr(session, "SessionLocal", connect)
    arguments = [
        "repair_form_routing.py",
        "--organization-id",
        str(uuid4()),
        "--released-at",
        "2026-10-03T18:00:00Z",
    ]
    if start is not None:
        arguments += ["--window-start", start]
    monkeypatch.setattr("sys.argv", arguments)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "window" in capsys.readouterr().err.lower()
    connect.assert_not_called()


@pytest.mark.parametrize("state", ["rejected", "foreign"])
def test_retired_resume_cancels_without_routing_ineligible_submission(
    db, test_org, test_user, state
):
    submission, _, execution, task = _paused_submission(
        db, test_org, test_user, [{"action_type": "auto_match_submission"}]
    )
    if state == "rejected":
        submission.status = "rejected"
    else:
        foreign = Organization(name="Foreign", slug=uuid4().hex)
        db.add(foreign)
        db.flush()
        _, submission = routing_submission(db, foreign.id, test_user.id)
        execution.entity_id = execution.subject_id = submission.id
    db.commit()
    engine.continue_execution(db, execution.id, task, "approved")
    db.refresh(execution)
    db.refresh(submission)
    assert execution.status == "canceled"
    assert submission.match_status == "workflow_pending"
    assert submission.routing_review_step is None
    assert db.query(Task).filter_by(form_submission_id=submission.id).count() == 0


@pytest.mark.asyncio
async def test_repair_retained_generated_actions_become_visible(
    authed_client, db, test_org, test_user
):
    form, _ = routing_submission(db, test_org.id, test_user.id)
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Edited generated routing",
        scope="org",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=[
            {"action_type": "auto_match_submission"},
            {"action_type": "send_notification", "title": "Received"},
        ],
        is_enabled=True,
        is_system_workflow=True,
        system_key=f"shared_intake_routing:{form.id}",
    )
    db.add(workflow)
    db.commit()
    released_at = datetime.now(UTC)
    repair_routing_window(
        db,
        org_id=test_org.id,
        window_start=released_at - timedelta(hours=1),
        released_at=released_at,
        apply=True,
    )
    db.refresh(workflow)
    assert workflow.is_enabled and workflow.system_key is None and not workflow.is_system_workflow
    assert workflow.id in {
        w.id for w in workflow_service.list_workflows(db, test_org.id, test_user.id)
    }
    response = await authed_client.get(f"/forms/{form.id}/workflows")
    assert response.status_code == 200, response.text
    assert str(workflow.id) in {w["id"] for w in response.json()}
