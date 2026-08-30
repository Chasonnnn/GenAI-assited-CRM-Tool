import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core.policies import POLICIES
from app.db.enums import (
    JobType,
    Role,
    TaskStatus,
    WorkflowEventSource,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)
from app.db.models import (
    Attachment,
    AutomationWorkflow,
    EmailTemplate,
    EntityNote,
    Form,
    FormSubmission,
    IntakeLead,
    Job,
    Membership,
    Notification,
    Organization,
    Task,
    User,
    UserPermissionOverride,
    WorkflowExecution,
)
from app.routers.workflows import test_workflow as workflow_test_route
from app.schemas.auth import UserSession
from app.schemas.donor import DonorCreate, DonorUpdate
from app.schemas.task import TaskCreate
from app.schemas.workflow import WorkflowCreate, WorkflowTestRequest
from app.services import (
    donor_service,
    permission_service,
    pipeline_service,
    task_service,
    workflow_service,
    workflow_triggers,
)
from app.services.workflow_engine import engine


def _pipeline_stage(db, org_id, entity_type: str, stage_key: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=entity_type,
    )
    return (
        pipeline_service.get_stage_by_key(db, pipeline.id, stage_key),
        pipeline,
    )


def _notification_action() -> dict[str, object]:
    return {
        "action_type": "send_notification",
        "title": "Donor follow-up",
        "recipients": "owner",
    }


def test_workflow_creation_persists_exact_donor_subject_and_rejects_cross_type_stage(
    db, test_org, test_user
):
    egg_new, _egg_pipeline = _pipeline_stage(db, test_org.id, "egg_donor", "new")
    sperm_new, _sperm_pipeline = _pipeline_stage(db, test_org.id, "sperm_donor", "new")
    assert egg_new is not None
    assert sperm_new is not None

    with pytest.raises(ValueError, match="egg_donor pipeline"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Invalid donor stage {uuid.uuid4()}",
                subject_type="egg_donor",
                trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
                trigger_config={"to_stage_id": str(sperm_new.id)},
                actions=[_notification_action()],
            ),
        )

    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Egg donor stage {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
            trigger_config={"to_stage_id": str(egg_new.id)},
            actions=[_notification_action()],
        ),
    )
    assert workflow.subject_type == "egg_donor"
    assert workflow.trigger_config["to_stage_id"] == str(egg_new.id)


def test_workflow_options_return_only_the_requested_donor_pipeline(db, test_org, test_user):
    egg_new, egg_pipeline = _pipeline_stage(db, test_org.id, "egg_donor", "new")
    _sperm_new, sperm_pipeline = _pipeline_stage(db, test_org.id, "sperm_donor", "new")
    assert egg_new is not None

    options = workflow_service.get_workflow_options(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        subject_type="egg_donor",
        workflow_scope="org",
        allow_messaging=True,
    )

    returned_stage_ids = {item["id"] for item in options.statuses}
    assert str(egg_new.id) in returned_stage_ids
    assert returned_stage_ids
    assert all(
        db.get(type(egg_new), uuid.UUID(stage_id)).pipeline_id == egg_pipeline.id
        for stage_id in returned_stage_ids
    )
    assert not any(
        db.get(type(egg_new), uuid.UUID(stage_id)).pipeline_id == sperm_pipeline.id
        for stage_id in returned_stage_ids
    )
    assert options.trigger_entity_types["donor_stage_changed"] == "egg_donor"
    assert "assign_donor" in options.action_types_by_trigger["donor_stage_changed"]
    assert "send_message" not in {item["value"] for item in options.action_types}
    assert "send_message" not in options.action_types_by_trigger["donor_stage_changed"]
    assert "education" in options.condition_fields
    assert "bmi" not in options.condition_fields


def test_workflow_dry_run_uses_exact_donor_subject_and_rejects_cross_type(db, test_org, test_user):
    egg = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Egg Dry Run",
            email="egg-dry-run@example.com",
        ),
    )
    sperm = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Sperm Dry Run",
            email="sperm-dry-run@example.com",
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Egg dry run {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            conditions=[{"field": "donor_type", "operator": "equals", "value": "egg"}],
            actions=[_notification_action()],
        ),
    )
    session = UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.ADMIN,
        email=test_user.email,
        display_name=test_user.display_name,
    )

    result = workflow_test_route(
        workflow.id,
        WorkflowTestRequest(entity_id=egg.id, entity_type="egg_donor"),
        db,
        session,
    )
    assert result.conditions_matched is True
    assert result.conditions_evaluated[0]["actual"] == "egg"

    with pytest.raises(HTTPException) as exc_info:
        workflow_test_route(
            workflow.id,
            WorkflowTestRequest(entity_id=sperm.id, entity_type="egg_donor"),
            db,
            session,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    ("trigger_type", "expected_subject"),
    [
        (WorkflowTriggerType.FORM_SUBMITTED, "form_submission"),
        (WorkflowTriggerType.MATCH_PROPOSED, "match"),
        (WorkflowTriggerType.APPOINTMENT_SCHEDULED, "appointment"),
    ],
)
def test_legacy_workflow_create_without_subject_infers_trigger_subject_and_matches(
    db, test_org, test_user, trigger_type, expected_subject
):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Legacy inferred subject {uuid.uuid4()}",
            trigger_type=trigger_type,
            actions=[_notification_action()],
        ),
    )
    assert workflow.subject_type == expected_subject
    matched = engine._find_matching_workflows(
        db,
        test_org.id,
        trigger_type,
        {},
        test_user.id,
        expected_subject,
    )
    assert workflow.id in {item.id for item in matched}


