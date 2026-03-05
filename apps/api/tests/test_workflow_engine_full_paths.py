from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import (
    OwnerType,
    Role,
    TaskStatus,
    TaskType,
    WorkflowConditionOperator,
    WorkflowEventSource,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)
from app.db.models import (
    AutomationWorkflow,
    EmailTemplate,
    Membership,
    Task,
    User,
    UserWorkflowPreference,
    WorkflowExecution,
)
from app.services import workflow_service
from app.services.workflow_engine_core import MAX_DEPTH, WorkflowEngineCore
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter


class _DummyAdapter:
    def get_entity(self, db, entity_type, entity_id):
        return None

    def get_related_surrogate(self, db, entity_type, entity):
        return None

    def create_approval_task(
        self,
        db,
        workflow,
        execution,
        action,
        action_index,
        entity,
        surrogate,
        owner,
        triggered_by_user_id,
    ):
        return None

    def execute_action(self, **kwargs):
        return {"success": True}


def _create_workflow(
    db,
    *,
    org_id,
    user_id,
    name: str,
    scope: str = "org",
    owner_user_id=None,
    trigger_type: WorkflowTriggerType = WorkflowTriggerType.STATUS_CHANGED,
    trigger_config: dict | None = None,
):
    wf = AutomationWorkflow(
        id=uuid4(),
        organization_id=org_id,
        name=name,
        scope=scope,
        owner_user_id=owner_user_id,
        trigger_type=trigger_type.value,
        trigger_config=trigger_config or {},
        conditions=[],
        actions=[{"action_type": "add_note", "content": "note"}],
        is_enabled=True,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(wf)
    db.flush()
    return wf


def _create_member(db, org_id, *, role: str = Role.DEVELOPER.value, is_active: bool = True):
    user = User(
        id=uuid4(),
        email=f"workflow-{uuid4().hex[:8]}@example.com",
        display_name="Workflow User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=org_id,
        role=role,
        is_active=is_active,
    )
    db.add(membership)
    db.flush()
    return user


def test_workflow_action_normalization_and_trigger_config_validation():
    normalized = workflow_service._normalize_actions_for_trigger(
        WorkflowTriggerType.FORM_SUBMITTED,
        [
            {"action_type": "auto_match_submission"},
            {"action_type": "create_intake_lead"},
        ],
    )
    assert len(normalized) == 2

    with pytest.raises(
        ValueError, match="auto_match_submission must be placed before create_intake_lead"
    ):
        workflow_service._normalize_actions_for_trigger(
            WorkflowTriggerType.FORM_SUBMITTED,
            [
                {"action_type": "create_intake_lead"},
                {"action_type": "auto_match_submission"},
            ],
        )

    workflow_service._validate_trigger_config(
        WorkflowTriggerType.STATUS_CHANGED, {"from_stage_id": None, "to_stage_id": None}
    )
    workflow_service._validate_trigger_config(WorkflowTriggerType.SCHEDULED, {"cron": "0 9 * * 1"})
    workflow_service._validate_trigger_config(WorkflowTriggerType.TASK_DUE, {"hours_before": 24})
    workflow_service._validate_trigger_config(WorkflowTriggerType.INACTIVITY, {"days": 7})
    workflow_service._validate_trigger_config(
        WorkflowTriggerType.SURROGATE_UPDATED, {"fields": ["status_label"]}
    )
    workflow_service._validate_trigger_config(
        WorkflowTriggerType.FORM_STARTED, {"form_id": str(uuid4())}
    )
    workflow_service._validate_trigger_config(
        WorkflowTriggerType.FORM_SUBMITTED, {"form_id": str(uuid4())}
    )
    workflow_service._validate_trigger_config(
        WorkflowTriggerType.INTAKE_LEAD_CREATED, {"form_id": str(uuid4())}
    )

    with pytest.raises(Exception):
        workflow_service._validate_trigger_config(WorkflowTriggerType.SCHEDULED, {})


def test_workflow_action_config_validation_branches(db, test_org, test_user):
    template = EmailTemplate(
        id=uuid4(),
        organization_id=test_org.id,
        name="WF Template",
        subject="Hi",
        body="<p>Body</p>",
        scope="org",
        is_active=True,
        created_by_user_id=test_user.id,
    )
    db.add(template)
    db.commit()

    workflow_service._validate_action_config(
        db,
        org_id=test_org.id,
        action={"action_type": "send_email", "template_id": template.id, "recipients": "owner"},
        workflow_scope="org",
        owner_user_id=test_user.id,
    )

    with pytest.raises(ValueError, match="Email template"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "send_email", "template_id": uuid4(), "recipients": "owner"},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="User .* not found in organization"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "create_task", "title": "Follow up", "assignee": uuid4()},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="Queue .* not found in organization"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={
                "action_type": "assign_surrogate",
                "owner_type": OwnerType.QUEUE.value,
                "owner_id": uuid4(),
            },
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="Users not found in organization"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "send_notification", "title": "Ping", "recipients": [uuid4()]},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="only supported for org workflows"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "send_zapier_conversion_event"},
            workflow_scope="personal",
            owner_user_id=test_user.id,
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        )

    with pytest.raises(ValueError, match="only supported for status_changed triggers"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "send_zapier_conversion_event"},
            workflow_scope="org",
            owner_user_id=test_user.id,
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
        )

    with pytest.raises(ValueError, match="only supported for org workflows"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "promote_intake_lead"},
            workflow_scope="personal",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="does not support requires_approval"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "promote_intake_lead", "requires_approval": True},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="only supported for org workflows"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "auto_match_submission"},
            workflow_scope="personal",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="only supported for org workflows"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "create_intake_lead"},
            workflow_scope="personal",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="Unknown action type"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "does_not_exist"},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )

    with pytest.raises(ValueError, match="requires_approval must be a boolean"):
        workflow_service._validate_action_config(
            db,
            org_id=test_org.id,
            action={"action_type": "add_note", "content": "x", "requires_approval": "yes"},
            workflow_scope="org",
            owner_user_id=test_user.id,
        )


