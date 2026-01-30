"""
Tests for AI workflow generation and action execution.
"""

import json
import uuid
from datetime import datetime, timezone

from app.core.encryption import hash_email
from app.db.models import Surrogate, EntityNote, Task, EmailTemplate, PipelineStage, AISettings
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse
from app.services.ai_workflow_service import GeneratedWorkflow, validate_workflow
from app.services.ai_action_executor import (
    AddNoteExecutor,
    CreateTaskExecutor,
    UpdateStatusExecutor,
    get_executor,
    ACTION_PERMISSIONS,
)
from app.utils.normalization import normalize_email


# =============================================================================
# AI Workflow Validation Tests
# =============================================================================


def test_ai_workflow_prompt_anonymizes_users(db, test_org, test_user, monkeypatch):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        anonymize_pii=True,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()

    captured = []
    workflow_payload = {
        "name": "Test Workflow",
        "description": "Test",
        "icon": "zap",
        "trigger_type": "surrogate_created",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [{"action_type": "add_note", "content": "Hello"}],
    }

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content=json.dumps(workflow_payload),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    from app.services import ai_workflow_service

    result = ai_workflow_service.generate_workflow(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Create a workflow",
    )

    combined = "\n".join(msg.content for msg in captured)
    assert test_user.email not in combined
    assert test_user.display_name not in combined
    assert result.success is True


def test_ai_workflow_prompt_filters_templates_by_scope(db, test_org, test_user, monkeypatch):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        anonymize_pii=False,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()

    # Templates: org + personal (owner) + personal (other)
    org_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Org Template",
        subject="Test",
        body="Test body",
        scope="org",
        created_by_user_id=test_user.id,
    )
    owner_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Owner Template",
        subject="Test",
        body="Test body",
        scope="personal",
        owner_user_id=test_user.id,
        created_by_user_id=test_user.id,
    )

    from app.db.models import User, Membership
    from app.db.enums import Role

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:6]}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add(other_user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
        )
    )
    db.flush()

    other_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Other Template",
        subject="Test",
        body="Test body",
        scope="personal",
        owner_user_id=other_user.id,
        created_by_user_id=other_user.id,
    )

    db.add_all([org_template, owner_template, other_template])
    db.flush()

    captured = []
    workflow_payload = {
        "name": "Test Workflow",
        "description": "Test",
        "icon": "zap",
        "trigger_type": "surrogate_created",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [{"action_type": "add_note", "content": "Hello"}],
    }

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content=json.dumps(workflow_payload),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    from app.services import ai_workflow_service

    ai_workflow_service.generate_workflow(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Create a workflow",
        scope="personal",
    )
    combined = "\n".join(msg.content for msg in captured)
    assert str(org_template.id) in combined
    assert str(owner_template.id) in combined
    assert str(other_template.id) not in combined

    captured.clear()
    ai_workflow_service.generate_workflow(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Create a workflow",
        scope="org",
    )
    combined = "\n".join(msg.content for msg in captured)
    assert str(org_template.id) in combined
    assert str(owner_template.id) not in combined
    assert str(other_template.id) not in combined


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
            trigger_type="surrogate_created",
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
            trigger_type="surrogate_created",
            actions=[],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("at least one action" in e.lower() for e in result.errors)

    def test_validate_invalid_action_type(self, db, test_org):
        """Should fail with invalid action type."""
        workflow = GeneratedWorkflow(
            name="Invalid Action",
            trigger_type="surrogate_created",
            actions=[{"action_type": "invalid_action"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("Invalid action type" in e for e in result.errors)

    def test_validate_missing_required_field(self, db, test_org):
        """Should fail when action missing required field."""
        workflow = GeneratedWorkflow(
            name="Missing Field",
            trigger_type="surrogate_created",
            actions=[{"action_type": "add_note"}],  # Missing content
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("content" in e.lower() for e in result.errors)

    def test_validate_invalid_condition_field(self, db, test_org):
        """Should fail with invalid condition field."""
        workflow = GeneratedWorkflow(
            name="Invalid Condition",
            trigger_type="surrogate_created",
            conditions=[{"field": "invalid_field", "operator": "equals", "value": "test"}],
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("invalid field" in e.lower() for e in result.errors)

    def test_validate_invalid_condition_logic(self, db, test_org):
        """Should fail with invalid condition logic."""
        workflow = GeneratedWorkflow(
            name="Invalid Logic",
            trigger_type="surrogate_created",
            condition_logic="INVALID",
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("condition_logic" in e.lower() for e in result.errors)

    def test_validate_in_list_operator_normalizes(self, db, test_org):
        """in_list operator should normalize to in."""
        workflow = GeneratedWorkflow(
            name="In List",
            trigger_type="surrogate_created",
            conditions=[{"field": "state", "operator": "in_list", "value": ["CA", "TX"]}],
            actions=[{"action_type": "add_note", "content": "test"}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert result.valid
        assert not any("unknown operator" in w.lower() for w in result.warnings)
        assert workflow.conditions[0]["operator"] == "in"

    def test_validate_nonexistent_template_id(self, db, test_org):
        """Should fail with non-existent template ID."""
        workflow = GeneratedWorkflow(
            name="Bad Template",
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(uuid.uuid4())}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert not result.valid
        assert any("Email template" in e and "not found" in e for e in result.errors)

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
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(template.id)}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert result.valid
        assert not any("Template ID does not exist" in e for e in result.errors)

    def test_validate_org_scope_rejects_personal_template(self, db, test_org, test_user):
        """Org workflows should not use personal templates."""
        personal_template = EmailTemplate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Personal Template",
            subject="Test",
            body="Test body",
            scope="personal",
            owner_user_id=test_user.id,
            created_by_user_id=test_user.id,
        )
        db.add(personal_template)
        db.flush()

        workflow = GeneratedWorkflow(
            name="Org Workflow",
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(personal_template.id)}],
        )
        result = validate_workflow(db, test_org.id, workflow, scope="org")
        assert not result.valid
        assert any("Org workflows cannot use personal email templates" in e for e in result.errors)

    def test_validate_personal_scope_rejects_other_owner_template(self, db, test_org, test_user):
        """Personal workflows should only use templates owned by the workflow owner."""
        from app.db.models import User, Membership
        from app.db.enums import Role

        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:6]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.INTAKE_SPECIALIST,
            )
        )
        db.flush()

        personal_template = EmailTemplate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Other Personal Template",
            subject="Test",
            body="Test body",
            scope="personal",
            owner_user_id=other_user.id,
            created_by_user_id=other_user.id,
        )
        db.add(personal_template)
        db.flush()

        workflow = GeneratedWorkflow(
            name="Personal Workflow",
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(personal_template.id)}],
        )
        result = validate_workflow(
            db, test_org.id, workflow, scope="personal", owner_user_id=test_user.id
        )
        assert not result.valid
        assert any("Personal email templates must be owned" in e for e in result.errors)

    def test_validate_personal_scope_accepts_owner_template(self, db, test_org, test_user):
        """Personal workflows can use templates owned by the workflow owner."""
        personal_template = EmailTemplate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Owned Personal Template",
            subject="Test",
            body="Test body",
            scope="personal",
            owner_user_id=test_user.id,
            created_by_user_id=test_user.id,
        )
        db.add(personal_template)
        db.flush()

        workflow = GeneratedWorkflow(
            name="Personal Workflow",
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(personal_template.id)}],
        )
        result = validate_workflow(
            db, test_org.id, workflow, scope="personal", owner_user_id=test_user.id
        )
        assert result.valid

    def test_validate_org_scope_accepts_org_template(self, db, test_org, test_user):
        """Org workflows can use org templates."""
        org_template = EmailTemplate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Org Template",
            subject="Test",
            body="Test body",
            scope="org",
            created_by_user_id=test_user.id,
        )
        db.add(org_template)
        db.flush()

        workflow = GeneratedWorkflow(
            name="Org Workflow",
            trigger_type="surrogate_created",
            actions=[{"action_type": "send_email", "template_id": str(org_template.id)}],
        )
        result = validate_workflow(db, test_org.id, workflow, scope="org")
        assert result.valid


