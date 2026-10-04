"""Routing is configured on forms and cannot return through workflow write paths."""

import io
import json
import zipfile
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.enums import WorkflowActionType
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services import admin_import_service, ai_workflow_service

RETIRED = ("auto_match_submission", "create_intake_lead")


@pytest.mark.parametrize("action", RETIRED)
@pytest.mark.parametrize("schema", [WorkflowCreate, WorkflowUpdate])
def test_workflow_schemas_reject_retired_routing_actions(action, schema):
    payload = {"actions": [{"action_type": action}]}
    if schema is WorkflowCreate:
        payload.update(name="Retired route", trigger_type="form_submitted")
    with pytest.raises(ValidationError, match=f"Unknown workflow action type: {action}"):
        schema.model_validate(payload)


def test_ai_builder_and_action_enum_only_offer_supported_actions():
    offered = set(ai_workflow_service.AVAILABLE_ACTIONS)
    assert not offered.intersection(RETIRED)
    assert "promote_intake_lead" in offered
    assert offered <= {action.value for action in WorkflowActionType}


@pytest.mark.parametrize("action", RETIRED)
def test_approval_snapshot_cannot_execute_retired_routing_actions(action):
    from app.db.models import FormSubmission
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter

    submission = FormSubmission(
        id=uuid4(),
        organization_id=uuid4(),
        form_id=uuid4(),
        source_mode="shared",
        lead_kind="surrogate",
        match_status="routing_review",
        routing_review_step="match",
    )
    db = Mock()
    result = DefaultWorkflowDomainAdapter().execute_action(
        db=db,
        action={"action_type": action},
        entity=submission,
        entity_type="form_submission",
        event_id=uuid4(),
        depth=0,
    )
    assert result["success"] is False
    assert result["error"] == f"Unknown action type: {action}"
    assert submission.match_status == "routing_review"
    assert submission.routing_review_step == "match"
    assert submission.intake_lead_id is None
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", RETIRED)
async def test_workflow_create_and_update_reject_routing_with_422(authed_client, action):
    payload = {
        "name": f"Staff notice {uuid4()}",
        "trigger_type": "form_submitted",
        "subject_type": "form_submission",
        "scope": "org",
        "actions": [{"action_type": "send_notification", "title": "Review application"}],
    }
    response = await authed_client.post("/workflows", json=payload)
    assert response.status_code == 200, response.text
    workflow_id = response.json()["id"]
    for method, path, body in (
        ("post", "/workflows", {**payload, "actions": [{"action_type": action}]}),
        ("patch", f"/workflows/{workflow_id}", {"actions": [{"action_type": action}]}),
    ):
        response = await getattr(authed_client, method)(path, json=body)
        assert response.status_code == 422, response.text
        assert f"Unknown workflow action type: {action}" in response.text
    response = await authed_client.get(f"/workflows/{workflow_id}")
    assert response.status_code == 200
    assert response.json()["actions"] == payload["actions"]


@pytest.mark.parametrize("action", ["unknown_action"])
@pytest.mark.parametrize("entry", ["workflows.json", "workflow_templates.json"])
def test_admin_import_refuses_unknown_actions_before_any_write(monkeypatch, action, entry):
    monkeypatch.setattr(admin_import_service, "_ensure_empty_org", lambda *_: None)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr(entry, json.dumps([{"actions": [{"action_type": action}]}]))
    db = Mock()
    with pytest.raises(ValueError, match=f"Unknown workflow action type: {action}"):
        admin_import_service.import_org_config_zip(db, uuid4(), archive_bytes.getvalue())
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("action", RETIRED)
def test_rollout_skips_entire_workflow_before_any_action(action, caplog):
    from app.db.models import AutomationWorkflow
    from app.services.workflow_engine_core import WorkflowEngineCore

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=uuid4(),
        subject_type="form_submission",
        actions=[
            {"action_type": "update_field", "field": "is_priority", "value": True},
            {"action_type": action},
        ],
    )
    db, adapter = Mock(), Mock()
    result = WorkflowEngineCore(adapter).execute_workflow(
        db,
        workflow,
        "form_submission",
        uuid4(),
        {"email": "private@example.com"},
    )
    assert result is None
    assert not db.mock_calls
    assert not adapter.mock_calls
    assert str(workflow.id) in caplog.text
    assert str(workflow.organization_id) in caplog.text
    assert "private@example.com" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_generated_leftovers_hidden_but_execution_history_visible(
    authed_client, db, test_org, test_user, enabled
):
    from app.db.models import AutomationWorkflow, WorkflowExecution
    from tests.test_form_routing import routing_submission

    form, submission = routing_submission(db, test_org.id, test_user.id)
    leftover = AutomationWorkflow(
        organization_id=test_org.id,
        name="Retired route",
        scope="org",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=[],
        is_enabled=False,
        is_system_workflow=True,
        system_key=f"shared_intake_routing:{form.id}",
    )
    visible = AutomationWorkflow(
        organization_id=test_org.id,
        name="Staff notice",
        system_key=f"sharedXintakeXrouting:{form.id}",
        scope="org",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=[{"action_type": "send_notification"}],
    )
    retained = AutomationWorkflow(
        organization_id=test_org.id,
        name="Retained generated notification",
        scope="org",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(form.id)},
        actions=[{"action_type": "send_notification", "title": "Received"}],
        is_enabled=enabled,
        is_system_workflow=True,
        system_key=f"shared_intake_routing:{uuid4()}",
    )
    db.add_all([leftover, visible, retained])
    db.flush()
    execution = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=leftover.id,
        event_id=uuid4(),
        depth=0,
        event_source="system",
        trigger_event={},
        entity_type="form_submission",
        entity_id=submission.id,
        subject_type="form_submission",
        subject_id=submission.id,
        status="success",
        actions_executed=[{"action_type": RETIRED[0], "success": True}],
        matched_conditions=True,
    )
    db.add(execution)
    db.commit()
    for path in ("/workflows", f"/forms/{form.id}/workflows"):
        response = await authed_client.get(path)
        assert response.status_code == 200, response.text
        data = response.json()
        entries = data["items"] if isinstance(data, dict) else data
        ids = {row["id"] for row in entries}
        assert str(visible.id) in ids
        assert str(retained.id) in ids
        assert str(leftover.id) not in ids
    for path in ("/workflows/executions", f"/workflows/{leftover.id}/executions"):
        response = await authed_client.get(path)
        assert response.status_code == 200, response.text
        assert str(execution.id) in {row["id"] for row in response.json()["items"]}