def test_workflow_engine_core_trigger_matching_and_finders(db, test_org, test_user):
    engine = WorkflowEngineCore(adapter=_DummyAdapter())

    wf_org = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"OrgWorkflow-{uuid4().hex[:6]}",
        scope="org",
        trigger_config={"to_stage_id": str(uuid4())},
    )
    wf_personal = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"PersonalWorkflow-{uuid4().hex[:6]}",
        scope="personal",
        owner_user_id=test_user.id,
        trigger_config={},
    )
    db.commit()

    # trigger() early-return guards
    assert (
        engine.trigger(
            db=db,
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            entity_type="surrogate",
            entity_id=uuid4(),
            event_data={},
            org_id=test_org.id,
            depth=MAX_DEPTH,
        )
        == []
    )

    assert (
        engine.trigger(
            db=db,
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            entity_type="surrogate",
            entity_id=uuid4(),
            event_data={},
            org_id=test_org.id,
            depth=2,
            source=WorkflowEventSource.WORKFLOW,
        )
        == []
    )

    # _trigger_matches branches
    assert (
        engine._trigger_matches(
            wf_org,
            WorkflowTriggerType.STATUS_CHANGED,
            {"new_stage_id": str(uuid4())},
        )
        is False
    )
    wf_org.trigger_config = {"fields": ["status_label"]}
    assert (
        engine._trigger_matches(
            wf_org,
            WorkflowTriggerType.SURROGATE_UPDATED,
            {"changed_fields": ["status_label"]},
        )
        is True
    )
    wf_org.trigger_config = {"form_id": str(uuid4())}
    assert (
        engine._trigger_matches(
            wf_org,
            WorkflowTriggerType.FORM_SUBMITTED,
            {"form_id": str(uuid4())},
        )
        is False
    )
    assert (
        engine._trigger_matches(
            wf_org,
            WorkflowTriggerType.SCHEDULED,
            {},
        )
        is True
    )

    # _find_matching_workflows scope filtering
    wf_personal.trigger_config = {}
    matches = engine._find_matching_workflows(
        db=db,
        org_id=test_org.id,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        event_data={"new_stage_id": wf_org.trigger_config.get("to_stage_id")},
        entity_owner_id=test_user.id,
    )
    assert isinstance(matches, list)

    # execute_workflow wrapper delegates
    engine._execute_workflow = lambda **kwargs: SimpleNamespace(id=uuid4())  # type: ignore[method-assign]
    execution = engine.execute_workflow(
        db=db,
        workflow=wf_org,
        entity_type="surrogate",
        entity_id=uuid4(),
        event_data={},
    )
    assert execution is not None


