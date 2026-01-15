"""
Tests for Workflows and AI Workflow Generation.

Tests workflow models, service logic, and AI workflow generation.
"""

from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.utils.normalization import normalize_email

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_workflow(db, test_org, test_user):
    """Create a test workflow."""
    from app.db.models import AutomationWorkflow

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Test Workflow",
        description="A test workflow",
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Welcome to our agency!"}],
        is_enabled=False,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()
    return workflow


# =============================================================================
# Workflow Model Tests
# =============================================================================


def test_workflow_model_creation(db, test_org, test_user):
    """Test AutomationWorkflow model can be created with all fields."""
    from app.db.models import AutomationWorkflow

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Complete Workflow",
        description="Workflow with all fields",
        icon="mail",
        trigger_type="inactivity",
        trigger_config={"days": 7},
        conditions=[{"field": "state", "operator": "equals", "value": "TX"}],
        condition_logic="AND",
        actions=[
            {"action_type": "send_email", "template_id": str(uuid4())},
            {"action_type": "add_note", "content": "Followed up"},
        ],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    assert workflow.id is not None
    assert workflow.created_at is not None
    assert workflow.trigger_config["days"] == 7


def test_workflow_model_with_recurrence(db, test_org, test_user):
    """Test workflow model with recurrence fields."""
    from app.db.models import AutomationWorkflow

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Recurring Workflow",
        trigger_type="scheduled",
        trigger_config={"cron": "0 9 * * 1"},  # Every Monday 9am
        actions=[{"action_type": "add_note", "content": "Weekly check"}],
        is_enabled=True,
        is_system_workflow=False,
        recurrence_mode="recurring",
        recurrence_interval_hours=168,  # Weekly
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    assert workflow.recurrence_mode == "recurring"
    assert workflow.recurrence_interval_hours == 168


# =============================================================================
# Workflow Service Tests
# =============================================================================


def test_workflow_service_list(db, test_org, test_workflow):
    """Test workflow service list function."""
    from app.services import workflow_service

    workflows = workflow_service.list_workflows(db, test_org.id)

    assert len(workflows) == 1
    assert workflows[0].name == "Test Workflow"


def test_workflow_service_get(db, test_org, test_workflow):
    """Test workflow service get function."""
    from app.services import workflow_service

    # Note: get_workflow takes (db, workflow_id, org_id)
    workflow = workflow_service.get_workflow(db, test_workflow.id, test_org.id)

    assert workflow is not None
    assert workflow.name == "Test Workflow"


def test_workflow_service_create(db, test_org, test_user):
    """Test workflow service create function."""
    from app.services import workflow_service
    from app.schemas.workflow import WorkflowCreate
    from app.db.enums import WorkflowTriggerType

    create_data = WorkflowCreate(
        name="New Service Workflow",
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,  # Use enum
        actions=[{"action_type": "add_note", "content": "Created!"}],
    )

    workflow = workflow_service.create_workflow(db, test_org.id, test_user.id, create_data)

    assert workflow is not None
    assert workflow.name == "New Service Workflow"
    # Note: is_enabled defaults to True per schema


def test_workflow_service_update(db, test_org, test_user, test_workflow):
    """Test workflow service update function."""
    from app.services import workflow_service
    from app.schemas.workflow import WorkflowUpdate

    update_data = WorkflowUpdate(
        name="Updated Workflow",
        is_enabled=True,
    )

    # Note: update_workflow takes (db, workflow, user_id, data)
    workflow = workflow_service.update_workflow(db, test_workflow, test_user.id, update_data)

    assert workflow is not None
    assert workflow.name == "Updated Workflow"
    assert workflow.is_enabled is True


def test_workflow_service_delete(db, test_org, test_workflow):
    """Test workflow service delete function."""
    from app.services import workflow_service

    # Note: delete_workflow takes (db, workflow)
    workflow_service.delete_workflow(db, test_workflow)

    # Verify deleted
    workflow = workflow_service.get_workflow(db, test_workflow.id, test_org.id)
    assert workflow is None


# =============================================================================
# AI Workflow Generation Tests (Unit Tests)
# =============================================================================


def test_ai_workflow_service_validation():
    """Test AI workflow validation logic."""
    from app.services.ai_workflow_service import (
        GeneratedWorkflow,
        AVAILABLE_TRIGGERS,
        AVAILABLE_ACTIONS,
    )

    # Valid workflow
    workflow = GeneratedWorkflow(
        name="Test AI Workflow",
        trigger_type="surrogate_created",
        actions=[{"action_type": "add_note", "content": "Hello!"}],
    )

    assert workflow.name == "Test AI Workflow"
    assert workflow.trigger_type in AVAILABLE_TRIGGERS
    assert workflow.actions[0]["action_type"] in AVAILABLE_ACTIONS


