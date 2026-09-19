"""Shared donor forms retain subtype routing through workflow configuration."""

import uuid

import pytest

from app.core.config import settings
from app.db.enums import WorkflowTriggerType
from app.db.models import FormSubmission, IntakeLead, WorkflowExecution
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services import workflow_service, workflow_triggers
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer,lead_kind", [("Egg donor", "egg_donor"), ("Sperm donor", "sperm_donor")]
)
@pytest.mark.parametrize(
    "trigger_type,context_key",
    [
        (WorkflowTriggerType.FORM_SUBMITTED, "lead_kind"),
        (WorkflowTriggerType.INTAKE_LEAD_CREATED, "lead_type"),
    ],
)
async def test_shared_donor_form_workflows_match_both_subtypes(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
    answer,
    lead_kind,
    trigger_type,
    context_key,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    form_id, slug = await _create_donor_form(authed_client, shared_donor=True)
    # Draft mapping edits must not narrow the published form's donor programs.
    mappings = (await authed_client.get(f"/forms/{form_id}/mappings")).json()
    changed = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": item["field_key"], "surrogate_field": item["surrogate_field"]}
                for item in mappings
                if item["surrogate_field"] != "donor_type"
            ]
        },
    )
    assert changed.status_code == 200, changed.text
    workflows = {}
    for kind in (None, "egg_donor", "sperm_donor"):
        workflow = workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Shared donor {kind} {uuid.uuid4()}",
                scope="org",
                subject_type="form_submission" if context_key == "lead_kind" else "intake_lead",
                trigger_type=trigger_type,
                trigger_config={"form_id": form_id, **({context_key: kind} if kind else {})},
                actions=[
                    {
                        "action_type": "send_notification",
                        "title": "Matched donor",
                        "recipients": "creator",
                    }
                ],
            ),
        )
        workflow = workflow_service.update_workflow(
            db, workflow, test_user.id, WorkflowUpdate(name=f"Updated {workflow.name}")
        )
        assert workflow.trigger_config.get(context_key) == kind
        workflows[kind] = workflow.id

    with pytest.raises(ValueError, match="must match"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name="Invalid surrogate filter",
                subject_type="form_submission",
                trigger_type=trigger_type,
                trigger_config={"form_id": form_id, context_key: "surrogate"},
                actions=[
                    {
                        "action_type": "send_notification",
                        "title": "Invalid",
                        "recipients": "creator",
                    }
                ],
            ),
        )

    submitted = await _submit_donor_form(
        authed_client, slug=slug, email="shared-workflow@example.com", donor_type=answer
    )
    assert submitted.status_code == 200, submitted.text
    submission = db.get(FormSubmission, uuid.UUID(submitted.json()["id"]))
    assert submission.lead_kind == lead_kind
    entity_id = submission.id
    if trigger_type == WorkflowTriggerType.INTAKE_LEAD_CREATED:
        lead = IntakeLead(
            organization_id=test_org.id,
            source="shared_intake",
            lead_type=lead_kind,
            full_name="Workflow Test",
            email="workflow-lead@example.com",
            status="pending_review",
            created_by_user_id=test_user.id,
        )
        db.add(lead)
        db.flush()
        workflow_triggers.trigger_intake_lead_created(
            db, lead, form_id=uuid.UUID(form_id), submission_id=submission.id
        )
        entity_id = lead.id
    executions = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.entity_id == entity_id,
            WorkflowExecution.workflow_id.in_(list(workflows.values())),
        )
        .all()
    )
    assert {execution.workflow_id for execution in executions} == {
        workflows[None],
        workflows[lead_kind],
    }
    assert all(execution.trigger_event[context_key] == lead_kind for execution in executions)


@pytest.mark.asyncio
async def test_shared_donor_workflow_keeps_donor_access_and_org_scope(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.core.policies import POLICIES
    from app.db.models import Organization
    from app.services import permission_service

    form_id, _slug = await _create_donor_form(authed_client, shared_donor=True)
    payload = WorkflowCreate(
        name="Shared donor scope check",
        scope="org",
        subject_type="form_submission",
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
        trigger_config={"form_id": form_id},
        actions=[
            {"action_type": "send_notification", "title": "Scope test", "recipients": "creator"}
        ],
    )
    foreign_org = Organization(name="Foreign workflow org", slug=f"foreign-{uuid.uuid4()}")
    db.add(foreign_org)
    db.flush()
    with pytest.raises(ValueError, match="not found in organization"):
        workflow_service.create_workflow(db, foreign_org.id, test_user.id, payload)

    workflow = workflow_service.create_workflow(db, test_org.id, test_user.id, payload)
    assert "lead_kind" not in workflow.trigger_config
    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)
    detail = await authed_client.get(f"/workflows/{workflow.id}")
    assert detail.status_code == 403
    listed = await authed_client.get("/workflows")
    assert listed.status_code == 200
    assert str(workflow.id) not in {item["id"] for item in listed.json()}
    denied = await authed_client.post("/workflows", json=payload.model_dump(mode="json"))
    assert denied.status_code == 403