def test_workflow_engine_core_rate_limit_dedupe_and_conditions(db, test_org, test_user):
    engine = WorkflowEngineCore(adapter=_DummyAdapter())

    wf = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"RateLimit-{uuid4().hex[:6]}",
        trigger_type=WorkflowTriggerType.SCHEDULED,
    )
    wf.rate_limit_per_hour = 1
    wf.rate_limit_per_entity_per_day = 1

    entity_id = uuid4()
    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=test_org.id,
        workflow_id=wf.id,
        event_id=uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="surrogate",
        entity_id=entity_id,
        trigger_event={},
        dedupe_key="dedupe:1",
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.SUCCESS.value,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    db.commit()

    assert engine._is_duplicate(db, "dedupe:1") is True
    assert engine._is_duplicate(db, "missing") is False

    rate_error = engine._check_rate_limits(db, wf, entity_id)
    assert rate_error is not None
    assert "Rate limit exceeded" in rate_error

    assert engine._get_dedupe_key(wf, entity_id) is not None

    dummy = SimpleNamespace(status_label="approved", days=10, text="Hello world", empty=None)
    assert engine._evaluate_conditions([], "AND", dummy) is True
    assert engine._evaluate_condition(WorkflowConditionOperator.EQUALS.value, "x", "x") is True
    assert engine._evaluate_condition(WorkflowConditionOperator.NOT_EQUALS.value, "x", "y") is True
    assert engine._evaluate_condition(WorkflowConditionOperator.CONTAINS.value, "abc", "b") is True
    assert (
        engine._evaluate_condition(WorkflowConditionOperator.NOT_CONTAINS.value, "abc", "z") is True
    )
    assert engine._evaluate_condition(WorkflowConditionOperator.IS_EMPTY.value, "", None) is True
    assert (
        engine._evaluate_condition(WorkflowConditionOperator.IS_NOT_EMPTY.value, "x", None) is True
    )
    assert engine._evaluate_condition(WorkflowConditionOperator.IN.value, "TX", "TX,CA") is True
    assert (
        engine._evaluate_condition(WorkflowConditionOperator.NOT_IN.value, "NY", ["TX", "CA"])
        is True
    )
    assert (
        engine._evaluate_condition(WorkflowConditionOperator.GREATER_THAN.value, "5", "4") is True
    )
    assert engine._evaluate_condition(WorkflowConditionOperator.LESS_THAN.value, "2", "3") is True
    assert engine._evaluate_condition("unknown", "a", "b") is False


def test_workflow_engine_continue_execution_denied_and_expired_paths(db, test_org, test_user):
    adapter = _DummyAdapter()
    engine = WorkflowEngineCore(adapter=adapter)

    wf = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"Resume-{uuid4().hex[:6]}",
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
    )

    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=test_org.id,
        workflow_id=wf.id,
        event_id=uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="surrogate",
        entity_id=uuid4(),
        trigger_event={},
        dedupe_key=None,
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.PAUSED.value,
        paused_at_action_index=0,
        paused_task_id=None,
    )
    db.add(execution)
    db.commit()

    adapter.get_entity = lambda *_args, **_kwargs: SimpleNamespace(id=uuid4())  # type: ignore[method-assign]

    denied_task = SimpleNamespace(
        status=TaskStatus.DENIED.value,
        workflow_action_type="add_note",
        workflow_denial_reason="Not now",
        workflow_triggered_by_user_id=test_user.id,
    )
    engine.continue_execution(db, execution.id, denied_task, "deny")
    db.refresh(execution)
    assert execution.status == WorkflowExecutionStatus.CANCELED.value
    assert "Approval denied" in (execution.error_message or "")

    execution.status = WorkflowExecutionStatus.PAUSED.value
    execution.paused_at_action_index = 0
    execution.actions_executed = []
    db.commit()

    expired_task = SimpleNamespace(
        status=TaskStatus.EXPIRED.value,
        workflow_action_type="add_note",
        workflow_denial_reason=None,
        workflow_triggered_by_user_id=test_user.id,
    )
    engine.continue_execution(db, execution.id, expired_task, "expire")
    db.refresh(execution)
    assert execution.status == WorkflowExecutionStatus.EXPIRED.value