def test_donor_execution_matches_exact_subject_and_records_sanitized_subject_context(
    db, test_org, test_user
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Automation Donor",
            email="automation-donor@example.com",
            phone="6075550101",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    for subject_type in ("egg_donor", "sperm_donor"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"{subject_type} update {uuid.uuid4()}",
                subject_type=subject_type,
                trigger_type=WorkflowTriggerType.DONOR_UPDATED,
                trigger_config={"fields": ["education"]},
                actions=[
                    {
                        "action_type": "add_note",
                        "content": f"Automated {subject_type} note",
                    }
                ],
            ),
        )

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DONOR_UPDATED,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
        org_id=test_org.id,
        entity_owner_id=test_user.id,
    )

    assert len(executions) == 1
    execution = executions[0]
    assert execution.subject_type == "egg_donor"
    assert execution.subject_id == donor.id
    assert execution.trigger_event == {"changed_fields": ["education"]}
    assert "automation-donor@example.com" not in str(execution.trigger_event)
    assert "+16075550101" not in str(execution.trigger_event)
    notes = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
            EntityNote.entity_type == "donor",
            EntityNote.entity_id == donor.id,
        )
        .all()
    )
    assert [note.content for note in notes] == ["Automated egg_donor note"]


def test_org_execution_dashboard_includes_donor_subject_identity(db, test_org, test_user):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor dashboard identity {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[_notification_action()],
        ),
    )
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Execution Dashboard Donor",
            email="execution-dashboard-donor@example.com",
        ),
    )

    items, total = workflow_service.list_org_executions(
        db,
        test_org.id,
        workflow_id=workflow.id,
    )

    assert total == 1
    assert items[0]["subject_type"] == "sperm_donor"
    assert items[0]["subject_id"] == donor.id
    assert items[0]["entity_name"] == donor.full_name
    assert items[0]["entity_number"] == donor.donor_number


@pytest.mark.asyncio
async def test_execution_history_enriches_only_exact_tenant_subtype_donors(
    authed_client,
    db,
    test_org,
    test_user,
):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Exact donor execution identity {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[_notification_action()],
        ),
    )
    exact_donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Exact Execution Donor",
            email="exact-execution-donor@example.com",
        ),
    )
    wrong_subtype_donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Wrong Subtype Donor",
            email="wrong-subtype-execution@example.com",
        ),
        emit_workflow_events=False,
    )
    other_org = Organization(
        id=uuid.uuid4(),
        name="Execution Identity Other Org",
        slug=f"execution-identity-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_org_donor = donor_service.create_donor(
        db,
        other_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Other Tenant Donor",
            email="other-tenant-execution@example.com",
        ),
        emit_workflow_events=False,
    )

    unavailable_executions = [
        WorkflowExecution(
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid.uuid4(),
            depth=0,
            event_source=WorkflowEventSource.USER.value,
            entity_type="task",
            entity_id=uuid.uuid4(),
            subject_type="sperm_donor",
            subject_id=subject_id,
            trigger_event={"source": "test"},
            matched_conditions=True,
            actions_executed=[],
            status=WorkflowExecutionStatus.SUCCESS.value,
            duration_ms=1,
        )
        for subject_id in (wrong_subtype_donor.id, other_org_donor.id)
    ]
    db.add_all(unavailable_executions)
    db.commit()

    history_response = await authed_client.get(f"/workflows/{workflow.id}/executions")
    assert history_response.status_code == 200, history_response.text
    history_by_id = {item["id"]: item for item in history_response.json()["items"]}

    exact_execution = next(
        item
        for item in history_by_id.values()
        if item["subject_id"] == str(exact_donor.id)
    )
    assert exact_execution["entity_name"] == exact_donor.full_name
    assert exact_execution["entity_number"] == exact_donor.donor_number
    for execution in unavailable_executions:
        assert history_by_id[str(execution.id)]["entity_name"] is None
        assert history_by_id[str(execution.id)]["entity_number"] is None

    org_response = await authed_client.get(
        "/workflows/executions",
        params={"workflow_id": str(workflow.id)},
    )
    assert org_response.status_code == 200, org_response.text
    org_history_by_id = {item["id"]: item for item in org_response.json()["items"]}
    assert org_history_by_id[str(exact_execution["id"])]["entity_name"] == exact_donor.full_name
    for execution in unavailable_executions:
        assert org_history_by_id[str(execution.id)]["entity_name"] is None
        assert org_history_by_id[str(execution.id)]["entity_number"] is None


def test_donor_service_emits_created_workflow_without_pii(db, test_org, test_user):
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor created {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[{"action_type": "add_note", "content": "Created by automation"}],
        ),
    )

    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Created Trigger Donor",
            email="created-trigger@example.com",
            phone="6075550199",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )

    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.subject_type == "egg_donor",
            WorkflowExecution.subject_id == donor.id,
        )
        .one()
    )
    assert execution.trigger_event["donor_number"] == donor.donor_number
    assert "created-trigger@example.com" not in str(execution.trigger_event)
    assert "+16075550199" not in str(execution.trigger_event)
    assert db.query(EntityNote).filter(EntityNote.entity_id == donor.id).count() == 1


