"""Human-approved AI actions use current applicant authority and handoff rules."""

from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import (
    AIActionApproval,
    AIConversation,
    AIMessage,
    EntityNote,
    Membership,
    OrganizationPermissionPolicy,
    PipelineStage,
    RecordCollaborator,
    RoleRecordScope,
    Surrogate,
    SurrogateStatusHistory,
    User,
    UserPermissionOverride,
)
from app.services import ai_action_executor, pipeline_service


@pytest.fixture
def ai_context(db, test_org):
    actor = User(
        id=uuid4(), email=f"{uuid4()}@test.invalid", display_name="Synthetic Intake", is_active=True
    )
    db.add(actor)
    db.flush()
    membership = Membership(
        organization_id=test_org.id, user_id=actor.id, role="intake_specialist", is_active=True
    )
    db.add_all(
        [
            membership,
            OrganizationPermissionPolicy(organization_id=test_org.id, version=2),
            UserPermissionOverride(
                organization_id=test_org.id,
                user_id=actor.id,
                permission="approve_ai_actions",
                override_type="grant",
            ),
        ]
    )
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    stages = {
        stage.stage_key: stage
        for stage in db.query(PipelineStage).filter_by(pipeline_id=pipeline.id)
    }
    intake = min(
        (stage for stage in stages.values() if stage.stage_type == "intake"),
        key=lambda stage: stage.order,
    )
    record = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number="S10001",
        full_name="Synthetic Applicant",
        email=f"{uuid4()}@test.invalid",
        email_hash=uuid4().hex,
        stage_id=intake.id,
        status_label=intake.label,
        owner_type="user",
        owner_id=actor.id,
    )
    db.add(record)
    db.flush()
    return test_org, actor, membership, record, stages


def proposal(db, org, actor, record, *, action="update_status", payload=None):
    conversation = AIConversation(
        organization_id=org.id, user_id=actor.id, entity_type="surrogate", entity_id=record.id
    )
    db.add(conversation)
    db.flush()
    message = AIMessage(
        conversation_id=conversation.id, role="assistant", content="Synthetic proposed action"
    )
    db.add(message)
    db.flush()
    approval = AIActionApproval(
        message_id=message.id, action_index=0, action_type=action, action_payload=payload or {}
    )
    db.add(approval)
    db.flush()
    return approval


def execute(db, context, approval):
    org, actor, _, record, _ = context
    return ai_action_executor.execute_action(
        db,
        approval,
        actor.id,
        org.id,
        record.id,
        user_permissions={
            "approve_ai_actions",
            "approve_surrogates",
            "change_surrogate_status",
            "edit_surrogate_notes",
        },
    )


def test_ai_stage_change_cannot_borrow_approval_from_caller_permissions(db, ai_context):
    org, actor, member, record, stages = ai_context
    member.role = Role.CASE_MANAGER.value
    db.add(
        RoleRecordScope(
            organization_id=org.id,
            role=member.role,
            module="surrogates",
            assignment="all",
            phase="all",
        )
    )
    approval = proposal(db, org, actor, record, payload={"stage_id": str(stages["approved"].id)})
    old_stage_id = record.stage_id
    result = execute(db, ai_context, approval)
    assert result["success"] is False
    assert result["error_code"] == "permission_denied"
    assert record.stage_id == old_stage_id
    assert db.query(SurrogateStatusHistory).filter_by(surrogate_id=record.id).count() == 0


def test_ai_approval_retains_intake_and_moves_to_pool_once(db, ai_context, monkeypatch):
    org, actor, _, record, stages = ai_context
    monkeypatch.setattr(
        "app.services.workflow_triggers.trigger_status_changed", lambda *args, **kwargs: None
    )
    approval = proposal(db, org, actor, record, payload={"stage_id": str(stages["approved"].id)})
    result = execute(db, ai_context, approval)
    assert result["success"] is True
    assert record.stage_id == stages["approved"].id
    assert record.owner_type == "queue"
    assert (
        db.query(RecordCollaborator).filter_by(surrogate_id=record.id, user_id=actor.id).count()
        == 1
    )
    assert db.query(SurrogateStatusHistory).filter_by(surrogate_id=record.id).count() == 1
    assert execute(db, ai_context, approval)["success"] is False
    assert db.query(SurrogateStatusHistory).filter_by(surrogate_id=record.id).count() == 1


def test_ai_execution_rechecks_scope_after_human_proposal(db, ai_context):
    org, actor, _, record, stages = ai_context
    approval = proposal(
        db, org, actor, record, action="add_note", payload={"content": "Synthetic note"}
    )
    record.owner_id = uuid4()
    record.stage_id = stages["approved"].id
    db.flush()
    result = execute(db, ai_context, approval)
    assert result["success"] is False
    assert result["error_code"] == "permission_denied"
    assert db.query(EntityNote).filter_by(entity_id=record.id).count() == 0