def test_workflow_engine_resolve_approval_context_fallbacks(db, test_org, test_user):
    adapter = _DummyAdapter()
    engine = WorkflowEngineCore(adapter=adapter)

    admin_user = _create_member(db, test_org.id, role=Role.ADMIN.value)

    wf = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"ApprovalCtx-{uuid4().hex[:6]}",
        scope="org",
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
    )
    wf.created_by_user_id = admin_user.id
    wf.updated_by_user_id = None
    wf.owner_user_id = None
    db.commit()

    # No related surrogate + approval required -> fallback approver.
    adapter.get_related_surrogate = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    surrogate, owner, error = engine._resolve_approval_context(
        db=db,
        workflow=wf,
        entity_type="surrogate",
        entity=SimpleNamespace(id=uuid4()),
        has_approval_actions=True,
        triggered_by_user_id=None,
    )
    assert surrogate is None
    assert owner is not None
    assert error is None

    # Surrogate owned by queue with approval requirement -> explicit error.
    adapter.get_related_surrogate = lambda *_args, **_kwargs: SimpleNamespace(
        owner_type=OwnerType.QUEUE.value, owner_id=None
    )  # type: ignore[method-assign]
    _surrogate, _owner, error = engine._resolve_approval_context(
        db=db,
        workflow=wf,
        entity_type="surrogate",
        entity=SimpleNamespace(id=uuid4()),
        has_approval_actions=True,
        triggered_by_user_id=None,
    )
    assert error == "Workflow requires surrogate owner to be a user"


