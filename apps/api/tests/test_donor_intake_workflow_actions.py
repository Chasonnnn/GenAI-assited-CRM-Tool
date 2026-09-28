"""Form submission and intake lead workflows act on the linked donor with donor rules."""

import uuid

import pytest

from app.db.enums import JobType, WorkflowTriggerType
from app.db.models import (
    EmailTemplate,
    EntityNote,
    Form,
    FormSubmission,
    IntakeLead,
    Job,
    Notification,
    Organization,
    Task,
    WorkflowExecution,
)
from app.schemas.donor import DonorCreate
from app.schemas.workflow import WorkflowCreate
from app.services import donor_service, workflow_service, workflow_triggers
from app.services.workflow_engine import engine


def _mock_email_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_service,
        "validate_email_provider",
        lambda *_args, **_kwargs: (True, None),
    )
    monkeypatch.setattr(
        "app.services.workflow_email_provider.resolve_workflow_email_provider",
        lambda **_kwargs: (
            "resend",
            {"from_email": "workflows@example.com", "from_name": "Workflow Team"},
        ),
    )


def _donor(db, org_id, user_id, *, donor_type="egg", owner_id=None):
    return donor_service.create_donor(
        db,
        org_id,
        user_id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Linked Intake Donor",
            email=f"linked-{uuid.uuid4().hex[:8]}@example.com",
            owner_type="user",
            owner_id=owner_id or user_id,
        ),
        emit_workflow_events=False,
    )


def _donor_form(db, org_id, user_id, lead_kind="egg_donor") -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"Donor intake {uuid.uuid4().hex[:6]}",
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


def _submission(db, org_id, form, *, donor_id=None) -> FormSubmission:
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=org_id,
        form=form,
        lead_kind=form.lead_kind,
        source_mode="shared",
        match_status="linked" if donor_id else "unmatched",
        status="pending_review",
        answers_json={},
        donor_id=donor_id,
    )
    db.add(submission)
    db.flush()
    return submission


def _template(db, org_id, user_id) -> EmailTemplate:
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=org_id,
        created_by_user_id=user_id,
        name=f"Donor intake email {uuid.uuid4()}",
        subject="Thanks",
        body="<p>Thanks for applying</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template


def _form_workflow(db, org_id, user_id, form, actions):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"Donor form actions {uuid.uuid4()}",
            subject_type="form_submission",
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
            trigger_config={"form_id": str(form.id)},
            actions=actions,
        ),
    )


def _submit(db, org_id, form, submission) -> WorkflowExecution:
    workflow_triggers.trigger_form_submitted(
        db=db,
        org_id=org_id,
        form_id=form.id,
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
    )
    return (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.entity_id == submission.id,
        )
        .one()
    )


def _other_org_donor(db, test_user):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Donor Org", slug=f"other-donor-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    return donor_service.create_donor(
        db,
        other_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Other Org Donor",
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        ),
        emit_workflow_events=False,
    )


def test_linked_donor_form_submission_runs_donor_actions(db, test_org, test_user, monkeypatch):
    _mock_email_provider(monkeypatch)
    donor = _donor(db, test_org.id, test_user.id)
    form = _donor_form(db, test_org.id, test_user.id)
    submission = _submission(db, test_org.id, form, donor_id=donor.id)
    template = _template(db, test_org.id, test_user.id)
    _form_workflow(
        db,
        test_org.id,
        test_user.id,
        form,
        [
            {
                "action_type": "send_email",
                "template_id": str(template.id),
                "recipients": "surrogate",
            },
            {"action_type": "create_task", "title": "Call donor applicant", "assignee": "owner"},
            {"action_type": "add_note", "content": "Returning donor applied"},
            {"action_type": "send_notification", "title": "Donor applied", "recipients": "owner"},
            {"action_type": "update_field", "field": "is_priority", "value": True},
            {
                "action_type": "assign_surrogate",
                "owner_type": "user",
                "owner_id": str(test_user.id),
            },
        ],
    )

    execution = _submit(db, test_org.id, form, submission)

    results = execution.actions_executed
    assert [result["success"] for result in results[:4]] == [True, True, True, True], results
    assert results[4] == {
        "action_type": "update_field",
        "success": False,
        "error": "Field is_priority not allowed for donor update",
    }
    assert results[5]["skipped"] is True
    assert results[5]["error"] == "Action 'assign_surrogate' does not support donor subjects"

    job = (
        db.query(Job)
        .filter(Job.organization_id == test_org.id, Job.job_type == JobType.WORKFLOW_EMAIL.value)
        .one()
    )
    assert job.payload["recipient_email"] == donor.email
    assert (job.payload["subject_type"], job.payload["subject_id"]) == ("egg_donor", str(donor.id))
    task = db.query(Task).filter(Task.title == "Call donor applicant").one()
    assert (task.donor_id, task.surrogate_id, task.owner_id) == (donor.id, None, test_user.id)
    note = (
        db.query(EntityNote)
        .filter(EntityNote.entity_type == "donor", EntityNote.entity_id == donor.id)
        .one()
    )
    assert "Returning donor applied" in note.content
    notification = (
        db.query(Notification)
        .filter(Notification.organization_id == test_org.id, Notification.title == "Donor applied")
        .one()
    )
    assert (notification.user_id, notification.entity_type, notification.entity_id) == (
        test_user.id,
        "donor",
        donor.id,
    )