def test_donor_service_emits_updated_assigned_and_stage_changed_events(db, test_org, test_user):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Lifecycle Donor",
            email="lifecycle-donor@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    target_stage, _pipeline = _pipeline_stage(db, test_org.id, "egg_donor", "closed")
    assert target_stage is not None
    updated_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor education updated {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[{"action_type": "add_note", "content": "Education updated"}],
        ),
    )
    assigned_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor assignment changed {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_ASSIGNED,
            actions=[{"action_type": "add_note", "content": "Assignment changed"}],
        ),
    )
    stage_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor stage changed {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
            trigger_config={"to_stage_id": str(target_stage.id)},
            actions=[{"action_type": "add_note", "content": "Stage changed"}],
        ),
    )

    donor = donor_service.update_donor(db, donor, test_user.id, DonorUpdate(education="College"))
    donor = donor_service.update_donor(
        db,
        donor,
        test_user.id,
        DonorUpdate(owner_type=None, owner_id=None),
    )
    donor_service.change_status(
        db,
        donor,
        target_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
    )

    executed_workflow_ids = {
        execution.workflow_id
        for execution in db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.subject_id == donor.id,
        )
        .all()
    }
    assert {
        updated_workflow.id,
        assigned_workflow.id,
        stage_workflow.id,
    } <= executed_workflow_ids


def test_donor_actions_create_linked_task_assign_update_note_and_notify(db, test_org, test_user):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Action Donor",
            email="action-donor@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor actions {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[
                {
                    "action_type": "create_task",
                    "title": "Review donor",
                    "assignee": "owner",
                },
                {
                    "action_type": "assign_donor",
                    "owner_type": "user",
                    "owner_id": str(test_user.id),
                },
                {
                    "action_type": "update_field",
                    "field": "education",
                    "value": "Graduate degree",
                },
                {"action_type": "add_note", "content": "Reviewed donor"},
                {
                    "action_type": "send_notification",
                    "title": "Donor reviewed",
                    "recipients": "owner",
                },
            ],
        ),
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="sperm_donor",
        subject_id=donor.id,
        event_data={"donor_id": str(donor.id)},
    )

    assert execution is not None
    assert execution.status == "success"
    assert all(item["success"] for item in execution.actions_executed)
    assert db.query(Task).filter(Task.donor_id == donor.id).one().title == "Review donor"
    db.refresh(donor)
    assert donor.education == "Graduate degree"
    assert db.query(EntityNote).filter(EntityNote.entity_id == donor.id).count() == 1
    assert (
        db.query(Notification)
        .filter(Notification.entity_type == "donor", Notification.entity_id == donor.id)
        .count()
        == 1
    )


def test_unassigned_donor_note_and_task_use_workflow_creator_as_actor(db, test_org, test_user):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Unassigned Donor",
            email="unassigned-donor@example.com",
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Unassigned donor actions {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[
                {"action_type": "add_note", "content": "Unassigned donor note"},
                {"action_type": "create_task", "title": "Review unassigned donor"},
            ],
        ),
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
    )

    assert execution is not None
    assert execution.status == "success"
    note = db.query(EntityNote).filter(EntityNote.entity_id == donor.id).one()
    assert note.author_id == test_user.id
    task = db.query(Task).filter(Task.donor_id == donor.id).one()
    assert task.created_by_user_id == test_user.id


def test_scheduled_and_inactivity_sweeps_enumerate_only_exact_donor_subject(
    db, test_org, test_user
):
    egg = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Scheduled Egg",
            email="scheduled-egg@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    sperm = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Scheduled Sperm",
            email="scheduled-sperm@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Scheduled egg {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.SCHEDULED,
            trigger_config={"cron": "0 9 * * *", "timezone": "UTC"},
            actions=[{"action_type": "add_note", "content": "Scheduled donor note"}],
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Inactive egg {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.INACTIVITY,
            trigger_config={"days": 7},
            actions=[{"action_type": "add_note", "content": "Inactive donor note"}],
        ),
    )
    egg.updated_at = datetime.now(UTC) - timedelta(days=8)
    sperm.updated_at = datetime.now(UTC) - timedelta(days=8)
    db.commit()

    workflow_triggers.trigger_scheduled_workflows(
        db,
        test_org.id,
        evaluated_at=datetime(2026, 8, 29, 9, 0, tzinfo=UTC),
    )
    workflow_triggers.trigger_inactivity_workflows(db, test_org.id)

    egg_notes = {
        note.content
        for note in db.query(EntityNote)
        .filter(EntityNote.entity_type == "donor", EntityNote.entity_id == egg.id)
        .all()
    }
    assert egg_notes == {"Scheduled donor note", "Inactive donor note"}
    assert (
        db.query(EntityNote)
        .filter(EntityNote.entity_type == "donor", EntityNote.entity_id == sperm.id)
        .count()
        == 0
    )


def test_task_and_note_triggers_recover_exact_donor_subject_without_pii(db, test_org, test_user):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Derived Subject Donor",
            email="derived-subject@example.com",
            education="Masters",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor task due {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.TASK_DUE,
            trigger_config={"hours_before": 24},
            conditions=[{"field": "education", "operator": "equals", "value": "Masters"}],
            actions=[{"action_type": "add_note", "content": "Task-linked donor note"}],
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor note added {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.NOTE_ADDED,
            actions=[{"action_type": "add_note", "content": "Note-linked donor note"}],
        ),
    )
    task = task_service.create_task(
        db,
        test_org.id,
        test_user.id,
        TaskCreate(
            title="Private donor follow-up",
            donor_id=donor.id,
            owner_type="user",
            owner_id=test_user.id,
        ),
    )

    workflow_triggers.trigger_task_due(db, task)
    source_note = EntityNote(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        content="Private source note",
        author_id=test_user.id,
    )
    db.add(source_note)
    db.commit()
    workflow_triggers.trigger_note_added(db, source_note)

    executions = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.subject_type == "egg_donor",
            WorkflowExecution.subject_id == donor.id,
        )
        .all()
    )
    assert len(executions) == 2
    task_execution = next(item for item in executions if item.entity_type == "task")
    assert task_execution.trigger_event["task_title"] is None
    assert "Private donor follow-up" not in str(task_execution.trigger_event)
    note_contents = {
        note.content
        for note in db.query(EntityNote)
        .filter(EntityNote.entity_type == "donor", EntityNote.entity_id == donor.id)
        .all()
    }
    assert {"Task-linked donor note", "Note-linked donor note"} <= note_contents