def test_default_adapter_execute_action_guardrails_and_error_path(monkeypatch):
    adapter = DefaultWorkflowDomainAdapter()

    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    fake_db = SimpleNamespace(query=lambda *_args, **_kwargs: _FakeQuery())

    # Surrogate-only action with task missing surrogate link.
    result = adapter.execute_action(
        db=fake_db,
        action={"action_type": "send_email"},
        entity=SimpleNamespace(surrogate_id=None),
        entity_type="task",
        event_id=uuid4(),
        depth=0,
    )
    assert result["success"] is False
    assert result["skipped"] is True

    # Intake-lead only action on wrong entity.
    result = adapter.execute_action(
        db=fake_db,
        action={"action_type": "promote_intake_lead"},
        entity=SimpleNamespace(),
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
    )
    assert result["success"] is False
    assert "intake_lead" in result["error"]

    # Unknown action.
    result = adapter.execute_action(
        db=fake_db,
        action={"action_type": "unknown_action"},
        entity=SimpleNamespace(),
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
    )
    assert result["success"] is False
    assert "Unknown action type" in result["error"]

    alerts: list[dict] = []
    monkeypatch.setattr(
        "app.services.alert_service.record_alert_isolated",
        lambda **kwargs: alerts.append(kwargs),
    )
    monkeypatch.setattr(
        adapter,
        "_action_send_email",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = adapter.execute_action(
        db=fake_db,
        action={"action_type": "send_email"},
        entity=SimpleNamespace(organization_id=uuid4(), id=uuid4()),
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
    )
    assert result["success"] is False
    assert result["action_type"] == "send_email"
    assert alerts


def test_default_adapter_action_helpers(monkeypatch):
    adapter = DefaultWorkflowDomainAdapter()
    org_id = uuid4()

    queued: list[dict] = []
    monkeypatch.setattr(
        "app.services.job_service.schedule_job",
        lambda **kwargs: queued.append(kwargs) or SimpleNamespace(id=uuid4()),
    )
    monkeypatch.setattr(
        adapter,
        "_resolve_email_variables",
        lambda _db, _surrogate: {"full_name": "Case Owner"},
    )

    surrogate = SimpleNamespace(
        id=uuid4(),
        organization_id=org_id,
        email="case@example.com",
        owner_type=OwnerType.USER.value,
        owner_id=None,
        created_by_user_id=None,
    )
    send_result = adapter._action_send_email(
        db=SimpleNamespace(),
        action={"action_type": "send_email", "template_id": uuid4(), "recipients": "surrogate"},
        entity=surrogate,
        event_id=uuid4(),
    )
    assert send_result["success"] is True
    assert send_result["queued_count"] == 1
    assert queued

    no_email = SimpleNamespace(
        id=uuid4(),
        organization_id=org_id,
        email=None,
        owner_type=OwnerType.USER.value,
        owner_id=None,
        created_by_user_id=None,
    )
    send_result = adapter._action_send_email(
        db=SimpleNamespace(),
        action={"action_type": "send_email", "template_id": uuid4(), "recipients": "surrogate"},
        entity=no_email,
        event_id=uuid4(),
    )
    assert send_result["success"] is False

    notifications: list[dict] = []
    monkeypatch.setattr(
        "app.services.notification_facade.create_notification",
        lambda **kwargs: notifications.append(kwargs),
    )
    notify_result = adapter._action_send_notification(
        db=SimpleNamespace(query=lambda *_args, **_kwargs: None),
        action={"action_type": "send_notification", "title": "Reminder", "recipients": "owner"},
        entity=SimpleNamespace(
            id=uuid4(),
            organization_id=org_id,
            owner_type=OwnerType.USER.value,
            owner_id=uuid4(),
            created_by_user_id=None,
        ),
    )
    assert notify_result["success"] is True
    assert notify_result["recipients_count"] == 1
    assert len(notifications) == 1

    bad_field = adapter._action_update_field(
        db=SimpleNamespace(),
        action={"action_type": "update_field", "field": "not_allowed", "value": "x"},
        entity=SimpleNamespace(),
        event_id=uuid4(),
        depth=0,
        trigger_callback=None,
    )
    assert bad_field["success"] is False

    no_author_note = adapter._action_add_note(
        db=SimpleNamespace(),
        action={"action_type": "add_note", "content": "Hello"},
        entity=SimpleNamespace(
            owner_type=OwnerType.QUEUE.value,
            owner_id=None,
            created_by_user_id=None,
        ),
    )
    assert no_author_note["success"] is False


def test_workflow_service_stats_options_and_preferences(db, test_org, test_user):
    wf_org = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"StatsWF-{uuid4().hex[:6]}",
        scope="org",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
    )
    wf_personal = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"PersonalWF-{uuid4().hex[:6]}",
        scope="personal",
        owner_user_id=test_user.id,
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
    )

    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=test_org.id,
        workflow_id=wf_org.id,
        event_id=uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="surrogate",
        entity_id=uuid4(),
        trigger_event={},
        dedupe_key=None,
        matched_conditions=True,
        actions_executed=[{"success": True}],
        status=WorkflowExecutionStatus.SUCCESS.value,
        duration_ms=120,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(execution)

    approval_task = Task(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_id=None,
        intended_parent_id=None,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="Approve workflow",
        description=None,
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        status=TaskStatus.PENDING.value,
        due_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(approval_task)
    db.commit()

    stats = workflow_service.get_workflow_stats(db, test_org.id)
    assert stats.total_workflows >= 2
    assert stats.enabled_workflows >= 2
    assert stats.total_executions_24h >= 1

    exec_stats = workflow_service.get_execution_stats(db, test_org.id)
    assert exec_stats["total_24h"] >= 1

    pref = workflow_service.update_user_preference(db, test_user.id, wf_org.id, True)
    assert isinstance(pref, UserWorkflowPreference)
    assert workflow_service.is_user_opted_out(db, test_user.id, wf_org.id) is True

    items, total = workflow_service.list_executions(db, wf_org.id, limit=10, offset=0)
    assert total >= 1
    assert items

    options = workflow_service.get_workflow_options(
        db,
        test_org.id,
        workflow_scope="personal",
        user_id=test_user.id,
    )
    assert options.trigger_types
    assert options.action_types_by_trigger

    listed = workflow_service.list_workflows(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        has_manage_permission=False,
    )
    assert listed

    wf_read = workflow_service.to_workflow_read(db, wf_org, can_edit=True)
    assert wf_read.id == wf_org.id
    wf_item = workflow_service.to_workflow_list_item(db, wf_personal, can_edit=True)
    assert wf_item.id == wf_personal.id


def test_workflow_service_duplicate_and_list_scope_filters(db, test_org, test_user):
    wf = _create_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Duplicate Me",
        scope="org",
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
    )
    db.commit()

    copy_one = workflow_service.duplicate_workflow(db, wf, test_user.id)
    assert "(Copy)" in copy_one.name
    copy_two = workflow_service.duplicate_workflow(db, wf, test_user.id)
    assert copy_two.name != copy_one.name

    only_org = workflow_service.list_workflows(
        db,
        org_id=test_org.id,
        user_id=None,
        has_manage_permission=False,
        scope_filter="org",
    )
    assert all(item.scope == "org" for item in only_org)

    only_personal = workflow_service.list_workflows(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        has_manage_permission=False,
        scope_filter="personal",
    )
    assert all(item.scope == "personal" for item in only_personal)
