import uuid

import pytest

from app.core.encryption import hash_email
from app.db.enums import WorkflowEventSource, WorkflowExecutionStatus
from app.db.models import AutomationWorkflow, Surrogate, WorkflowExecution
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_retry_failed_workflow_execution_creates_new_execution(
    authed_client, db, test_org, test_user, default_stage
):
    email = f"retry-{uuid.uuid4().hex[:8]}@example.com"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Retry Surrogate",
        email=normalize_email(email),
        email_hash=hash_email(normalize_email(email)),
    )
    db.add(surrogate)
    db.flush()

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Retry workflow {uuid.uuid4().hex[:6]}",
        description=None,
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Retry note"}],
        is_enabled=True,
        is_system_workflow=False,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    failed_execution = WorkflowExecution(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="surrogate",
        entity_id=surrogate.id,
        trigger_event={"surrogate_id": str(surrogate.id)},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic failure",
        duration_ms=0,
    )
    db.add(failed_execution)
    db.flush()

    retry_res = await authed_client.post(f"/workflows/executions/{failed_execution.id}/retry")
    assert retry_res.status_code == 200
    data = retry_res.json()

    assert data["id"] != str(failed_execution.id)
    assert data["workflow_id"] == str(workflow.id)
    assert data["entity_id"] == str(surrogate.id)
    assert data["status"] == "success"
