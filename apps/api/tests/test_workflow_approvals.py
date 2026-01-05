"""Tests for workflow approval functionality."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.db.enums import (
    TaskType,
    TaskStatus,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
    OwnerType,
)
from app.db.models import (
    Task,
    Case,
    User,
    AutomationWorkflow,
    WorkflowExecution,
    Queue,
)
from app.core.constants import SYSTEM_USER_ID
from app.core.encryption import hash_email
from app.utils.normalization import normalize_email
from app.utils.business_hours import (
    is_business_day,
    is_business_time,
    add_business_hours,
    calculate_approval_due_date,
)
from app.services.workflow_action_preview import build_action_preview, render_action_payload


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_case(db, test_org, test_user, default_stage):
    """Create a test case owned by test_user."""
    normalized = normalize_email("testcase@example.com")
    case = Case(
        id=uuid4(),
        organization_id=test_org.id,
        case_number=f"C-{uuid4().hex[:6].upper()}",  # Max 10 chars
        full_name="Test Case",
        email=normalized,
        email_hash=hash_email(normalized),
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
    )
    db.add(case)
    db.flush()
    return case


# =============================================================================
# Business Hours Tests
# =============================================================================


class TestBusinessHoursCalculator:
    """Test the 48 business hours calculator."""

    def test_is_business_day_weekday(self):
        """Monday-Friday should be business days (if not holiday)."""
        # Monday Jan 6, 2025 - pass datetime not date
        monday = datetime(2025, 1, 6, 12, 0, tzinfo=timezone.utc)
        assert is_business_day(monday) is True

    def test_is_business_day_weekend(self):
        """Saturday and Sunday should not be business days."""
        # Saturday Jan 4, 2025
        saturday = datetime(2025, 1, 4, 12, 0, tzinfo=timezone.utc)
        assert is_business_day(saturday) is False

    def test_is_business_day_holiday(self):
        """US federal holidays should not be business days."""
        # New Year's Day 2025 - pass datetime not date
        new_years = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert is_business_day(new_years) is False

    def test_is_business_time_during_hours(self):
        """10am on a weekday should be business time."""
        # Monday Jan 6, 2025 at 10:00am
        monday_10am = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)
        assert is_business_time(monday_10am) is True

    def test_is_business_time_before_hours(self):
        """7am on a weekday should not be business time."""
        monday_7am = datetime(2025, 1, 6, 7, 0, tzinfo=timezone.utc)
        assert is_business_time(monday_7am) is False

    def test_is_business_time_after_hours(self):
        """7pm on a weekday should not be business time."""
        monday_7pm = datetime(2025, 1, 6, 19, 0, tzinfo=timezone.utc)
        assert is_business_time(monday_7pm) is False

    def test_is_business_time_weekend(self):
        """12pm on Saturday should not be business time."""
        saturday_noon = datetime(2025, 1, 4, 12, 0, tzinfo=timezone.utc)
        assert is_business_time(saturday_noon) is False

    def test_add_business_hours_same_day(self):
        """Adding 2 hours at 10am should result in 12pm same day."""
        start = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)
        result = add_business_hours(start, 2, "UTC")
        assert result.hour == 12
        assert result.day == 6

    def test_add_business_hours_spans_days(self):
        """Adding 10 hours should span to next business day."""
        # Start at 2pm Monday, add 10 hours
        # 4 hours left Monday (2pm-6pm), then 6 hours Tuesday (8am-2pm)
        start = datetime(2025, 1, 6, 14, 0, tzinfo=timezone.utc)
        result = add_business_hours(start, 10, "UTC")
        assert result.day == 7  # Tuesday
        assert result.hour == 14  # 2pm

    def test_add_business_hours_skips_weekend(self):
        """Hours added on Friday afternoon should skip to Monday."""
        # Friday Jan 3, 2025 at 5pm, add 2 hours
        # 1 hour left Friday (5pm-6pm), weekend skipped, 1 hour Monday (8am-9am)
        friday_5pm = datetime(2025, 1, 3, 17, 0, tzinfo=timezone.utc)
        result = add_business_hours(friday_5pm, 2, "UTC")
        assert result.weekday() == 0  # Monday
        assert result.hour == 9

    def test_add_48_business_hours(self):
        """48 business hours = ~5 business days (4.8 days at 10 hrs/day)."""
        # Monday 9am, add 48 hours
        # Mon: 9 hours (9am-6pm), Tue-Thu: 30 hours, Fri: 9 hours = 48 total
        monday_9am = datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)
        result = add_business_hours(monday_9am, 48, "UTC")
        # Should be Friday at 5pm (9+10+10+10+9=48)
        assert result.weekday() == 4  # Friday
        assert result.hour == 17  # 5pm

    def test_calculate_approval_due_date(self):
        """Due date should be 48 business hours from now."""
        now = datetime.now(timezone.utc)
        due = calculate_approval_due_date(now, None, None)
        assert due > now


# =============================================================================
# Action Preview Tests
# =============================================================================


class TestWorkflowActionPreview:
    """Test the action preview builder."""

    def test_preview_assign_case(self, db, test_user, test_org):
        """Preview for assign_case should show assignee name."""
        action = {
            "action_type": "assign_case",
            "owner_type": "user",
            "owner_id": str(test_user.id),
        }

        # Mock entity with case_number
        class MockCase:
            case_number = "1234"
            id = uuid4()

        preview = build_action_preview(db, action, MockCase())
        assert "Assign" in preview
        assert "Case #1234" in preview

    def test_preview_create_task(self, db, test_user, test_org):
        """Preview for create_task should show title and due days."""
        action = {
            "action_type": "create_task",
            "title": "Follow up call",
            "due_days": 3,
            "assignee": "owner",
        }

        class MockCase:
            case_number = "5678"
            id = uuid4()
            owner_type = "user"
            owner_id = test_user.id

        preview = build_action_preview(db, action, MockCase())
        assert "Follow up call" in preview
        assert "3 day" in preview

    def test_render_action_payload(self):
        """Payload should include action config and entity context."""
        action = {
            "action_type": "assign_case",
            "owner_type": "user",
            "owner_id": "abc-123",
        }

        class MockEntity:
            id = uuid4()
            organization_id = uuid4()

        payload = render_action_payload(action, MockEntity())
        assert payload["action_type"] == "assign_case"
        assert payload["owner_type"] == "user"
        assert "entity_id" in payload
        assert "organization_id" in payload


# =============================================================================
# Task Service Tests
# =============================================================================


class TestWorkflowApprovalTaskService:
    """Test the task service workflow approval functions."""

    def test_resolve_approval_approve(self, db, test_org, test_user, test_case):
        """Approving should complete the task and queue resume job."""
        from app.services import task_service

        # Create a workflow execution
        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        # Create approval task owned by test_user
        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        # Resolve as approve
        result = task_service.resolve_workflow_approval(
            db=db,
            task_id=task.id,
            org_id=test_org.id,
            decision="approve",
            user_id=test_user.id,
            reason=None,
        )

        assert result.status == TaskStatus.COMPLETED.value
        assert result.is_completed is True

    def test_resolve_approval_deny(self, db, test_org, test_user, test_case):
        """Denying should mark task as denied with reason."""
        from app.services import task_service

        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        result = task_service.resolve_workflow_approval(
            db=db,
            task_id=task.id,
            org_id=test_org.id,
            decision="deny",
            user_id=test_user.id,
            reason="Not appropriate for this case",
        )

        assert result.status == TaskStatus.DENIED.value
        assert result.workflow_denial_reason == "Not appropriate for this case"

    def test_resolve_approval_wrong_user(self, db, test_org, test_user, test_case):
        """Non-owner should not be able to resolve approval."""
        from app.services import task_service

        other_user = User(
            email="other@example.com",
            display_name="Other User",
        )
        db.add(other_user)
        db.flush()

        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,  # Owned by test_user
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        # Try to resolve as other_user (should fail)
        with pytest.raises(task_service.WorkflowApprovalError) as exc_info:
            task_service.resolve_workflow_approval(
                db=db,
                task_id=task.id,
                org_id=test_org.id,
                decision="approve",
                user_id=other_user.id,  # Wrong user
                reason=None,
            )

        assert "only the case owner" in str(exc_info.value).lower()

    def test_expire_approval_task(self, db, test_org, test_user, test_case):
        """Expiring should mark task as expired."""
        from app.services import task_service

        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Past due
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        task_service.expire_approval_task(db, task)

        assert task.status == TaskStatus.EXPIRED.value
        assert task.workflow_denial_reason == "Approval timed out"


# =============================================================================
# Endpoint Tests
# =============================================================================


class TestWorkflowApprovalEndpoint:
    """Test the /tasks/{id}/resolve endpoint."""

    @pytest.mark.asyncio
    async def test_resolve_endpoint_approve(
        self, authed_client, db, test_org, test_user, test_case
    ):
        """POST /tasks/{id}/resolve with approve should complete task."""
        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        response = await authed_client.post(
            f"/tasks/{task.id}/resolve",
            json={"decision": "approve"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["is_completed"] is True

    @pytest.mark.asyncio
    async def test_resolve_endpoint_deny(
        self, authed_client, db, test_org, test_user, test_case
    ):
        """POST /tasks/{id}/resolve with deny should mark as denied."""
        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        response = await authed_client.post(
            f"/tasks/{task.id}/resolve",
            json={"decision": "deny", "reason": "Not needed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "denied"
        assert data["workflow_denial_reason"] == "Not needed"

    @pytest.mark.asyncio
    async def test_complete_endpoint_blocks_approvals(
        self, authed_client, db, test_org, test_user, test_case
    ):
        """POST /tasks/{id}/complete should reject workflow approvals."""
        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.commit()

        response = await authed_client.post(f"/tasks/{task.id}/complete")

        assert response.status_code == 400
        assert "resolve" in response.json()["detail"].lower()


# =============================================================================
# Owner Change Tests
# =============================================================================


class TestOwnerChangeInvalidation:
    """Test that changing case owner invalidates pending approvals."""

    def test_owner_change_cancels_approval(self, db, test_org, test_user, test_case):
        """Changing case owner should cancel pending approval."""
        from app.services import task_service

        other_user = User(
            email="newowner@example.com",
            display_name="New Owner",
        )
        db.add(other_user)
        db.flush()

        workflow = AutomationWorkflow(
            organization_id=test_org.id,
            name="Test Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
            trigger_config={},
            conditions=[],
            actions=[{"action_type": "assign_case", "requires_approval": True}],
            is_enabled=True,
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution = WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),  # Required for loop protection
            event_source="test",  # Required
            entity_type="case",
            entity_id=test_case.id,
            status=WorkflowExecutionStatus.PAUSED.value,
            trigger_event={"type": "status_changed"},
            matched_conditions=True,
            actions_executed=[],
        )
        db.add(execution)
        db.flush()

        task = Task(
            organization_id=test_org.id,
            case_id=test_case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title="Approve: Assign case",
            status=TaskStatus.PENDING.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            created_by_user_id=SYSTEM_USER_ID,
            workflow_execution_id=execution.id,
            workflow_action_index=0,
            workflow_action_type="assign_case",
            workflow_action_preview="Assign case to User",
            workflow_action_payload={"action_type": "assign_case"},
            due_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(task)
        db.flush()

        execution.paused_task_id = task.id
        execution.paused_at_action_index = 0
        db.commit()

        # Invalidate approvals for this case
        count = task_service.invalidate_pending_approvals_for_case(
            db=db,
            case_id=test_case.id,
            reason="Case owner changed",
            actor_user_id=other_user.id,
        )

        assert count == 1
        db.refresh(task)
        assert task.status == TaskStatus.DENIED.value
        assert "owner changed" in task.workflow_denial_reason.lower()

        db.refresh(execution)
        assert execution.status == WorkflowExecutionStatus.CANCELED.value