def test_document_trigger_recovers_donor_from_attachment_owner_without_filename_pii(
    db, test_org, test_user
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Document Donor",
            email="document-donor@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor document uploaded {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DOCUMENT_UPLOADED,
            actions=[{"action_type": "add_note", "content": "Document received"}],
        ),
    )
    attachment = Attachment(
        organization_id=test_org.id,
        donor_id=donor.id,
        uploaded_by_user_id=test_user.id,
        filename="private-donor-name.jpg",
        storage_key=f"donors/{donor.id}/profile.jpg",
        content_type="image/jpeg",
        file_size=128,
        checksum_sha256="0" * 64,
        scan_status="clean",
    )
    db.add(attachment)
    db.commit()

    workflow_triggers.trigger_document_uploaded(db, attachment)

    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.entity_type == "document",
            WorkflowExecution.entity_id == attachment.id,
        )
        .one()
    )
    assert execution.subject_type == "sperm_donor"
    assert execution.subject_id == donor.id
    assert execution.trigger_event["filename"] is None
    assert "private-donor-name.jpg" not in str(execution.trigger_event)


def test_donor_approval_task_links_donor_and_reviewed_communications_fail_closed(
    db, test_org, test_user
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Approval Donor",
            email="approval-donor@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    with pytest.raises(ValueError, match="review approval"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Unreviewed donor communication {uuid.uuid4()}",
                subject_type="sperm_donor",
                trigger_type=WorkflowTriggerType.DONOR_UPDATED,
                trigger_config={"fields": ["education"]},
                actions=[
                    {
                        "action_type": "send_email",
                        "template_id": str(uuid.uuid4()),
                        "recipients": "donor",
                    }
                ],
            ),
        )

    with pytest.raises(ValueError, match="does not support donor workflows"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Unsupported donor message {uuid.uuid4()}",
                subject_type="sperm_donor",
                trigger_type=WorkflowTriggerType.DONOR_UPDATED,
                trigger_config={"fields": ["education"]},
                actions=[
                    {
                        "action_type": "send_message",
                        "purpose": "operational",
                        "message_template_version_id": str(uuid.uuid4()),
                        "requires_approval": True,
                    }
                ],
            ),
        )

    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Reviewed donor update {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[
                {
                    "action_type": "update_field",
                    "field": "education",
                    "value": "Reviewed degree",
                    "requires_approval": True,
                }
            ],
        ),
    )
    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="sperm_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
    )

    assert execution is not None
    assert execution.status == "paused"
    task = db.query(Task).filter(Task.workflow_execution_id == execution.id).one()
    assert task.donor_id == donor.id
    assert task.surrogate_id is None
    assert donor.donor_number in task.workflow_action_preview
    assert donor.full_name not in task.title
    assert donor.email not in task.title


def test_legacy_donor_intake_workflow_message_action_fails_closed_at_execution(
    db,
    test_org,
    test_user,
):
    lead = IntakeLead(
        organization_id=test_org.id,
        source="shared_intake",
        lead_type="egg_donor",
        full_name="Legacy donor messaging lead",
        email="legacy-donor-message@example.com",
        status="pending_review",
        created_by_user_id=test_user.id,
    )
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Legacy donor intake messaging {uuid.uuid4()}",
        subject_type="intake_lead",
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED.value,
        trigger_config={},
        conditions=[],
        actions=[
            {
                "action_type": "send_message",
                "purpose": "operational",
                "message_template_version_id": str(uuid.uuid4()),
            }
        ],
        is_enabled=True,
        created_by_user_id=test_user.id,
        updated_by_user_id=test_user.id,
    )
    db.add_all([lead, workflow])
    db.flush()

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": "egg_donor"},
    )

    assert execution is not None
    assert execution.status == WorkflowExecutionStatus.PARTIAL.value
    assert execution.actions_executed == [
        {
            "success": False,
            "error": "Action 'send_message' does not support donor subjects",
            "skipped": True,
            "action_type": "send_message",
        }
    ]


@pytest.mark.asyncio
async def test_donor_execution_retry_preserves_subject_and_cross_org_retry_is_hidden(
    authed_client, db, test_org, test_user
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Retry Donor",
            email="retry-donor@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Retry donor workflow {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[{"action_type": "add_note", "content": "Retried donor workflow"}],
        ),
    )
    failed = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        trigger_event={"changed_fields": ["education"]},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic failure",
        duration_ms=0,
    )
    db.add(failed)

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Donor Org",
        slug=f"other-donor-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_workflow = AutomationWorkflow(
        organization_id=other_org.id,
        name=f"Other donor workflow {uuid.uuid4()}",
        subject_type="egg_donor",
        trigger_type=WorkflowTriggerType.DONOR_UPDATED.value,
        trigger_config={"fields": ["education"]},
        conditions=[],
        actions=[],
        is_enabled=True,
    )
    db.add(other_workflow)
    db.flush()
    other_execution = WorkflowExecution(
        organization_id=other_org.id,
        workflow_id=other_workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="donor",
        entity_id=uuid.uuid4(),
        subject_type="egg_donor",
        subject_id=uuid.uuid4(),
        trigger_event={"changed_fields": ["education"]},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic failure",
        duration_ms=0,
    )
    db.add(other_execution)
    db.commit()

    retry_response = await authed_client.post(f"/workflows/executions/{failed.id}/retry")
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["subject_type"] == "egg_donor"
    assert retried["subject_id"] == str(donor.id)
    assert retried["status"] == "success"

    cross_org_response = await authed_client.post(
        f"/workflows/executions/{other_execution.id}/retry"
    )
    assert cross_org_response.status_code == 404


