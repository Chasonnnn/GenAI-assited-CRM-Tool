"""Per-workflow execution history names the surrogate each run acted on."""

import uuid

import pytest

from app.core.encryption import hash_email
from app.db.enums import Role, WorkflowEventSource, WorkflowExecutionStatus, WorkflowTriggerType
from app.db.models import Membership, Organization, Surrogate, User, WorkflowExecution
from app.schemas.workflow import WorkflowCreate
from app.services import workflow_service
from app.utils.normalization import normalize_email


def _surrogate(db, org_id, owner_id, stage, name: str) -> Surrogate:
    email = normalize_email(f"history-{uuid.uuid4().hex[:8]}@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=owner_id,
        created_by_user_id=owner_id,
        full_name=name,
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _execution(db, org_id, workflow_id, surrogate_id) -> WorkflowExecution:
    execution = WorkflowExecution(
        organization_id=org_id,
        workflow_id=workflow_id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="surrogate",
        entity_id=surrogate_id,
        subject_type="surrogate",
        subject_id=surrogate_id,
        trigger_event={"source": "test"},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.SUCCESS.value,
        duration_ms=1,
    )
    db.add(execution)
    db.flush()
    return execution


@pytest.mark.asyncio
async def test_workflow_history_names_surrogates_only_within_the_org(
    authed_client, db, test_org, test_user, default_stage
):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="History labels",
            trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
            actions=[{"action_type": "send_notification", "title": "Hi", "recipients": "owner"}],
        ),
    )
    own = _surrogate(db, test_org.id, test_user.id, default_stage, "Own Record")
    other_org = Organization(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other",
        token_version=1,
        is_active=True,
    )
    db.add(other_user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(), user_id=other_user.id, organization_id=other_org.id, role=Role.ADMIN
        )
    )
    foreign = _surrogate(db, other_org.id, other_user.id, default_stage, "Foreign Record")
    own_run = _execution(db, test_org.id, workflow.id, own.id)
    foreign_run = _execution(db, test_org.id, workflow.id, foreign.id)
    db.commit()

    response = await authed_client.get(f"/workflows/{workflow.id}/executions")

    assert response.status_code == 200, response.text
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert by_id[str(own_run.id)]["entity_name"] == "Own Record"
    assert by_id[str(own_run.id)]["entity_number"] == own.surrogate_number
    assert by_id[str(foreign_run.id)]["entity_name"] is None
    assert "Foreign Record" not in response.text
