"""Fixed-subject triggers must be stored with the subject they execute against."""

from __future__ import annotations

import json
import uuid

import pytest

from app.db.enums import WorkflowTriggerType
from app.db.models import AutomationWorkflow, FormSubmission, IntakeLead, WorkflowExecution
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services import workflow_service

FIXED_TRIGGER_SUBJECTS = [
    (WorkflowTriggerType.FORM_SUBMITTED, "form_submission"),
    (WorkflowTriggerType.INTAKE_LEAD_CREATED, "intake_lead"),
    (WorkflowTriggerType.MATCH_PROPOSED, "match"),
    (WorkflowTriggerType.MATCH_ACCEPTED, "match"),
    (WorkflowTriggerType.MATCH_DECLINED, "match"),
    (WorkflowTriggerType.MATCH_CANCELLED, "match"),
    (WorkflowTriggerType.APPOINTMENT_SCHEDULED, "appointment"),
    (WorkflowTriggerType.APPOINTMENT_COMPLETED, "appointment"),
    (WorkflowTriggerType.APPOINTMENT_CANCELLED, "appointment"),
    (WorkflowTriggerType.APPOINTMENT_NO_SHOW, "appointment"),
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter(monkeypatch):
    from app.core import rate_limit
    from app.core.rate_limit import limiter

    client_key = f"fixed-subject-test-{uuid.uuid4().hex}"
    monkeypatch.setattr(rate_limit, "get_client_ip", lambda request: client_key)
    limiter.reset()
    yield
    limiter.reset()


def _notification_action() -> dict:
    return {"action_type": "send_notification", "title": "Heads up", "recipients": "owner"}


@pytest.mark.parametrize(("trigger_type", "fixed_subject"), FIXED_TRIGGER_SUBJECTS)
def test_create_rejects_surrogate_subject_for_fixed_subject_trigger(
    db, test_org, test_user, trigger_type, fixed_subject
):
    with pytest.raises(
        ValueError,
        match=f"Trigger {trigger_type.value} requires the {fixed_subject} subject",
    ):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name="Mismatched subject",
                subject_type="surrogate",
                trigger_type=trigger_type,
                actions=[_notification_action()],
            ),
        )


@pytest.mark.parametrize(("trigger_type", "fixed_subject"), FIXED_TRIGGER_SUBJECTS)
def test_create_derives_fixed_subject_when_omitted(
    db, test_org, test_user, trigger_type, fixed_subject
):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Derived {fixed_subject}",
            trigger_type=trigger_type,
            actions=[_notification_action()],
        ),
    )

    assert workflow.subject_type == fixed_subject


@pytest.mark.parametrize(
    "fixed_subject", ["form_submission", "intake_lead", "match", "appointment"]
)
def test_create_rejects_fixed_subject_for_unrelated_trigger(db, test_org, test_user, fixed_subject):
    with pytest.raises(
        ValueError,
        match=f"Subject {fixed_subject} does not support trigger status_changed",
    ):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name="Unrelated trigger",
                subject_type=fixed_subject,
                trigger_type=WorkflowTriggerType.STATUS_CHANGED,
                actions=[_notification_action()],
            ),
        )


def test_update_trigger_change_rederives_subject(db, test_org, test_user):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="Changing trigger",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            actions=[_notification_action()],
        ),
    )
    assert workflow.subject_type == "surrogate"

    workflow = workflow_service.update_workflow(
        db,
        workflow,
        test_user.id,
        WorkflowUpdate(trigger_type=WorkflowTriggerType.FORM_SUBMITTED),
    )
    assert workflow.trigger_type == "form_submitted"
    assert workflow.subject_type == "form_submission"

    workflow = workflow_service.update_workflow(
        db,
        workflow,
        test_user.id,
        WorkflowUpdate(trigger_type=WorkflowTriggerType.MATCH_ACCEPTED),
    )
    assert workflow.subject_type == "match"

    workflow = workflow_service.update_workflow(
        db,
        workflow,
        test_user.id,
        WorkflowUpdate(trigger_type=WorkflowTriggerType.STATUS_CHANGED),
    )
    assert workflow.subject_type == "surrogate"


def test_update_donor_workflow_to_fixed_trigger_is_rejected(db, test_org, test_user):
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="Donor workflow",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[_notification_action()],
        ),
    )

    with pytest.raises(ValueError, match="Trigger form_submitted does not support egg_donor"):
        workflow_service.update_workflow(
            db,
            workflow,
            test_user.id,
            WorkflowUpdate(trigger_type=WorkflowTriggerType.FORM_SUBMITTED),
        )
    assert workflow.subject_type == "egg_donor"
    assert workflow.trigger_type == "donor_created"


@pytest.mark.asyncio
async def test_api_rejects_mismatched_fixed_trigger_subject(authed_client):
    response = await authed_client.post(
        "/workflows",
        json={
            "name": "Mismatched API subject",
            "subject_type": "surrogate",
            "trigger_type": "form_submitted",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [_notification_action()],
            "is_enabled": True,
            "scope": "org",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == (
        "Trigger form_submitted requires the form_submission subject"
    )


@pytest.mark.asyncio
async def test_builder_payload_workflow_runs_on_real_form_submission(authed_client, db, test_org):
    from tests.test_forms_public_shared_intake import _create_published_form_and_shared_link

    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    create_response = await authed_client.post(
        "/workflows",
        json={
            "name": "Builder intake routing",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {"form_id": form_id},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [{"action_type": "create_intake_lead"}],
            "is_enabled": True,
            "scope": "org",
        },
    )
    assert create_response.status_code == 200, create_response.text
    workflow_id = uuid.UUID(create_response.json()["id"])
    assert db.get(AutomationWorkflow, workflow_id).subject_type == "form_submission"

    submit_response = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Builder Lead",
                    "date_of_birth": "1992-05-14",
                    "phone": "+1 (555) 100-2201",
                    "email": "builder-lead@example.com",
                }
            )
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    body = submit_response.json()
    assert db.get(FormSubmission, uuid.UUID(body["id"])).match_status == "lead_created"

    submission = db.get(FormSubmission, uuid.UUID(body["id"]))
    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.workflow_id == workflow_id,
        )
        .one()
    )
    assert execution.subject_type == "form_submission"
    assert execution.subject_id == submission.id
    assert (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == test_org.id,
            IntakeLead.form_submission_id == submission.id,
        )
        .count()
        == 1
    )
