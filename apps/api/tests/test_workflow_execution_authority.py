"""Workflow permission v2 covers execution, management and publication boundaries."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.db.enums import Role, WorkflowEventSource
from app.db.models import (
    AutomationWorkflow,
    EmailTemplate,
    Membership,
    Organization,
    RolePermission,
    Surrogate,
    User,
    WorkflowExecution,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.db.models.record_access import RecordCollaborator, RoleRecordScope
from app.services import workflow_access, workflow_service
from app.services import workflow_execution_authority as authority
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter
from app.services.workflow_engine_core import WorkflowEngineCore


@pytest.fixture
def setup(db, test_org, test_user, default_stage):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        full_name="Permission Test",
        email="workflow-permissions@example.com",
        email_hash=hash_email("workflow-permissions@example.com"),
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
    )
    db.add(surrogate)
    db.flush()
    return test_org, test_user, surrogate


def workflow(db, org, user, *, scope="personal", actions=None):
    item = AutomationWorkflow(
        id=uuid4(),
        organization_id=org.id,
        name=f"Workflow {uuid4()}",
        subject_type="surrogate",
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=actions or [{"action_type": "add_note", "content": "Follow up"}],
        scope=scope,
        owner_user_id=user.id if scope == "personal" else None,
        is_enabled=True,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(item)
    db.flush()
    return item


def member(db, org, role=Role.INTAKE_SPECIALIST):
    user = User(
        id=uuid4(), email=f"member-{uuid4()}@example.com", display_name="Staff", is_active=True
    )
    db.add(user)
    db.flush()
    membership = Membership(
        id=uuid4(), organization_id=org.id, user_id=user.id, role=role.value, is_active=True
    )
    db.add(membership)
    db.add(
        RoleRecordScope(
            organization_id=org.id,
            role=role.value,
            module="surrogates",
            assignment="all",
            phase="all",
        )
    )
    db.flush()
    return user, membership


class RecordingAdapter(DefaultWorkflowDomainAdapter):
    def __init__(self):
        self.calls = []

    def execute_action(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True}


def execute(db, item, record, adapter=None):
    adapter = adapter or RecordingAdapter()
    result = WorkflowEngineCore(adapter).execute_workflow(
        db, item, "surrogate", record.id, {}, source=WorkflowEventSource.USER
    )
    return result, adapter


def test_personal_execution_rechecks_owner_membership(setup, db):
    org, owner, record = setup
    item = workflow(db, org, owner)
    db.query(Membership).filter_by(organization_id=org.id, user_id=owner.id).one().is_active = False
    db.flush()
    result, adapter = execute(db, item, record)
    assert adapter.calls == []
    assert result.actions_executed[0]["skipped"]
    assert "no longer has action permission" in result.actions_executed[0]["error"]


def test_personal_execution_accepts_collaborator_then_stops_after_removal(setup, db):
    org, admin, record = setup
    owner, membership = member(db, org)
    item = workflow(db, org, owner)
    link = RecordCollaborator(
        organization_id=org.id,
        membership_id=membership.id,
        user_id=owner.id,
        surrogate_id=record.id,
        granted_by_user_id=admin.id,
    )
    db.add(link)
    db.flush()
    result, adapter = execute(db, item, record)
    assert result.status == "success"
    assert len(adapter.calls) == 1
    db.delete(link)
    db.flush()
    denied, adapter = execute(db, item, record)
    assert adapter.calls == []
    assert denied.actions_executed[0]["error"] == "Record is outside personal workflow scope"


def test_personal_visible_unassigned_records_are_not_an_audience(setup, db):
    org, admin, record = setup
    owner, _ = member(db, org)
    item = workflow(db, org, owner)
    assert not authority.personal_subject_allowed(db, item, "surrogate", record.id)
    result, adapter = execute(db, item, record)
    assert adapter.calls == []
    assert result.actions_executed[0]["skipped"]


def test_personal_action_revocation_does_not_block_other_allowed_actions(setup, db):
    org, _, record = setup
    owner, _ = member(db, org)
    record.owner_id = owner.id
    item = workflow(
        db,
        org,
        owner,
        actions=[
            {"action_type": "add_note", "content": "Follow up"},
            {"action_type": "create_task", "title": "Follow up"},
        ],
    )
    db.add(
        RolePermission(
            organization_id=org.id,
            role=Role.INTAKE_SPECIALIST.value,
            permission="edit_surrogate_notes",
            is_granted=False,
        )
    )
    db.flush()
    result, adapter = execute(db, item, record)
    assert result.status == "partial"
    assert result.actions_executed[0]["skipped"]
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["action"]["action_type"] == "create_task"


def test_org_execution_survives_proposer_departure(setup, db):
    org, proposer, record = setup
    item = workflow(db, org, proposer, scope="org")
    authority.authorize_configuration(db, item, proposer.id)
    db.query(Membership).filter_by(
        organization_id=org.id, user_id=proposer.id
    ).one().is_active = False
    db.flush()
    result, adapter = execute(db, item, record)
    assert result.status == "success"
    assert len(adapter.calls) == 1
    assert result.authority_snapshot["authorized_by_user_id"] == str(proposer.id)


def test_changed_org_reach_requires_new_authorization(setup, db):
    org, actor, record = setup
    item = workflow(db, org, actor, scope="org")
    authority.authorize_configuration(db, item, actor.id)
    item.conditions = [{"field": "state", "operator": "equals", "value": "CA"}]
    result, adapter = execute(db, item, record)
    assert result.status == "skipped"
    assert adapter.calls == []
    assert "configuration authorization" in result.error_message


@pytest.mark.parametrize("binding", ["organization_id", "workflow_id"])
def test_org_authority_grant_cannot_cross_organizations(setup, db, binding):
    org, actor, record = setup
    item = workflow(db, org, actor, scope="org")
    authority.authorize_configuration(db, item, actor.id)
    snapshot = authority.execution_snapshot(db, item)
    snapshot[binding] = str(uuid4())
    with pytest.raises(authority.WorkflowAuthorityError, match="execution authority is invalid"):
        authority.authorize_action(
            db,
            item,
            item.actions[0],
            subject_type="surrogate",
            subject_id=record.id,
            snapshot=snapshot,
        )


def test_staff_cannot_edit_peers_personal_workflow(setup, db):
    org, owner, _ = setup
    peer, _ = member(db, org)
    item = workflow(db, org, owner)
    peer_session = authority.active_session(db, org.id, peer.id)
    assert not workflow_access.can_view(db, peer_session, item)
    assert not workflow_access.can_edit(db, peer_session, item)
    assert workflow_access.can_edit(db, authority.active_session(db, org.id, owner.id), item)


def test_org_publish_copies_private_template_and_credits_original_owner(setup, db):
    org, actor, _ = setup
    template = EmailTemplate(
        id=uuid4(),
        organization_id=org.id,
        name="Personal template",
        subject="Hello",
        body="<p>Hello</p>",
        scope="personal",
        owner_user_id=actor.id,
        created_by_user_id=actor.id,
        is_active=True,
    )
    db.add(template)
    db.flush()
    item = workflow(
        db,
        org,
        actor,
        actions=[
            {
                "action_type": "send_email",
                "template_id": str(template.id),
                "requires_approval": True,
            }
        ],
    )
    published = workflow_service.publish_workflow(db, item, actor.id)
    copied = db.get(EmailTemplate, published.actions[0]["template_id"])
    assert published.id != item.id
    assert published.scope == "org" and published.owner_user_id is None
    assert not published.is_enabled and published.execution_authority is None
    assert (
        published.proposed_by_user_id == actor.id
        and published.proposed_by_name == actor.display_name
    )
    assert copied.id != template.id and copied.scope == "org" and copied.owner_user_id is None
    template.subject = "Private update"
    item.actions[0]["template_id"] = str(uuid4())
    assert copied.subject == "Hello"
    assert published.actions[0]["template_id"] == str(copied.id)


def test_publish_rolls_back_copied_templates_when_dependency_is_invalid(setup, db):
    org, actor, _ = setup
    template = EmailTemplate(
        id=uuid4(),
        organization_id=org.id,
        name="Private valid",
        subject="Hello",
        body="<p>Hello</p>",
        scope="personal",
        owner_user_id=actor.id,
        created_by_user_id=actor.id,
        is_active=True,
    )
    db.add(template)
    db.flush()
    item = workflow(
        db,
        org,
        actor,
        actions=[
            {"action_type": "send_email", "template_id": str(template.id)},
            {"action_type": "send_email", "template_id": str(uuid4())},
        ],
    )
    before = db.query(EmailTemplate).filter_by(organization_id=org.id).count()
    with pytest.raises(ValueError, match="unavailable"):
        workflow_service.publish_workflow(db, item, actor.id)
    assert db.query(EmailTemplate).filter_by(organization_id=org.id).count() == before
    assert db.query(AutomationWorkflow).filter_by(organization_id=org.id).count() == 1


def test_queued_personal_email_rechecks_owner_and_org_binding(setup, db):
    org, owner, record = setup
    item = workflow(db, org, owner)
    execution = WorkflowExecution(
        organization_id=org.id,
        workflow_id=item.id,
        event_id=uuid4(),
        event_source="user",
        entity_type="surrogate",
        entity_id=record.id,
        subject_type="surrogate",
        subject_id=record.id,
        trigger_event={},
        status="success",
        authority_snapshot=authority.execution_snapshot(db, item),
    )
    db.add(execution)
    db.flush()
    job = SimpleNamespace(
        organization_id=org.id,
        payload={
            "workflow_execution_id": str(execution.id),
            "workflow_scope": "personal",
            "workflow_owner_id": str(owner.id),
            "subject_type": "surrogate",
            "subject_id": str(record.id),
        },
    )
    authority.authorize_email_job(db, job)
    db.query(Membership).filter_by(organization_id=org.id, user_id=owner.id).one().is_active = False
    db.flush()
    with pytest.raises(authority.WorkflowAuthorityError, match="no longer"):
        authority.authorize_email_job(db, job)
    other = Organization(id=uuid4(), name="Other", slug=f"other-{uuid4()}")
    db.add(other)
    db.add(OrganizationPermissionPolicy(organization_id=other.id, version=2))
    db.flush()
    job.organization_id = other.id
    with pytest.raises(authority.WorkflowAuthorityError, match="unavailable"):
        authority.authorize_email_job(db, job)


def test_collaborator_personal_workflow_is_selected_for_live_events(setup, db):
    org, admin, record = setup
    owner, membership = member(db, org)
    item = workflow(db, org, owner)
    db.add(
        RecordCollaborator(
            organization_id=org.id,
            membership_id=membership.id,
            user_id=owner.id,
            surrogate_id=record.id,
            granted_by_user_id=admin.id,
        )
    )
    db.flush()
    adapter = RecordingAdapter()
    from app.db.enums import WorkflowTriggerType

    results = WorkflowEngineCore(adapter).trigger(
        db,
        WorkflowTriggerType.SURROGATE_CREATED,
        "surrogate",
        record.id,
        {},
        org.id,
        entity_owner_id=admin.id,
        subject_type="surrogate",
        subject_id=record.id,
    )
    assert [result.workflow_id for result in results] == [item.id]
    assert len(adapter.calls) == 1


def test_collaborator_personal_workflow_runs_in_scheduled_sweep(setup, db, monkeypatch):
    from datetime import UTC, datetime

    from app.services import workflow_triggers

    org, admin, record = setup
    owner, membership = member(db, org)
    item = workflow(db, org, owner)
    item.trigger_type = "scheduled"
    item.trigger_config = {"cron": "0 9 * * *", "timezone": "UTC"}
    db.add(
        RecordCollaborator(
            organization_id=org.id,
            membership_id=membership.id,
            user_id=owner.id,
            surrogate_id=record.id,
            granted_by_user_id=admin.id,
        )
    )
    db.flush()
    adapter = RecordingAdapter()
    monkeypatch.setattr(workflow_triggers, "engine", WorkflowEngineCore(adapter))
    workflow_triggers.trigger_scheduled_workflows(
        db, org.id, evaluated_at=datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
    )
    assert len(adapter.calls) == 1


def test_cross_org_task_cannot_resume_paused_execution(setup, db):
    org, owner, record = setup
    item = workflow(db, org, owner)
    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=org.id,
        workflow_id=item.id,
        event_id=uuid4(),
        event_source="user",
        entity_type="surrogate",
        entity_id=record.id,
        subject_type="surrogate",
        subject_id=record.id,
        trigger_event={},
        status="paused",
        paused_at_action_index=0,
        authority_snapshot=authority.execution_snapshot(db, item),
    )
    db.add(execution)
    db.flush()
    foreign_task = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        workflow_execution_id=execution.id,
        status="completed",
        workflow_action_payload=item.actions[0],
    )
    adapter = RecordingAdapter()
    WorkflowEngineCore(adapter).continue_execution(db, execution.id, foreign_task, "approve")
    assert adapter.calls == []
    assert execution.status == "paused"


def test_revoke_while_paused_blocks_approved_snapshot(setup, db):
    from app.db.models import Task

    org, owner, record = setup
    item = workflow(db, org, owner)
    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=org.id,
        workflow_id=item.id,
        event_id=uuid4(),
        event_source="user",
        entity_type="surrogate",
        entity_id=record.id,
        subject_type="surrogate",
        subject_id=record.id,
        trigger_event={},
        status="paused",
        paused_at_action_index=0,
        authority_snapshot=authority.execution_snapshot(db, item),
    )
    db.add(execution)
    db.flush()
    task = Task(
        id=uuid4(),
        organization_id=org.id,
        title="Approve note",
        task_type="workflow_approval",
        status="completed",
        owner_type="user",
        owner_id=owner.id,
        surrogate_id=record.id,
        created_by_user_id=owner.id,
        workflow_execution_id=execution.id,
        workflow_action_type="add_note",
        workflow_action_payload=item.actions[0],
        workflow_action_index=0,
    )
    db.add(task)
    db.flush()
    execution.paused_task_id = task.id
    db.query(Membership).filter_by(organization_id=org.id, user_id=owner.id).one().is_active = False
    db.flush()
    adapter = RecordingAdapter()
    WorkflowEngineCore(adapter).continue_execution(db, execution.id, task, "approve")
    assert adapter.calls == []
    assert execution.status == "partial"
    assert execution.actions_executed[0]["skipped"]


def test_activation_inventory_requires_explicit_pause_without_changing_history(setup, db):
    org, owner, record = setup
    item = workflow(db, org, owner, scope="org")
    completed = WorkflowExecution(
        organization_id=org.id,
        workflow_id=item.id,
        event_id=uuid4(),
        event_source="user",
        entity_type="surrogate",
        entity_id=record.id,
        subject_type="surrogate",
        subject_id=record.id,
        trigger_event={},
        status="success",
    )
    db.add(completed)
    db.flush()
    snapshot = authority.get_policy_execution_snapshot(db, org.id)
    assert snapshot[0]["id"] == str(item.id)
    assert snapshot[0]["unreviewed_execution_ids"] == []
    with pytest.raises(authority.WorkflowAuthorityError, match="explicitly paused"):
        authority.apply_policy_execution_resolutions(db, org.id, owner.id, [])
    authority.apply_policy_execution_resolutions(
        db, org.id, owner.id, [{"item_type": "workflow", "id": str(item.id), "action": "pause"}]
    )
    assert item.is_enabled is False
    assert completed.status == "success"


@pytest.mark.asyncio
async def test_personal_revocation_after_email_outbox_materialization_prevents_dispatch(
    setup, db, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from app.db.models import Job, ResendSettings
    from app.services import email_delivery_dispatch, resend_settings_service
    from app.services.email_delivery_service import (
        DeliveryRoute,
        EmailSource,
        RenderedEmail,
        claim_due_deliveries,
        queue_rendered_email,
    )

    org, owner, record = setup
    item = workflow(db, org, owner)
    execution = WorkflowExecution(
        id=uuid4(),
        organization_id=org.id,
        workflow_id=item.id,
        event_id=uuid4(),
        event_source="user",
        entity_type="surrogate",
        entity_id=record.id,
        subject_type="surrogate",
        subject_id=record.id,
        trigger_event={},
        status="success",
        authority_snapshot=authority.execution_snapshot(db, item),
    )
    db.add(execution)
    db.flush()
    job = Job(
        organization_id=org.id,
        job_type="workflow_email",
        status="completed",
        payload={
            "workflow_execution_id": str(execution.id),
            "workflow_scope": "personal",
            "workflow_owner_id": str(owner.id),
            "subject_type": "surrogate",
            "subject_id": str(record.id),
            "recipient_email": record.email,
        },
    )
    db.add(job)
    db.add(
        ResendSettings(
            organization_id=org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{org.id}",
        idempotency_key=f"workflow-email/{job.id}",
        rendered_email=RenderedEmail(
            recipient_email=record.email,
            subject="Hello",
            html="<p>Hello</p>",
            text="Hello",
            from_email="care@example.com",
        ),
        source=EmailSource(
            source_type="workflow_job",
            source_id=job.id,
            actor_user_id=owner.id,
            surrogate_id=record.id,
        ),
        schedule_at=datetime.now(UTC) - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db, worker_id="workflow-authority-test", limit=1, lease_for=timedelta(minutes=2)
    )[0]
    db.query(Membership).filter_by(organization_id=org.id, user_id=owner.id).one().is_active = False
    db.flush()
    calls = []

    async def no_send(**kwargs):
        calls.append(kwargs)
        raise AssertionError("Provider must not be called")

    monkeypatch.setattr(email_delivery_dispatch.resend_transport, "send_email", no_send)
    result = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    assert calls == []
    assert result.status == "cancelled"
    assert result.last_error_type == "workflow_authority_revoked"
    assert queued.email_log.status == "skipped"