@pytest.mark.asyncio
async def test_donor_workflow_surfaces_fail_closed_without_donor_view_permission(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Private donor workflow {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            conditions=[{"field": "education", "operator": "equals", "value": "College"}],
            actions=[_notification_action()],
        ),
    )
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Private Workflow Donor",
            email="private-workflow-donor@example.com",
            education="College",
        ),
    )
    failed = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        trigger_event={"changed_fields": ["education"]},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic failure",
        duration_ms=0,
    )
    db.add(failed)
    db.commit()

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    explicit_list = await authed_client.get(
        "/workflows",
        params={"subject_type": "egg_donor"},
    )
    assert explicit_list.status_code == 403

    mixed_list = await authed_client.get("/workflows")
    assert mixed_list.status_code == 200, mixed_list.text
    assert str(workflow.id) not in {item["id"] for item in mixed_list.json()}

    options = await authed_client.get(
        "/workflows/options",
        params={"subject_type": "egg_donor"},
    )
    assert options.status_code == 403

    detail = await authed_client.get(f"/workflows/{workflow.id}")
    assert detail.status_code == 403

    dry_run = await authed_client.post(
        f"/workflows/{workflow.id}/test",
        json={"entity_id": str(donor.id), "entity_type": "egg_donor"},
    )
    assert dry_run.status_code == 403

    history = await authed_client.get(f"/workflows/{workflow.id}/executions")
    assert history.status_code == 403

    org_history = await authed_client.get("/workflows/executions")
    assert org_history.status_code == 200, org_history.text
    assert str(failed.id) not in {item["id"] for item in org_history.json()["items"]}

    scoped_org_history = await authed_client.get(
        "/workflows/executions",
        params={"workflow_id": str(workflow.id)},
    )
    assert scoped_org_history.status_code == 403

    workflow_stats = await authed_client.get("/workflows/stats")
    assert workflow_stats.status_code == 200, workflow_stats.text
    assert "donor_updated" not in workflow_stats.json()["by_trigger_type"]

    execution_stats = await authed_client.get("/workflows/executions/stats")
    assert execution_stats.status_code == 200, execution_stats.text
    assert execution_stats.json()["total_24h"] == 0

    retry = await authed_client.post(f"/workflows/executions/{failed.id}/retry")
    assert retry.status_code == 403


@pytest.mark.asyncio
async def test_generic_donor_intake_workflow_surfaces_and_orphaned_execution_fail_closed(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Private donor workflow form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        lead_kind="egg_donor",
        source_mode="shared",
        match_status="unmatched",
        status="pending_review",
        answers_json={"full_name": "Private Donor Submission"},
    )
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        source="shared_intake",
        lead_type="egg_donor",
        full_name="Private Donor Intake Lead",
        email="private-donor-intake@example.com",
        status="pending_review",
    )
    db.add_all([submission, lead])
    db.flush()
    submission_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Generic donor submission test {uuid.uuid4()}",
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
            conditions=[{"field": "status", "operator": "equals", "value": "pending_review"}],
            actions=[_notification_action()],
        ),
    )
    lead_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Generic donor lead test {uuid.uuid4()}",
            trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
            conditions=[
                {
                    "field": "full_name",
                    "operator": "equals",
                    "value": "Private Donor Intake Lead",
                }
            ],
            actions=[_notification_action()],
        ),
    )
    failed_submission_execution = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=submission_workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="form_submission",
        entity_id=submission.id,
        subject_type="form_submission",
        subject_id=submission.id,
        trigger_event={"submission_id": str(submission.id)},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic donor submission failure",
        duration_ms=0,
    )
    missing_form_workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Legacy missing-form intake workflow {uuid.uuid4()}",
        subject_type="form_submission",
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED.value,
        trigger_config={"form_id": str(uuid.uuid4())},
        conditions=[],
        actions=[_notification_action()],
        is_enabled=True,
        created_by_user_id=test_user.id,
        updated_by_user_id=test_user.id,
    )
    db.add_all([failed_submission_execution, missing_form_workflow])
    db.commit()

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    submission_response = await authed_client.post(
        f"/workflows/{submission_workflow.id}/test",
        json={"entity_id": str(submission.id), "entity_type": "form_submission"},
    )
    lead_response = await authed_client.post(
        f"/workflows/{lead_workflow.id}/test",
        json={"entity_id": str(lead.id), "entity_type": "intake_lead"},
    )

    assert submission_response.status_code == 403
    assert lead_response.status_code == 403

    listed = await authed_client.get("/workflows")
    assert listed.status_code == 200, listed.text
    listed_ids = {item["id"] for item in listed.json()}
    assert str(submission_workflow.id) not in listed_ids
    assert str(lead_workflow.id) not in listed_ids
    assert str(missing_form_workflow.id) not in listed_ids

    history = await authed_client.get(f"/workflows/{submission_workflow.id}/executions")
    assert history.status_code == 403

    stats = await authed_client.get("/workflows/stats")
    assert stats.status_code == 200, stats.text
    assert stats.json()["total_workflows"] == 0

    retry = await authed_client.post(
        f"/workflows/executions/{failed_submission_execution.id}/retry"
    )
    assert retry.status_code == 403

    db.delete(submission)
    db.commit()
    org_history = await authed_client.get("/workflows/executions")
    assert org_history.status_code == 200, org_history.text
    assert str(failed_submission_execution.id) not in {
        item["id"] for item in org_history.json()["items"]
    }


