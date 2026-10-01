"""Workflow triggers fired by platform events outside the workflow engine."""

from __future__ import annotations

import uuid

from app.db.enums import WorkflowTriggerType
from app.db.models import WorkflowExecution
from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.schemas.workflow import WorkflowCreate
from app.services import surrogate_service, workflow_service


def _note_workflow(db, org_id, user_id, trigger_type, trigger_config=None, **extra):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"{trigger_type.value} {uuid.uuid4()}",
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            actions=[{"action_type": "add_note", "content": "Workflow ran"}],
            **extra,
        ),
    )


def _executed_workflow_ids(db, org_id, entity_id) -> set[uuid.UUID]:
    return {
        execution.workflow_id
        for execution in db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.entity_id == entity_id,
        )
        .all()
    }


def _create_surrogate(db, org_id, user_id):
    return surrogate_service.create_surrogate(
        db=db,
        org_id=org_id,
        user_id=user_id,
        data=SurrogateCreate(
            full_name="Workflow Trigger Surrogate",
            email=f"workflow-trigger-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )


def test_user_edit_fires_surrogate_updated_for_watched_fields_only(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    watches_state = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["state"]},
    )
    watches_priority = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["is_priority"]},
    )

    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(state="TX"),
        user_id=test_user.id,
        org_id=test_org.id,
    )

    executed = _executed_workflow_ids(db, test_org.id, surrogate.id)
    assert watches_state.id in executed
    assert watches_priority.id not in executed

    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(is_priority=True),
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert watches_priority.id in _executed_workflow_ids(db, test_org.id, surrogate.id)


def test_unchanged_or_uncommitted_edit_does_not_fire_surrogate_updated(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    surrogate_service.update_surrogate(
        db, surrogate, SurrogateUpdate(state="CA"), user_id=test_user.id, org_id=test_org.id
    )
    workflow = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["state"]},
    )

    surrogate_service.update_surrogate(
        db, surrogate, SurrogateUpdate(state="CA"), user_id=test_user.id, org_id=test_org.id
    )
    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(state="NV"),
        user_id=test_user.id,
        org_id=test_org.id,
        commit=False,
    )

    assert workflow.id not in _executed_workflow_ids(db, test_org.id, surrogate.id)