def test_unlinked_donor_form_submission_skips_record_actions(db, test_org, test_user):
    form = _donor_form(db, test_org.id, test_user.id, lead_kind="sperm_donor")
    submission = _submission(db, test_org.id, form)
    _form_workflow(
        db,
        test_org.id,
        test_user.id,
        form,
        [
            {"action_type": "create_task", "title": "Unlinked donor task", "assignee": "owner"},
            {"action_type": "send_notification", "title": "Donor form in", "recipients": "creator"},
        ],
    )

    execution = _submit(db, test_org.id, form, submission)

    task_result, notification_result = execution.actions_executed
    assert task_result["skipped"] is True
    assert task_result["error"] == "Form Submission is not linked to a donor"
    assert notification_result["success"] is True
    assert db.query(Task).filter(Task.title == "Unlinked donor task").count() == 0


@pytest.mark.parametrize("link", ["cross_org", "archived"])
def test_unavailable_linked_donor_fails_closed(db, test_org, test_user, link):
    if link == "cross_org":
        donor = _other_org_donor(db, test_user)
    else:
        donor = _donor(db, test_org.id, test_user.id)
        donor.is_archived = True
        db.flush()
    form = _donor_form(db, test_org.id, test_user.id)
    submission = _submission(db, test_org.id, form, donor_id=donor.id)
    _form_workflow(
        db,
        test_org.id,
        test_user.id,
        form,
        [
            {"action_type": "add_note", "content": "Should not attach"},
            {"action_type": "send_notification", "title": "Hidden donor", "recipients": "owner"},
        ],
    )

    execution = _submit(db, test_org.id, form, submission)

    for result in execution.actions_executed:
        assert result["success"] is False
        assert result["skipped"] is True
        assert result["error"] == "Donor not found for form submission"
    assert (
        db.query(EntityNote)
        .filter(EntityNote.entity_type == "donor", EntityNote.entity_id == donor.id)
        .count()
        == 0
    )
    assert db.query(Notification).filter(Notification.title == "Hidden donor").count() == 0


def test_promoted_donor_intake_lead_notifies_donor_owner(db, test_org, test_user):
    donor = _donor(db, test_org.id, test_user.id, donor_type="sperm")
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        source="shared_intake",
        lead_type="sperm_donor",
        full_name="Promoted Donor Lead",
        email=f"promoted-{uuid.uuid4().hex[:8]}@example.com",
        status="promoted",
        promoted_donor_id=donor.id,
    )
    db.add(lead)
    db.flush()
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Promoted donor lead {uuid.uuid4()}",
            subject_type="intake_lead",
            trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
            trigger_config={"lead_type": "sperm_donor"},
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Lead promoted",
                    "recipients": "owner",
                }
            ],
        ),
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": "sperm_donor"},
    )

    assert execution is not None
    assert execution.actions_executed[0]["success"] is True, execution.actions_executed
    notification = db.query(Notification).filter(Notification.title == "Lead promoted").one()
    assert (notification.user_id, notification.entity_type, notification.entity_id) == (
        test_user.id,
        "donor",
        donor.id,
    )