@pytest.mark.asyncio
async def test_donor_form_bound_workflow_crud_and_options_fail_closed(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    egg_form = Form(
        organization_id=test_org.id,
        name="Private egg donor workflow form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    surrogate_form = Form(
        organization_id=test_org.id,
        name="Visible surrogate workflow form",
        status="published",
        purpose="other",
        lead_kind="surrogate",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    sperm_form = Form(
        organization_id=test_org.id,
        name="Other sperm donor workflow form",
        status="published",
        purpose="other",
        lead_kind="sperm_donor",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    db.add_all([egg_form, surrogate_form, sperm_form])
    db.flush()

    egg_options = workflow_service.get_workflow_options(
        db,
        test_org.id,
        user_id=test_user.id,
        subject_type="egg_donor",
    )
    assert {item["id"] for item in egg_options.forms} == {str(egg_form.id)}

    donor_bound = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor form bound workflow {uuid.uuid4()}",
            subject_type="surrogate",
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
            trigger_config={"form_id": str(egg_form.id)},
            actions=[_notification_action()],
        ),
    )
    surrogate_bound = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Surrogate form bound workflow {uuid.uuid4()}",
            subject_type="surrogate",
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
            trigger_config={"form_id": str(surrogate_form.id)},
            actions=[_notification_action()],
        ),
    )
    assert donor_bound.trigger_config["lead_kind"] == "egg_donor"
    assert surrogate_bound.trigger_config["lead_kind"] == "surrogate"

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    listed = await authed_client.get("/workflows")
    assert listed.status_code == 200, listed.text
    listed_ids = {item["id"] for item in listed.json()}
    assert str(donor_bound.id) not in listed_ids
    assert str(surrogate_bound.id) in listed_ids

    options = await authed_client.get(
        "/workflows/options",
        params={"subject_type": "surrogate"},
    )
    assert options.status_code == 200, options.text
    option_form_ids = {item["id"] for item in options.json()["forms"]}
    assert str(egg_form.id) not in option_form_ids
    assert str(sperm_form.id) not in option_form_ids
    assert str(surrogate_form.id) in option_form_ids

    detail = await authed_client.get(f"/workflows/{donor_bound.id}")
    assert detail.status_code == 403

    created = await authed_client.post(
        "/workflows",
        json={
            "name": "Forbidden donor form workflow",
            "scope": "personal",
            "subject_type": "surrogate",
            "trigger_type": "form_submitted",
            "trigger_config": {"form_id": str(egg_form.id)},
            "actions": [_notification_action()],
        },
    )
    assert created.status_code == 403

    updated = await authed_client.patch(
        f"/workflows/{surrogate_bound.id}",
        json={"trigger_config": {"form_id": str(egg_form.id)}},
    )
    assert updated.status_code == 403

    toggled = await authed_client.post(f"/workflows/{donor_bound.id}/toggle")
    duplicated = await authed_client.post(f"/workflows/{donor_bound.id}/duplicate")
    deleted = await authed_client.delete(f"/workflows/{donor_bound.id}")
    assert toggled.status_code == 403
    assert duplicated.status_code == 403
    assert deleted.status_code == 403

    stats = await authed_client.get("/workflows/stats")
    assert stats.status_code == 200, stats.text
    assert stats.json()["total_workflows"] == 1


@pytest.mark.parametrize(
    ("trigger_type", "subject_type", "context_key"),
    [
        (WorkflowTriggerType.FORM_SUBMITTED, "form_submission", "lead_kind"),
        (WorkflowTriggerType.INTAKE_LEAD_CREATED, "intake_lead", "lead_type"),
    ],
)
def test_donor_form_workflow_persists_exact_subtype_and_rejects_mismatch(
    db,
    test_org,
    test_user,
    trigger_type,
    subject_type,
    context_key,
):
    form = Form(
        organization_id=test_org.id,
        name=f"Exact subtype {trigger_type.value} form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()

    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Exact subtype workflow {uuid.uuid4()}",
            subject_type=subject_type,
            trigger_type=trigger_type,
            trigger_config={"form_id": str(form.id)},
            actions=[_notification_action()],
        ),
    )
    assert workflow.trigger_config[context_key] == "egg_donor"

    with pytest.raises(ValueError, match=f"{context_key} must match"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Mismatched subtype workflow {uuid.uuid4()}",
                subject_type=subject_type,
                trigger_type=trigger_type,
                trigger_config={
                    "form_id": str(form.id),
                    context_key: "sperm_donor",
                },
                actions=[_notification_action()],
            ),
        )

    with pytest.raises(ValueError, match="does not support donor workflows"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Donor intake message workflow {uuid.uuid4()}",
                subject_type=subject_type,
                trigger_type=trigger_type,
                trigger_config={"form_id": str(form.id)},
                actions=[
                    {
                        "action_type": "send_message",
                        "purpose": "operational",
                        "message_template_version_id": str(uuid.uuid4()),
                    }
                ],
            ),
        )