# =============================================================================
# AI Workflow Save Tests
# =============================================================================


def test_save_workflow_respects_personal_scope(db, test_org, test_user):
    """AI save should create personal workflows when scope=personal."""
    from app.services import ai_workflow_service

    workflow = GeneratedWorkflow(
        name="AI Personal Workflow",
        trigger_type="surrogate_created",
        actions=[{"action_type": "add_note", "content": "Hello"}],
    )
    saved = ai_workflow_service.save_workflow(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        workflow=workflow,
        scope="personal",
    )

    assert saved.scope == "personal"
    assert saved.owner_user_id == test_user.id

    def test_validate_update_status_action_normalizes(self, db, test_org, default_stage):
        """update_status should normalize to update_field stage_id."""
        workflow = GeneratedWorkflow(
            name="Update Status",
            trigger_type="surrogate_created",
            actions=[{"action_type": "update_status", "stage_id": str(default_stage.id)}],
        )
        result = validate_workflow(db, test_org.id, workflow)
        assert result.valid
        assert workflow.actions[0]["action_type"] == "update_field"
        assert workflow.actions[0]["field"] == "stage_id"


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
        valid, error = executor.validate({"content": "test note"}, db, test_user.id, test_org.id)
        assert valid
        assert error is None

    def test_validate_accepts_body_alias(self, db, test_user, test_org):
        """Should accept 'body' as alias for content."""
        executor = AddNoteExecutor()
        valid, error = executor.validate({"body": "test note"}, db, test_user.id, test_org.id)
        assert valid

    def test_execute_creates_note(self, db, test_user, test_org, default_stage):
        """Should create a note on the case."""
        normalized_email = normalize_email("test@example.com")
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="manual",
            surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
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

        note = db.query(EntityNote).filter(EntityNote.id == uuid.UUID(result["note_id"])).first()
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
        valid, error = executor.validate({"title": "Follow up"}, db, test_user.id, test_org.id)
        assert valid

    def test_execute_creates_task(self, db, test_user, test_org, default_stage):
        """Should create a task for the case."""
        normalized_email = normalize_email("test@example.com")
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="manual",
            surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
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
        assert task.surrogate_id == case.id


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

        normalized_email = normalize_email("test@example.com")
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            full_name="Test Case",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="manual",
            surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
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
        assert case.stage_id == new_stage.id, "In-memory stage_id mismatch. Case re-queried?"
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
        """add_note requires edit_surrogate_notes."""
        assert ACTION_PERMISSIONS["add_note"] == "edit_surrogate_notes"

    def test_create_task_permission(self):
        """create_task requires create_tasks."""
        assert ACTION_PERMISSIONS["create_task"] == "create_tasks"

    def test_update_status_permission(self):
        """update_status requires change_surrogate_status."""
        assert ACTION_PERMISSIONS["update_status"] == "change_surrogate_status"

    def test_send_email_permission(self):
        """send_email requires edit_surrogates."""
        assert ACTION_PERMISSIONS["send_email"] == "edit_surrogates"
