"""Intake workflows validate stage references against the record they act on.

Form submission and intake lead workflows run Update Field on the linked surrogate or
donor, so stage references resolve in the pipeline of the trigger form's lead kind.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.encryption import hash_email
from app.db.enums import WorkflowTriggerType
from app.db.models import (
    AutomationWorkflow,
    Form,
    FormFieldMapping,
    FormSubmission,
    IntakeLead,
    Organization,
    Surrogate,
    WorkflowTemplate,
)
from app.schemas.donor import DonorCreate
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services import (
    donor_service,
    pipeline_service,
    template_service,
    workflow_service,
    workflow_triggers,
)
from app.services.workflow_engine import engine

INTAKE_TRIGGERS = [
    (WorkflowTriggerType.FORM_SUBMITTED, "form_submission"),
    (WorkflowTriggerType.INTAKE_LEAD_CREATED, "intake_lead"),
]


def _stage(db, org_id, entity_type: str, stage_key: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, entity_type=entity_type)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    assert stage is not None
    return stage


def _form(db, org_id, user_id, lead_kind: str) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"Intake {lead_kind} {uuid.uuid4().hex[:6]}",
        status="published",
        purpose="other",
        lead_kind=lead_kind,
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _update_stage(stage) -> dict[str, object]:
    return {"action_type": "update_field", "field": "stage_id", "value": str(stage.id)}


def _stage_condition(*stages) -> dict[str, object]:
    return {"field": "stage_id", "operator": "in", "value": [str(stage.id) for stage in stages]}


def _intake_workflow(
    db,
    org_id,
    user_id,
    *,
    trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
    subject_type="form_submission",
    form=None,
    actions,
    conditions=None,
):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"Intake stage {uuid.uuid4()}",
            subject_type=subject_type,
            trigger_type=trigger_type,
            trigger_config={"form_id": str(form.id)} if form else {},
            conditions=conditions or [],
            actions=actions,
        ),
    )


def _surrogate(db, org_id, user_id, stage) -> Surrogate:
    email = f"intake-stage-{uuid.uuid4().hex[:8]}@example.com"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Intake Stage Surrogate",
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _donor(db, org_id, user_id, donor_type: str):
    return donor_service.create_donor(
        db,
        org_id,
        user_id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Intake Stage Donor",
            email=f"intake-donor-{uuid.uuid4().hex[:8]}@example.com",
        ),
        emit_workflow_events=False,
    )


def _submission(db, org_id, form, *, surrogate_id=None, donor_id=None) -> FormSubmission:
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=org_id,
        form=form,
        lead_kind=form.lead_kind,
        source_mode="shared",
        match_status="linked",
        status="pending_review",
        answers_json={},
        surrogate_id=surrogate_id,
        donor_id=donor_id,
    )
    db.add(submission)
    db.flush()
    return submission


@pytest.mark.parametrize(("trigger_type", "subject_type"), INTAKE_TRIGGERS)
def test_surrogate_form_stage_update_resolves_in_the_surrogate_pipeline(
    db, test_org, test_user, trigger_type, subject_type
):
    form = _form(db, test_org.id, test_user.id, "surrogate")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    qualified = _stage(db, test_org.id, "surrogate", "pre_qualified")

    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=trigger_type,
        subject_type=subject_type,
        form=form,
        conditions=[_stage_condition(contacted, qualified)],
        actions=[_update_stage(contacted)],
    )

    assert workflow.subject_type == subject_type
    assert workflow.actions[0]["value"] == str(contacted.id)
    assert workflow.actions[0]["value_stage_key"] == "contacted"
    assert workflow.conditions[0]["value"] == [str(contacted.id), str(qualified.id)]
    assert workflow.conditions[0]["stage_keys"] == ["contacted", "pre_qualified"]


@pytest.mark.parametrize(("trigger_type", "subject_type"), INTAKE_TRIGGERS)
def test_intake_workflow_without_form_keeps_surrogate_stage_references(
    db, test_org, test_user, trigger_type, subject_type
):
    contacted = _stage(db, test_org.id, "surrogate", "contacted")

    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=trigger_type,
        subject_type=subject_type,
        conditions=[_stage_condition(contacted)],
        actions=[_update_stage(contacted)],
    )

    assert workflow.actions[0]["value_stage_key"] == "contacted"
    assert workflow.conditions[0]["stage_keys"] == ["contacted"]


@pytest.mark.parametrize(("trigger_type", "subject_type"), INTAKE_TRIGGERS)
@pytest.mark.parametrize("lead_kind", ["egg_donor", "sperm_donor"])
def test_donor_form_stage_references_resolve_in_the_donor_subtype_pipeline(
    db, test_org, test_user, trigger_type, subject_type, lead_kind
):
    form = _form(db, test_org.id, test_user.id, lead_kind)
    donor_stage = _stage(db, test_org.id, lead_kind, "contacted")
    surrogate_stage = _stage(db, test_org.id, "surrogate", "contacted")

    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=trigger_type,
        subject_type=subject_type,
        form=form,
        conditions=[_stage_condition(donor_stage)],
        actions=[_update_stage(donor_stage)],
    )

    assert workflow.actions[0]["value"] == str(donor_stage.id)
    assert workflow.conditions[0]["value"] == [str(donor_stage.id)]
    with pytest.raises(ValueError, match=f"not found in {lead_kind} pipeline"):
        _intake_workflow(
            db,
            test_org.id,
            test_user.id,
            trigger_type=trigger_type,
            subject_type=subject_type,
            form=form,
            actions=[_update_stage(surrogate_stage)],
        )


def test_donor_form_update_fields_follow_the_donor_rules(db, test_org, test_user):
    form = _form(db, test_org.id, test_user.id, "egg_donor")

    def create(action):
        return _intake_workflow(db, test_org.id, test_user.id, form=form, actions=[action])

    with pytest.raises(ValueError, match="Field 'is_priority' is not allowed for egg_donor"):
        create({"action_type": "update_field", "field": "is_priority", "value": True})
    with pytest.raises(ValueError, match="Invalid donor source"):
        create({"action_type": "update_field", "field": "source", "value": "Facebook"})
    workflow = create({"action_type": "update_field", "field": "source", "value": "Agency"})
    assert workflow.actions[0]["value"] == "agency"


def test_surrogate_form_rejects_donor_only_update_fields(db, test_org, test_user):
    form = _form(db, test_org.id, test_user.id, "surrogate")

    with pytest.raises(ValueError, match="Field 'education' is not allowed for surrogate"):
        _intake_workflow(
            db,
            test_org.id,
            test_user.id,
            form=form,
            actions=[{"action_type": "update_field", "field": "education", "value": "College"}],
        )


def test_shared_donor_form_rejects_stage_references(db, test_org, test_user):
    form = _form(db, test_org.id, test_user.id, "egg_donor")
    db.add(
        FormFieldMapping(
            form_id=form.id,
            field_key="donor_type",
            surrogate_field="donor_type",
        )
    )
    db.flush()
    egg_stage = _stage(db, test_org.id, "egg_donor", "contacted")

    with pytest.raises(ValueError, match="one donor type"):
        _intake_workflow(
            db, test_org.id, test_user.id, form=form, actions=[_update_stage(egg_stage)]
        )
    with pytest.raises(ValueError, match="one donor type"):
        _intake_workflow(
            db,
            test_org.id,
            test_user.id,
            form=form,
            conditions=[_stage_condition(egg_stage)],
            actions=[{"action_type": "add_note", "content": "Shared donor form"}],
        )
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        actions=[{"action_type": "update_field", "field": "education", "value": "College"}],
    )
    assert workflow.actions[0]["value"] == "College"


def test_stage_reference_from_another_org_is_rejected(db, test_org, test_user):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Intake Org", slug=f"other-intake-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    foreign_stage = _stage(db, other_org.id, "surrogate", "contacted")
    form = _form(db, test_org.id, test_user.id, "surrogate")

    with pytest.raises(ValueError, match="not found in surrogate pipeline"):
        _intake_workflow(
            db, test_org.id, test_user.id, form=form, actions=[_update_stage(foreign_stage)]
        )
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_stage_condition(foreign_stage)],
        actions=[{"action_type": "add_note", "content": "Foreign stage"}],
    )
    assert workflow.conditions[0]["value"] == []


def test_migrated_form_submission_workflow_saves_a_stage_update_from_the_builder(
    db, test_org, test_user
):
    form = _form(db, test_org.id, test_user.id, "surrogate")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Repaired application workflow",
        scope="org",
        subject_type="form_submission",
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED.value,
        trigger_config={"form_id": str(form.id)},
        conditions=[],
        condition_logic="AND",
        actions=[_update_stage(contacted)],
        is_enabled=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.flush()

    updated = workflow_service.update_workflow(
        db,
        workflow,
        test_user.id,
        WorkflowUpdate(
            trigger_config={"form_id": str(form.id)},
            conditions=[_stage_condition(contacted)],
            actions=[_update_stage(contacted)],
            is_enabled=True,
        ),
    )

    assert updated.is_enabled is True
    assert updated.actions[0]["value_stage_key"] == "contacted"
    assert updated.conditions[0]["stage_keys"] == ["contacted"]


@pytest.mark.parametrize(
    ("lead_kind", "stage_entity"), [("surrogate", "surrogate"), ("sperm_donor", "sperm_donor")]
)
def test_template_with_stage_update_creates_an_application_workflow(
    db, test_org, test_user, lead_kind, stage_entity
):
    form = _form(db, test_org.id, test_user.id, lead_kind)
    template = WorkflowTemplate(
        id=uuid.uuid4(),
        name=f"Application stage {uuid.uuid4().hex[:6]}",
        description="Move applicants to contacted",
        icon="template",
        category="intake",
        subject_type="form_submission",
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[
            {"action_type": "update_field", "field": "stage_id", "value_stage_key": "contacted"}
        ],
        is_global=False,
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
    )
    db.add(template)
    db.flush()

    workflow = template_service.use_template(
        db,
        test_org.id,
        test_user.id,
        template.id,
        "Application stage from template",
        trigger_form_id=form.id,
    )

    contacted = _stage(db, test_org.id, stage_entity, "contacted")
    assert workflow.subject_type == "form_submission"
    assert workflow.actions[0]["value"] == str(contacted.id)


@pytest.mark.asyncio
async def test_builder_payload_saves_an_application_submitted_stage_update(
    authed_client, db, test_org, test_user
):
    form = _form(db, test_org.id, test_user.id, "surrogate")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")

    response = await authed_client.post(
        "/workflows",
        json={
            "name": "Builder application stage",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {"form_id": str(form.id)},
            "conditions": [_stage_condition(contacted)],
            "condition_logic": "AND",
            "actions": [_update_stage(contacted)],
            "is_enabled": True,
            "scope": "org",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["actions"][0]["value_stage_key"] == "contacted"
    assert body["conditions"][0]["stage_keys"] == ["contacted"]


def test_form_submission_stage_update_moves_the_linked_surrogate(db, test_org, test_user):
    new_stage = _stage(db, test_org.id, "surrogate", "new_unread")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    surrogate = _surrogate(db, test_org.id, test_user.id, new_stage)
    form = _form(db, test_org.id, test_user.id, "surrogate")
    submission = _submission(db, test_org.id, form, surrogate_id=surrogate.id)
    _intake_workflow(db, test_org.id, test_user.id, form=form, actions=[_update_stage(contacted)])

    workflow_triggers.trigger_form_submitted(
        db=db,
        org_id=test_org.id,
        form_id=form.id,
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
    )

    db.refresh(surrogate)
    assert surrogate.stage_id == contacted.id


def test_form_submission_stage_update_moves_the_linked_donor(db, test_org, test_user):
    donor = _donor(db, test_org.id, test_user.id, "egg")
    contacted = _stage(db, test_org.id, "egg_donor", "contacted")
    form = _form(db, test_org.id, test_user.id, "egg_donor")
    submission = _submission(db, test_org.id, form, donor_id=donor.id)
    _intake_workflow(db, test_org.id, test_user.id, form=form, actions=[_update_stage(contacted)])

    workflow_triggers.trigger_form_submitted(
        db=db,
        org_id=test_org.id,
        form_id=form.id,
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
    )

    db.refresh(donor)
    assert donor.stage_id == contacted.id


def test_intake_lead_stage_update_moves_the_promoted_surrogate(db, test_org, test_user):
    new_stage = _stage(db, test_org.id, "surrogate", "new_unread")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    surrogate = _surrogate(db, test_org.id, test_user.id, new_stage)
    form = _form(db, test_org.id, test_user.id, "surrogate")
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        source="shared_intake",
        lead_type="surrogate",
        full_name="Promoted Surrogate Lead",
        status="promoted",
        promoted_surrogate_id=surrogate.id,
    )
    db.add(lead)
    db.flush()
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        form=form,
        actions=[_update_stage(contacted)],
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": "surrogate"},
    )

    assert execution is not None
    assert execution.actions_executed[0]["success"] is True, execution.actions_executed
    db.refresh(surrogate)
    assert surrogate.stage_id == contacted.id


def test_unpromoted_intake_lead_skips_the_stage_update(db, test_org, test_user):
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    form = _form(db, test_org.id, test_user.id, "surrogate")
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        source="shared_intake",
        lead_type="surrogate",
        full_name="Pending Surrogate Lead",
        status="pending_review",
    )
    db.add(lead)
    db.flush()
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        form=form,
        actions=[_update_stage(contacted)],
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": "surrogate"},
    )

    assert execution is not None
    (result,) = execution.actions_executed
    assert result["skipped"] is True
    assert result["error"] == "Intake Lead is not linked to a surrogate"


def test_intake_lead_promoted_into_another_org_surrogate_is_not_updated(db, test_org, test_user):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Lead Org", slug=f"other-lead-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    foreign_stage = _stage(db, other_org.id, "surrogate", "new_unread")
    foreign_surrogate = _surrogate(db, other_org.id, test_user.id, foreign_stage)
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    form = _form(db, test_org.id, test_user.id, "surrogate")
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        source="shared_intake",
        lead_type="surrogate",
        full_name="Mislinked Lead",
        status="promoted",
        promoted_surrogate_id=foreign_surrogate.id,
    )
    db.add(lead)
    db.flush()
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        form=form,
        actions=[_update_stage(contacted)],
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": "surrogate"},
    )

    assert execution is not None
    (result,) = execution.actions_executed
    assert result["skipped"] is True
    assert result["error"] == "Surrogate not found for intake lead"
    db.refresh(foreign_surrogate)
    assert foreign_surrogate.stage_id == foreign_stage.id


def _custom_stage(db, org_id, user_id, entity_type: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, user_id, entity_type=entity_type
    )
    stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="secondary_review",
        label="Secondary Review",
        color="#475569",
        stage_type="intake",
        user_id=user_id,
    )
    return pipeline, stage


def _remove_stage(db, pipeline, removed, target, user_id) -> None:
    kept = [
        stage
        for stage in pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
        if stage.is_active and stage.id != removed.id
    ]
    pipeline_service.apply_pipeline_draft(
        db,
        pipeline,
        name=pipeline.name,
        stages=[
            {
                "id": str(stage.id),
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": index + 1,
                "category": stage.stage_type,
                "is_active": stage.is_active,
                "semantics": stage.semantics,
            }
            for index, stage in enumerate(kept)
        ],
        feature_config=pipeline.feature_config,
        remaps=[{"removed_stage_key": removed.stage_key, "target_stage_key": target.stage_key}],
        user_id=user_id,
    )


def test_pipeline_remaps_move_intake_stage_references_only_in_the_form_pipeline(
    db, test_org, test_user
):
    from app.services import pipeline_dependency_service

    egg_pipeline, egg_custom = _custom_stage(db, test_org.id, test_user.id, "egg_donor")
    surrogate_pipeline, surrogate_custom = _custom_stage(db, test_org.id, test_user.id, "surrogate")
    egg_form = _form(db, test_org.id, test_user.id, "egg_donor")
    surrogate_form = _form(db, test_org.id, test_user.id, "surrogate")
    egg_workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=egg_form,
        conditions=[_stage_condition(egg_custom)],
        actions=[_update_stage(egg_custom)],
    )
    surrogate_workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        form=surrogate_form,
        conditions=[_stage_condition(surrogate_custom)],
        actions=[_update_stage(surrogate_custom)],
    )
    db.commit()

    def workflow_refs(pipeline, stage_key):
        graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, pipeline)
        (entry,) = [item for item in graph["stages"] if item["stage_key"] == stage_key]
        return {ref["id"] for ref in entry["workflow_refs"]}

    assert workflow_refs(egg_pipeline, "secondary_review") == {str(egg_workflow.id)}
    assert workflow_refs(surrogate_pipeline, "secondary_review") == {str(surrogate_workflow.id)}

    surrogate_contacted = _stage(db, test_org.id, "surrogate", "contacted")
    _remove_stage(db, surrogate_pipeline, surrogate_custom, surrogate_contacted, test_user.id)
    db.refresh(egg_workflow)
    db.refresh(surrogate_workflow)
    assert surrogate_workflow.actions[0]["value"] == str(surrogate_contacted.id)
    assert surrogate_workflow.conditions[0]["stage_keys"] == ["contacted"]
    assert egg_workflow.actions[0]["value"] == str(egg_custom.id)
    assert egg_workflow.conditions[0]["value"] == [str(egg_custom.id)]

    egg_contacted = _stage(db, test_org.id, "egg_donor", "contacted")
    _remove_stage(db, egg_pipeline, egg_custom, egg_contacted, test_user.id)
    db.refresh(egg_workflow)
    assert egg_workflow.actions[0]["value"] == str(egg_contacted.id)
    assert egg_workflow.actions[0]["value_stage_key"] == "contacted"
    assert egg_workflow.conditions[0]["value"] == [str(egg_contacted.id)]