def test_form_submission_workflows_match_exact_donor_lead_kind(
    db,
    test_org,
    test_user,
):
    form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Egg donor subtype workflow form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=test_user.id,
    )
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form=form,
        lead_kind="egg_donor",
        source_mode="shared",
        match_status="unmatched",
        status="pending_review",
        answers_json={},
    )
    db.add_all([form, submission])
    db.flush()

    workflows = {}
    for lead_kind in ("egg_donor", "sperm_donor"):
        workflows[lead_kind] = workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"{lead_kind} form submission {uuid.uuid4()}",
                subject_type="form_submission",
                trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
                trigger_config={"lead_kind": lead_kind},
                actions=[
                    {
                        "action_type": "send_notification",
                        "title": "Subtype matched",
                        "recipients": "creator",
                    }
                ],
            ),
        )

    workflow_triggers.trigger_form_submitted(
        db=db,
        org_id=test_org.id,
        form_id=form.id,
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
    )

    executions = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.entity_id == submission.id)
        .all()
    )
    assert {execution.workflow_id for execution in executions} == {
        workflows["egg_donor"].id
    }
    assert executions[0].subject_type == "form_submission"
    assert executions[0].trigger_event["lead_kind"] == "egg_donor"


def test_intake_lead_workflows_match_exact_donor_lead_type(db, test_org, test_user):
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        source="shared_intake",
        lead_type="sperm_donor",
        full_name="Subtype Intake Lead",
        email="subtype-intake@example.com",
        status="pending_review",
        created_by_user_id=test_user.id,
    )
    db.add(lead)
    db.flush()

    workflows = {}
    for lead_type in ("egg_donor", "sperm_donor"):
        workflows[lead_type] = workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"{lead_type} intake lead {uuid.uuid4()}",
                subject_type="intake_lead",
                trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
                trigger_config={"lead_type": lead_type},
                actions=[
                    {
                        "action_type": "send_notification",
                        "title": "Subtype matched",
                        "recipients": "creator",
                    }
                ],
            ),
        )

    workflow_triggers.trigger_intake_lead_created(
        db,
        lead,
        form_id=None,
        submission_id=None,
    )

    executions = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.entity_id == lead.id)
        .all()
    )
    assert {execution.workflow_id for execution in executions} == {
        workflows["sperm_donor"].id
    }
    assert executions[0].subject_type == "intake_lead"
    assert executions[0].trigger_event["lead_type"] == "sperm_donor"


@pytest.mark.asyncio
async def test_donor_workflow_access_does_not_require_surrogate_view_permission(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Donor-only Workflow User",
            email="donor-only-workflow@example.com",
            education="College",
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor-only permission workflow {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            conditions=[{"field": "education", "operator": "equals", "value": "College"}],
            actions=[_notification_action()],
        ),
    )

    original_check = permission_service.check_permission

    def deny_surrogate_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["surrogates"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_surrogate_view)

    detail = await authed_client.get(f"/workflows/{workflow.id}")
    assert detail.status_code == 200, detail.text

    dry_run = await authed_client.post(
        f"/workflows/{workflow.id}/test",
        json={"entity_id": str(donor.id), "entity_type": "sperm_donor"},
    )
    assert dry_run.status_code == 200, dry_run.text


@pytest.mark.asyncio
async def test_view_only_donor_user_cannot_configure_or_execute_donor_workflows(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="View-only Workflow Donor",
            email="view-only-workflow@example.com",
            education="College",
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"View-only donor workflow {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            conditions=[{"field": "education", "operator": "equals", "value": "College"}],
            actions=[_notification_action()],
        ),
    )
    failed = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source=WorkflowEventSource.USER.value,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        trigger_event={"changed_fields": ["education"]},
        matched_conditions=True,
        actions_executed=[],
        status=WorkflowExecutionStatus.FAILED.value,
        error_message="Synthetic view-only retry",
        duration_ms=0,
    )
    db.add(failed)
    db.commit()

    original_check = permission_service.check_permission

    def deny_donor_edit(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].actions["edit"].value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_edit)

    detail = await authed_client.get(f"/workflows/{workflow.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["can_edit"] is False

    dry_run = await authed_client.post(
        f"/workflows/{workflow.id}/test",
        json={"entity_id": str(donor.id), "entity_type": "egg_donor"},
    )
    assert dry_run.status_code == 200, dry_run.text

    created = await authed_client.post(
        "/workflows",
        json={
            "name": "Forbidden donor workflow",
            "scope": "personal",
            "subject_type": "egg_donor",
            "trigger_type": "donor_updated",
            "trigger_config": {"fields": ["education"]},
            "actions": [_notification_action()],
        },
    )
    assert created.status_code == 403

    updated = await authed_client.patch(
        f"/workflows/{workflow.id}",
        json={"name": "Forbidden update"},
    )
    assert updated.status_code == 403

    toggled = await authed_client.post(f"/workflows/{workflow.id}/toggle")
    assert toggled.status_code == 403

    duplicated = await authed_client.post(f"/workflows/{workflow.id}/duplicate")
    assert duplicated.status_code == 403

    retried = await authed_client.post(f"/workflows/executions/{failed.id}/retry")
    assert retried.status_code == 403


@pytest.mark.parametrize("recipient_mode", ["explicit", "all_admins"])
def test_donor_workflow_notification_skips_recipients_without_donor_access(
    db,
    test_org,
    test_user,
    monkeypatch,
    recipient_mode,
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Private Workflow Notification Donor",
            email=f"workflow-notification-{recipient_mode}@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )
    recipients = [str(test_user.id)] if recipient_mode == "explicit" else "all_admins"
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Private donor notification {recipient_mode} {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Private donor update",
                    "recipients": recipients,
                }
            ],
        ),
    )

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
    )

    assert execution is not None
    assert execution.status == WorkflowExecutionStatus.SUCCESS.value
    assert execution.actions_executed[0]["recipients_count"] == 0
    assert (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_org.id,
            Notification.user_id == test_user.id,
            Notification.entity_type == "donor",
            Notification.entity_id == donor.id,
        )
        .count()
        == 0
    )