def test_ai_workflow_service_triggers():
    """Test that all documented triggers are available."""
    from app.services.ai_workflow_service import AVAILABLE_TRIGGERS

    expected_triggers = [
        "surrogate_created",
        "status_changed",
        "inactivity",
        "scheduled",
        "match_proposed",
        "match_accepted",
        "match_rejected",
        "document_uploaded",
        "note_added",
        "appointment_scheduled",
        "appointment_completed",
    ]

    for trigger in expected_triggers:
        assert trigger in AVAILABLE_TRIGGERS, f"Missing trigger: {trigger}"


def test_ai_workflow_service_actions():
    """Test that all documented actions are available."""
    from app.services.ai_workflow_service import AVAILABLE_ACTIONS

    expected_actions = [
        "send_email",
        "create_task",
        "assign_surrogate",
        "update_status",
        "add_note",
        "send_notification",
    ]

    for action in expected_actions:
        assert action in AVAILABLE_ACTIONS, f"Missing action: {action}"


def test_generated_workflow_model():
    """Test GeneratedWorkflow model validation."""
    from app.services.ai_workflow_service import GeneratedWorkflow

    # Minimal valid workflow
    workflow = GeneratedWorkflow(
        name="Minimal Workflow",
        trigger_type="surrogate_created",
        actions=[{"action_type": "add_note", "content": "Test"}],
    )
    assert workflow.condition_logic == "AND"
    assert workflow.conditions == []

    # Full workflow
    full_workflow = GeneratedWorkflow(
        name="Full Workflow",
        description="A complete workflow",
        icon="sparkles",
        trigger_type="status_changed",
        trigger_config={"from_status": "new"},
        conditions=[{"field": "state", "operator": "equals", "value": "CA"}],
        condition_logic="OR",
        actions=[
            {"action_type": "send_email", "template_id": str(uuid4())},
            {"action_type": "create_task", "title": "Follow up"},
        ],
    )
    assert full_workflow.condition_logic == "OR"
    assert len(full_workflow.conditions) == 1
    assert len(full_workflow.actions) == 2


# =============================================================================
# Workflow Engine Task Mapping
# =============================================================================


def _create_surrogate_for_workflow(db, test_org, test_user, default_stage):
    from app.db.models import Surrogate
    from app.db.enums import OwnerType

    normalized_email = normalize_email("surrogate@example.com")
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number="SUR-1001",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Test Surrogate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        created_by_user_id=test_user.id,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_task_for_workflow(db, test_org, test_user, surrogate_id=None):
    from app.db.models import Task
    from app.db.enums import OwnerType

    task = Task(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_id=surrogate_id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="Follow up",
    )
    db.add(task)
    db.flush()
    return task


def test_task_triggered_workflow_maps_to_surrogate(db, test_org, test_user, default_stage):
    """Task-triggered actions should run against the task's surrogate."""
    from app.db.models import AutomationWorkflow, EntityNote
    from app.db.enums import WorkflowTriggerType
    from app.services.workflow_engine import engine

    surrogate = _create_surrogate_for_workflow(db, test_org, test_user, default_stage)
    task = _create_task_for_workflow(db, test_org, test_user, surrogate_id=surrogate.id)

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Task Due -> Add Note",
        trigger_type=WorkflowTriggerType.TASK_DUE.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Task is due"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_DUE,
        entity_type="task",
        entity_id=task.id,
        event_data={"task_id": str(task.id), "surrogate_id": str(surrogate.id)},
        org_id=test_org.id,
    )

    note = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
            EntityNote.entity_id == surrogate.id,
        )
        .first()
    )

    assert note is not None
    assert "Task is due" in note.content


def test_task_triggered_workflow_skips_without_surrogate(db, test_org, test_user, default_stage):
    """Task-triggered actions should skip when no surrogate is linked."""
    from app.db.models import AutomationWorkflow, EntityNote
    from app.db.enums import WorkflowTriggerType, WorkflowExecutionStatus
    from app.services.workflow_engine import engine

    _create_surrogate_for_workflow(db, test_org, test_user, default_stage)
    task = _create_task_for_workflow(db, test_org, test_user, surrogate_id=None)

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Task Due -> Add Note (No Surrogate)",
        trigger_type=WorkflowTriggerType.TASK_DUE.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Should not run"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_DUE,
        entity_type="task",
        entity_id=task.id,
        event_data={"task_id": str(task.id)},
        org_id=test_org.id,
    )

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecutionStatus.PARTIAL.value
    assert "Task is not linked to a surrogate" in (executions[0].error_message or "")

    note = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
        )
        .first()
    )

    assert note is None
