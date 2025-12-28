"""
Tests for AI workflow generation and action execution.
"""

import uuid


from app.db.models import Case, EntityNote, Task, EmailTemplate, PipelineStage
from app.services.ai_workflow_service import GeneratedWorkflow, validate_workflow
from app.services.ai_action_executor import (
    AddNoteExecutor,
    CreateTaskExecutor,
    UpdateStatusExecutor,
    get_executor,
    ACTION_PERMISSIONS,
)


# =============================================================================
# AI Workflow Validation Tests
# =============================================================================


class TestWorkflowValidation:
    """Tests for workflow validation logic."""

    def test_validate_invalid_trigger_type(self, db, test_org):
        """Should fail with invalid trigger type."""
        workflow = GeneratedWorkflow(
            name="Test Workflow",
            trigger_type="invalid_trigger",
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("Invalid trigger type" in e for e in result.errors)

    def test_validate_valid_trigger_type(self, db, test_org):
        """Should pass with valid trigger type and action."""
        workflow = GeneratedWorkflow(
            name="Test Workflow",
            trigger_type="case_created",
            actions=[{"action_type": "add_note", "content": "test note"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        # May have warnings but shouldn't have trigger errors
        assert not any("Invalid trigger type" in e for e in result.errors)

    def test_validate_inactivity_requires_days(self, db, test_org):
        """Inactivity trigger must have days config."""
        workflow = GeneratedWorkflow(
            name="Inactivity Workflow",
            trigger_type="inactivity",
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("days" in e.lower() for e in result.errors)

    def test_validate_inactivity_with_days(self, db, test_org):
        """Inactivity trigger with days should pass."""
        workflow = GeneratedWorkflow(
            name="Inactivity Workflow",
            trigger_type="inactivity",
            trigger_config={"days": 7},
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not any("days" in e.lower() for e in result.errors)

    def test_validate_scheduled_requires_cron(self, db, test_org):
        """Scheduled trigger must have cron config."""
        workflow = GeneratedWorkflow(
            name="Scheduled Workflow",
            trigger_type="scheduled",
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("cron" in e.lower() for e in result.errors)

    def test_validate_no_actions_fails(self, db, test_org):
        """Workflow must have at least one action."""
        workflow = GeneratedWorkflow(
            name="No Actions",
            trigger_type="case_created",
            actions=[],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("at least one action" in e.lower() for e in result.errors)

    def test_validate_invalid_action_type(self, db, test_org):
        """Should fail with invalid action type."""
        workflow = GeneratedWorkflow(
            name="Invalid Action",
            trigger_type="case_created",
            actions=[{"action_type": "invalid_action"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("Invalid action type" in e for e in result.errors)

    def test_validate_missing_required_field(self, db, test_org):
        """Should fail when action missing required field."""
        workflow = GeneratedWorkflow(
            name="Missing Field",
            trigger_type="case_created",
            actions=[{"action_type": "add_note"}],  # Missing content
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("content" in e.lower() for e in result.errors)

    def test_validate_invalid_condition_field(self, db, test_org):
        """Should fail with invalid condition field."""
        workflow = GeneratedWorkflow(
            name="Invalid Condition",
            trigger_type="case_created",
            conditions=[
                {"field": "invalid_field", "operator": "equals", "value": "test"}
            ],
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("invalid field" in e.lower() for e in result.errors)

    def test_validate_invalid_condition_logic(self, db, test_org):
        """Should fail with invalid condition logic."""
        workflow = GeneratedWorkflow(
            name="Invalid Logic",
            trigger_type="case_created",
            condition_logic="INVALID",
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("condition_logic" in e.lower() for e in result.errors)

    def test_validate_nonexistent_template_id(self, db, test_org):
        """Should fail with non-existent template ID."""
        workflow = GeneratedWorkflow(
            name="Bad Template",
            trigger_type="case_created",
            actions=[{"action_type": "send_email", "template_id": str(uuid.uuid4())}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("Template ID does not exist" in e for e in result.errors)

    def test_validate_existing_template_id(self, db, test_org, test_user):
        """Should pass with existing template ID."""
        template = EmailTemplate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Test Template",
            subject="Test",
            body="Test body",
            created_by_user_id=test_user.id,
        )
        db.add(template)
        db.flush()

        workflow = GeneratedWorkflow(
            name="Valid Template",
            trigger_type="case_created",
            actions=[{"action_type": "send_email", "template_id": str(template.id)}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not any("Template ID does not exist" in e for e in result.errors)


# =============================================================================
# AI Action Executor Tests
# =============================================================================


class TestAddNoteExecutor:
    """Tests for AddNoteExecutor."""

    def test_validate_requires_content(self, db, test_user, test_org):
        """Should fail without note content."""
        executor = AddNoteExecutor()
        valid, error = executor.validate({}, db, test_user.id, test_org.id)
        assert not valid
        assert "content" in error.lower()

    def test_validate_with_content(self, db, test_user, test_org):
        """Should pass with content."""
        executor = AddNoteExecutor()
        valid, error = executor.validate(
            {"content": "test note"}, db, test_user.id, test_org.id
        )
        assert valid
        assert error is None

    def test_validate_accepts_body_alias(self, db, test_user, test_org):
        """Should accept 'body' as alias for content."""
        executor = AddNoteExecutor()
        valid, error = executor.validate(
            {"body": "test note"}, db, test_user.id, test_org.id
        )
        assert valid

    def test_execute_creates_note(self, db, test_user, test_org, default_stage):
        """Should create a note on the case."""
        case = Case(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email="test@example.com",
            source="manual",
            case_number=f"C-{uuid.uuid4().hex[:6]}",
            owner_type="user",
            owner_id=test_user.id,
        )
        db.add(case)
        db.flush()

        executor = AddNoteExecutor()
        result = executor.execute(
            {"content": "AI generated note"}, db, test_user.id, test_org.id, case.id
        )

        assert result["success"]
        assert "note_id" in result

        note = (
            db.query(EntityNote)
            .filter(EntityNote.id == uuid.UUID(result["note_id"]))
            .first()
        )
        assert note is not None
        assert "AI generated note" in note.content


class TestCreateTaskExecutor:
    """Tests for CreateTaskExecutor."""

    def test_validate_requires_title(self, db, test_user, test_org):
        """Should fail without task title."""
        executor = CreateTaskExecutor()
        valid, error = executor.validate({}, db, test_user.id, test_org.id)
        assert not valid
        assert "title" in error.lower()

    def test_validate_with_title(self, db, test_user, test_org):
        """Should pass with title."""
        executor = CreateTaskExecutor()
        valid, error = executor.validate(
            {"title": "Follow up"}, db, test_user.id, test_org.id
        )
        assert valid

    def test_execute_creates_task(self, db, test_user, test_org, default_stage):
        """Should create a task for the case."""
        case = Case(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email="test@example.com",
            source="manual",
            case_number=f"C-{uuid.uuid4().hex[:6]}",
            owner_type="user",
            owner_id=test_user.id,
        )
        db.add(case)
        db.flush()

        executor = CreateTaskExecutor()
        result = executor.execute(
            {"title": "Follow up call", "description": "Call the client"},
            db,
            test_user.id,
            test_org.id,
            case.id,
        )

        assert result["success"]
        assert "task_id" in result

        task = db.query(Task).filter(Task.id == uuid.UUID(result["task_id"])).first()
        assert task is not None
        assert task.title == "Follow up call"
        assert task.case_id == case.id


class TestUpdateStatusExecutor:
    """Tests for UpdateStatusExecutor."""

    def test_validate_requires_stage_id(self, db, test_user, test_org):
        """Should fail without stage_id."""
        executor = UpdateStatusExecutor()
        valid, error = executor.validate({}, db, test_user.id, test_org.id)
        assert not valid
        assert "stage_id" in error.lower()

    def test_validate_with_valid_stage(self, db, test_user, test_org, default_stage):
        """Should pass with valid stage_id."""
        executor = UpdateStatusExecutor()
        valid, error = executor.validate(
            {"stage_id": str(default_stage.id)}, db, test_user.id, test_org.id
        )
        assert valid

    def test_execute_updates_status(self, db, test_user, test_org, default_stage):
        """Should update case status."""
        # Create a second stage in the SAME pipeline as default_stage
        new_stage = PipelineStage(
            id=uuid.uuid4(),
            pipeline_id=default_stage.pipeline_id,
            slug="in-progress",
            stage_type="progress",
            label="In Progress",
            color="#3b82f6",
            order=2,
            is_active=True,
        )
        db.add(new_stage)
        db.flush()

        case = Case(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email="test@example.com",
            source="manual",
            case_number=f"C-{uuid.uuid4().hex[:6]}",
            owner_type="user",
            owner_id=test_user.id,
        )
        db.add(case)
        db.flush()

        executor = UpdateStatusExecutor()
        result = executor.execute(
            {"stage_id": str(new_stage.id)}, db, test_user.id, test_org.id, case.id
        )

        assert result["success"], f"Expected success but got: {result}"
        assert result["new_stage_id"] == str(new_stage.id)

        # Check case in-memory before refresh
        assert case.stage_id == new_stage.id, (
            "In-memory stage_id mismatch. Case re-queried?"
        )
        assert case.status_label == "In Progress"


# =============================================================================
# Executor Registry Tests
# =============================================================================


class TestExecutorRegistry:
    """Tests for executor registry."""

    def test_get_executor_add_note(self):
        """Should return AddNoteExecutor."""
        executor = get_executor("add_note")
        assert executor is not None
        assert isinstance(executor, AddNoteExecutor)

    def test_get_executor_create_task(self):
        """Should return CreateTaskExecutor."""
        executor = get_executor("create_task")
        assert executor is not None
        assert isinstance(executor, CreateTaskExecutor)

    def test_get_executor_update_status(self):
        """Should return UpdateStatusExecutor."""
        executor = get_executor("update_status")
        assert executor is not None
        assert isinstance(executor, UpdateStatusExecutor)

    def test_get_executor_unknown(self):
        """Should return None for unknown action."""
        executor = get_executor("unknown_action")
        assert executor is None


class TestActionPermissions:
    """Tests for action permission mapping."""

    def test_add_note_permission(self):
        """add_note requires edit_case_notes."""
        assert ACTION_PERMISSIONS["add_note"] == "edit_case_notes"

    def test_create_task_permission(self):
        """create_task requires create_tasks."""
        assert ACTION_PERMISSIONS["create_task"] == "create_tasks"

    def test_update_status_permission(self):
        """update_status requires change_case_status."""
        assert ACTION_PERMISSIONS["update_status"] == "change_case_status"

    def test_send_email_permission(self):
        """send_email requires edit_cases."""
        assert ACTION_PERMISSIONS["send_email"] == "edit_cases"