def _mock_org_workflow_email_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_service,
        "validate_email_provider",
        lambda *_args, **_kwargs: (True, None),
    )
    monkeypatch.setattr(
        "app.services.workflow_email_provider.resolve_workflow_email_provider",
        lambda **_kwargs: (
            "resend",
            {
                "from_email": "workflows@example.com",
                "from_name": "Workflow Team",
            },
        ),
    )


def _create_donor_email_workflow(
    db,
    *,
    organization_id,
    creator_user_id,
    template_id,
    recipients,
):
    return workflow_service.create_workflow(
        db,
        organization_id,
        creator_user_id,
        WorkflowCreate(
            name=f"Reviewed donor email {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[
                {
                    "action_type": "send_email",
                    "template_id": str(template_id),
                    "recipients": recipients,
                    "requires_approval": True,
                }
            ],
        ),
    )


@pytest.mark.parametrize("recipient_mode", ["owner", "creator", "explicit", "all_admins"])
@pytest.mark.parametrize(
    "access_state",
    ["authorized", "permission_revoked", "membership_inactive", "user_inactive"],
)
def test_approved_donor_workflow_email_rechecks_internal_recipient_access(
    db,
    test_org,
    test_user,
    monkeypatch,
    recipient_mode,
    access_state,
):
    test_membership = (
        db.query(Membership)
        .filter(
            Membership.organization_id == test_org.id,
            Membership.user_id == test_user.id,
        )
        .one()
    )
    test_membership.role = Role.CASE_MANAGER.value
    recipient = User(
        id=uuid.uuid4(),
        email=f"donor-workflow-{recipient_mode}-{access_state}-{uuid.uuid4()}@example.com",
        display_name="Internal Donor Recipient",
        is_active=True,
    )
    recipient_membership = Membership(
        id=uuid.uuid4(),
        user_id=recipient.id,
        organization_id=test_org.id,
        role=Role.ADMIN.value,
        is_active=True,
    )
    db.add_all([recipient, recipient_membership])
    db.flush()

    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Private Approved Email Donor",
            email=f"private-approved-{uuid.uuid4()}@example.com",
            owner_type="user",
            owner_id=recipient.id if recipient_mode == "owner" else test_user.id,
        ),
        emit_workflow_events=False,
    )
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"Donor access check {uuid.uuid4()}",
        subject="Private donor follow-up",
        body="<p>Private donor workflow content</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()

    _mock_org_workflow_email_provider(monkeypatch)
    recipients = [str(recipient.id)] if recipient_mode == "explicit" else recipient_mode
    workflow = _create_donor_email_workflow(
        db,
        organization_id=test_org.id,
        creator_user_id=recipient.id if recipient_mode == "creator" else test_user.id,
        template_id=template.id,
        recipients=recipients,
    )
    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
    )
    assert execution is not None
    assert execution.status == WorkflowExecutionStatus.PAUSED.value
    approval_task = db.query(Task).filter(Task.id == execution.paused_task_id).one()

    if access_state == "permission_revoked":
        db.add(
            UserPermissionOverride(
                organization_id=test_org.id,
                user_id=recipient.id,
                permission=POLICIES["donors"].default.value,
                override_type="revoke",
            )
        )
    elif access_state == "membership_inactive":
        recipient_membership.is_active = False
    elif access_state == "user_inactive":
        recipient.is_active = False
    approval_task.status = TaskStatus.COMPLETED.value
    db.commit()

    engine.continue_execution(db, execution.id, approval_task, "approve")
    db.refresh(execution)
    queued_jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .all()
    )

    if access_state == "authorized":
        assert execution.status == WorkflowExecutionStatus.SUCCESS.value
        assert len(queued_jobs) == 1
        assert queued_jobs[0].payload["recipient_email"] == recipient.email
    else:
        assert execution.status == WorkflowExecutionStatus.PARTIAL.value
        assert queued_jobs == []
        result_text = str(execution.actions_executed[0])
        assert "No recipient emails resolved" in result_text
        assert donor.full_name not in result_text
        assert donor.email not in result_text
        assert recipient.email not in result_text
        assert str(recipient.id) not in result_text


@pytest.mark.parametrize("recipient_mode", ["donor", "subject"])
def test_approved_donor_workflow_email_keeps_external_subject_delivery(
    db,
    test_org,
    test_user,
    monkeypatch,
    recipient_mode,
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="External Approved Email Donor",
            email=f"external-approved-{uuid.uuid4()}@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
        emit_workflow_events=False,
    )
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"External donor email {uuid.uuid4()}",
        subject="Reviewed donor follow-up",
        body="<p>Reviewed donor workflow content</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()

    _mock_org_workflow_email_provider(monkeypatch)
    workflow = _create_donor_email_workflow(
        db,
        organization_id=test_org.id,
        creator_user_id=test_user.id,
        template_id=template.id,
        recipients=recipient_mode,
    )
    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
    )
    assert execution is not None
    assert execution.status == WorkflowExecutionStatus.PAUSED.value
    approval_task = db.query(Task).filter(Task.id == execution.paused_task_id).one()

    membership = (
        db.query(Membership)
        .filter(
            Membership.organization_id == test_org.id,
            Membership.user_id == test_user.id,
        )
        .one()
    )
    membership.is_active = False
    test_user.is_active = False
    approval_task.status = TaskStatus.COMPLETED.value
    db.commit()

    engine.continue_execution(db, execution.id, approval_task, "approve")
    db.refresh(execution)
    queued_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .one()
    )
    assert execution.status == WorkflowExecutionStatus.SUCCESS.value
    assert queued_job.payload["recipient_email"] == donor.email
