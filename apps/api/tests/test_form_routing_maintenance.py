"""Release repair is repeatable and isolated to the selected organization."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models import (
    AuditLog,
    AutomationWorkflow,
    Job,
    Organization,
    Task,
    WorkflowExecution,
)
from app.services.form_routing_maintenance_service import repair_routing_window
from app.services.workflow_engine import engine
from tests.test_form_routing import routing_submission


def test_release_repair_routes_missing_jobs_and_preserves_history(db, test_org, test_user):
    released_at = datetime.now(UTC) - timedelta(hours=1)
    fixtures = {}
    for state in ("missing", "old_completed", "new_completed", "new_failed", "rejected", "foreign"):
        org = test_org
        if state == "foreign":
            org = Organization(name="Other organization", slug=f"foreign-{uuid4().hex}")
            db.add(org)
            db.flush()
        form, submission = routing_submission(db, org.id, test_user.id)
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
    assert repair_routing_window(db, org_id=test_org.id, released_at=released_at) == {
        "workflows": 2,
        "submissions": 3,
    }
    assert workflows[0].actions == original
    assert all(
        submission.match_status == "workflow_pending" for _, _, submission in fixtures.values()
    )
    assert repair_routing_window(db, org_id=test_org.id, released_at=released_at, apply=True) == {
        "workflows": 2,
        "submissions": 3,
    }
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
    assert repair_routing_window(db, org_id=test_org.id, released_at=released_at, apply=True) == {
        "workflows": 0,
        "submissions": 0,
    }


@pytest.mark.parametrize("action_type", ["auto_match_submission", "create_intake_lead"])
def test_rollout_approval_resume_skips_whole_legacy_workflow(
    db, test_org, test_user, action_type, caplog
):
    form, submission = routing_submission(db, test_org.id, test_user.id)
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Old release",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=[{"action_type": action_type}, {"action_type": "send_notification"}],
    )
    db.add(workflow)
    db.flush()
    execution = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid4(),
        depth=0,
        event_source="system",
        trigger_event={},
        entity_type="form_submission",
        entity_id=submission.id,
        subject_type="form_submission",
        subject_id=submission.id,
        status="paused",
        paused_at_action_index=0,
        matched_conditions=True,
        actions_executed=[],
    )
    db.add(execution)
    db.flush()
    task = Task(
        organization_id=test_org.id,
        title="Approval",
        task_type="workflow_approval",
        status="completed",
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        workflow_execution_id=execution.id,
        workflow_action_index=0,
        workflow_action_type=action_type,
        workflow_action_payload={"action_type": action_type},
    )
    db.add(task)
    db.flush()
    execution.paused_task_id = task.id
    db.commit()
    engine.continue_execution(db, execution.id, task, "approved")
    db.refresh(execution)
    db.refresh(submission)
    assert execution.status == "paused"
    assert execution.paused_task_id == task.id
    assert execution.actions_executed == []
    assert submission.match_status == "workflow_pending"
    assert submission.intake_lead_id is None
    assert "Skipped retired routing workflow resume" in caplog.text


def test_release_repair_validates_before_writing(db, test_org):
    with pytest.raises(ValueError, match="timezone"):
        repair_routing_window(db, org_id=test_org.id, released_at=datetime(2026, 10, 3), apply=True)
    with pytest.raises(ValueError, match="Organization not found"):
        repair_routing_window(db, org_id=uuid4(), released_at=datetime.now(UTC), apply=True)