def test_ai_execution_rechecks_membership_after_proposal(db, ai_context):
    org, actor, member, record, _ = ai_context
    approval = proposal(
        db, org, actor, record, action="add_note", payload={"content": "Synthetic note"}
    )
    member.is_active = False
    db.flush()
    assert execute(db, ai_context, approval)["success"] is False
    assert db.query(EntityNote).filter_by(entity_id=record.id).count() == 0


def test_ai_approval_binding_rejects_cross_org_without_mutating_proposal(db, ai_context):
    from app.db.models import Organization

    other_org = Organization(id=uuid4(), name="Other tenant", slug=f"other-{uuid4()}")
    db.add(other_org)
    db.flush()
    org, actor, _, record, stages = ai_context
    approval = proposal(
        db, other_org, actor, record, payload={"stage_id": str(stages["approved"].id)}
    )
    result = execute(db, ai_context, approval)
    assert result["success"] is False
    assert result["error_code"] == "permission_denied"
    assert approval.status == "pending"
    assert record.stage_id != stages["approved"].id


def test_ai_regression_does_not_commit_a_partial_request(db, ai_context):
    org, actor, member, record, stages = ai_context
    from app.db.models import StatusChangeRequest

    member.role = Role.CASE_MANAGER.value
    original = record.stage_id
    record.stage_id = stages["approved"].id
    record.status_label = stages["approved"].label
    approval = proposal(
        db, org, actor, record, payload={"stage_id": str(original), "reason": "Synthetic review"}
    )
    result = execute(db, ai_context, approval)
    assert result["success"] is False
    assert record.stage_id == stages["approved"].id
    assert db.query(SurrogateStatusHistory).filter_by(surrogate_id=record.id).count() == 0
    assert db.query(StatusChangeRequest).filter_by(entity_id=record.id).count() == 0


def test_ai_approval_service_keeps_domain_status_activity_single(db, ai_context, monkeypatch):
    from app.db.models import SurrogateActivityLog
    from app.schemas.auth import UserSession
    from app.services.ai_action_approval_service import approve_action_for_session

    org, actor, _, record, stages = ai_context
    monkeypatch.setattr(
        "app.services.workflow_triggers.trigger_status_changed", lambda *args, **kwargs: None
    )
    approval = proposal(db, org, actor, record, payload={"stage_id": str(stages["approved"].id)})
    result = approve_action_for_session(
        db,
        approval_id=approval.id,
        session=UserSession(
            org_id=org.id, user_id=actor.id, role=Role.INTAKE_SPECIALIST, email="", display_name=""
        ),
    )
    assert result["success"] is True
    assert approval.status == "executed"
    assert (
        db.query(SurrogateActivityLog)
        .filter_by(surrogate_id=record.id, activity_type="status_changed")
        .count()
        == 1
    )


@pytest.mark.parametrize("version", [1, 2])
def test_approval_event_preserves_v2_case_manager_owner_and_v1_pool_behavior(
    db, ai_context, monkeypatch, version
):
    from datetime import UTC, datetime

    from app.services import surrogate_events

    org, actor, member, record, stages = ai_context
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=org.id).one().version = version
    member.role = Role.CASE_MANAGER.value
    old_stage_id = record.stage_id
    record.stage_id = stages["approved"].id
    record.status_label = stages["approved"].label
    db.flush()
    monkeypatch.setattr(
        "app.services.notification_facade.notify_surrogate_status_changed", lambda **kwargs: None
    )
    ready_notifications = []
    monkeypatch.setattr(
        "app.services.notification_facade.notify_surrogate_ready_for_claim",
        lambda **kwargs: ready_notifications.append(kwargs["surrogate"].id),
    )
    monkeypatch.setattr(surrogate_events, "_maybe_send_capi_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        surrogate_events, "_dispatch_conversion_events", lambda *args, **kwargs: None
    )
    surrogate_events.handle_status_changed(
        db=db,
        surrogate=record,
        new_stage=stages["approved"],
        old_stage_id=old_stage_id,
        old_label="New",
        old_slug="new_unread",
        user_id=actor.id,
        effective_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
        is_undo=False,
        request_id=None,
        approved_by_user_id=None,
        approved_at=None,
        requested_at=None,
        trigger_workflows=False,
    )
    if version == 2:
        assert record.owner_type == "user" and record.owner_id == actor.id
        assert ready_notifications == []
    else:
        assert record.owner_type == "queue"
        assert ready_notifications == [record.id]
