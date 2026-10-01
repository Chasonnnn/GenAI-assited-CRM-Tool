"""Send Email to staff: queues, roles, custom addresses, and unlinked intake records."""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import JobType, Role, WorkflowTriggerType
from app.db.models import (
    EmailTemplate,
    Job,
    Membership,
    Organization,
    Queue,
    QueueMember,
    User,
)
from app.schemas.workflow import WorkflowCreate
from app.services import workflow_communication_actions, workflow_email_provider, workflow_service


@pytest.fixture
def org_email(db, test_org, test_user, monkeypatch):
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Staff alert",
        subject="New record {{full_name}}",
        body="<p>{{form_name}} {{record_link}}</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.flush()
    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda *_args, **_kwargs: (
            "resend",
            {"from_email": "care@example.com", "from_name": "Care"},
        ),
    )
    return template


def _member(db, org_id, role=Role.CASE_MANAGER, *, active=True) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"staff-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Staff Member",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=role,
            is_active=active,
        )
    )
    db.flush()
    return user


def _queue(db, org_id, members: list[User]) -> Queue:
    queue = Queue(id=uuid.uuid4(), organization_id=org_id, name=f"Intake {uuid.uuid4().hex[:6]}")
    db.add(queue)
    db.flush()
    for member in members:
        db.add(QueueMember(id=uuid.uuid4(), queue_id=queue.id, user_id=member.id))
    db.flush()
    return queue


def _queued_recipients(db, org_id, result) -> set[str]:
    assert result["success"] is True, result
    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
            Job.id.in_([uuid.UUID(job_id) for job_id in result["job_ids"]]),
        )
        .all()
    )
    return {job.payload["recipient_email"] for job in jobs}


def _send(db, entity, template, **action):
    return workflow_communication_actions.send_email(
        db=db,
        action={"action_type": "send_email", "template_id": str(template.id), **action},
        entity=entity,
        event_id=uuid.uuid4(),
    )


def _surrogate(db, org_id, user_id, stage, **fields):
    from tests.test_form_submission_service import _create_surrogate

    surrogate = _create_surrogate(db, org_id, user_id, stage)
    for key, value in fields.items():
        setattr(surrogate, key, value)
    db.flush()
    return surrogate


def test_queue_recipients_reach_active_members_only(
    db, test_org, test_user, default_stage, org_email
):
    active = _member(db, test_org.id)
    inactive = _member(db, test_org.id, active=False)
    queue = _queue(db, test_org.id, [active, inactive])
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)

    result = _send(db, surrogate, org_email, recipients="queue", recipient_queue_id=str(queue.id))
    assert _queued_recipients(db, test_org.id, result) == {active.email}


def test_owner_recipient_expands_an_owning_queue(db, test_org, test_user, default_stage, org_email):
    member = _member(db, test_org.id)
    queue = _queue(db, test_org.id, [member])
    surrogate = _surrogate(
        db, test_org.id, test_user.id, default_stage, owner_type="queue", owner_id=queue.id
    )

    result = _send(db, surrogate, org_email, recipients="owner")
    assert _queued_recipients(db, test_org.id, result) == {member.email}


def test_role_and_custom_recipients(db, test_org, test_user, default_stage, org_email):
    intake = _member(db, test_org.id, Role.INTAKE_SPECIALIST)
    _member(db, test_org.id, Role.CASE_MANAGER)
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)

    by_role = _send(db, surrogate, org_email, recipients="role", recipient_role="intake_specialist")
    assert _queued_recipients(db, test_org.id, by_role) == {intake.email}

    custom = _send(
        db, surrogate, org_email, recipients="custom", recipient_emails=["intake@agency.test"]
    )
    assert _queued_recipients(db, test_org.id, custom) == {"intake@agency.test"}


def test_queue_from_another_org_is_never_emailed(db, test_org, test_user, default_stage, org_email):
    other_org = Organization(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    outsider = _member(db, other_org.id)
    foreign_queue = _queue(db, other_org.id, [outsider])
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)

    result = _send(
        db, surrogate, org_email, recipients="queue", recipient_queue_id=str(foreign_queue.id)
    )
    assert result == {"success": False, "error": "No recipient emails resolved"}

    with pytest.raises(ValueError, match="Recipient queue not found in organization"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Foreign queue {uuid.uuid4()}",
                trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
                actions=[
                    {
                        "action_type": "send_email",
                        "template_id": str(org_email.id),
                        "recipients": "queue",
                        "recipient_queue_id": str(foreign_queue.id),
                    }
                ],
            ),
        )


@pytest.mark.parametrize(
    ("action", "error"),
    [
        ({"recipients": "queue"}, "Queue recipients require a queue"),
        ({"recipients": "role"}, "Role recipients require a role"),
        ({"recipients": "custom"}, "Custom recipients require at least one email address"),
        ({"recipients": "custom", "recipient_emails": ["not-an-email"]}, "email"),
    ],
)
def test_staff_recipient_kinds_require_their_target(
    db, test_org, test_user, org_email, action, error
):
    with pytest.raises(ValueError, match=error):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Incomplete recipients {uuid.uuid4()}",
                trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
                actions=[{"action_type": "send_email", "template_id": str(org_email.id), **action}],
            ),
        )


def test_intake_lead_email_requires_staff_recipients(db, test_org, test_user, org_email):
    def create(recipients):
        return workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name=f"Lead email {uuid.uuid4()}",
                trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
                actions=[
                    {
                        "action_type": "send_email",
                        "template_id": str(org_email.id),
                        "recipients": recipients,
                    }
                ],
            ),
        )

    with pytest.raises(ValueError, match="Intake lead emails must go to staff recipients"):
        create("subject")
    assert create("all_admins").actions[0]["recipients"] == "all_admins"

    options = workflow_service.get_workflow_options(db, test_org.id, user_id=test_user.id)
    assert "send_email" in options.action_types_by_trigger["intake_lead_created"]


def test_unlinked_submission_emails_staff_with_record_variables(
    db, test_org, test_user, default_stage, org_email
):
    from app.services import workflow_engine_adapters
    from tests.test_form_submission_service import (
        _answers,
        _create_published_form,
        _create_shared_submission,
        _create_surrogate,
    )

    form = _create_published_form(db, test_org.id, test_user.id)
    submission = _create_shared_submission(
        db,
        form=form,
        surrogate=_create_surrogate(db, test_org.id, test_user.id, default_stage),
        user_id=test_user.id,
        answers=_answers(),
    )
    submission.surrogate_id = None
    db.flush()

    action = {
        "action_type": "send_email",
        "template_id": str(org_email.id),
        "recipients": [str(test_user.id)],
    }
    result = workflow_engine_adapters.DefaultWorkflowDomainAdapter().execute_action(
        db=db,
        action=action,
        entity=submission,
        entity_type="form_submission",
        event_id=uuid.uuid4(),
        depth=0,
        trigger_callback=lambda **_kwargs: None,
    )
    assert _queued_recipients(db, test_org.id, result) == {test_user.email}
    job = db.query(Job).filter(Job.id == uuid.UUID(result["job_ids"][0])).one()
    assert job.payload["subject_type"] == "form_submission"
    assert job.payload["subject_id"] == str(submission.id)
    assert job.payload["surrogate_id"] is None
    variables = job.payload["variables"]
    assert variables["full_name"] == "Jane Doe"
    assert variables["form_name"] == form.name
    assert variables["record_link"].endswith(f"/automation/form-submissions?form={form.id}")

    contact = workflow_engine_adapters.DefaultWorkflowDomainAdapter().execute_action(
        db=db,
        action={**action, "recipients": "surrogate"},
        entity=submission,
        entity_type="form_submission",
        event_id=uuid.uuid4(),
        depth=0,
        trigger_callback=lambda **_kwargs: None,
    )
    assert contact["skipped"] is True


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ({"recipients": "queue", "recipient_queue_id": str(uuid.uuid4())}, "to queue members"),
        ({"recipients": "role", "recipient_role": "case_manager"}, "to case manager members"),
        ({"recipients": "custom", "recipient_emails": ["a@agency.test"]}, "to 1 address(es)"),
    ],
)
def test_approval_preview_describes_staff_recipients(
    db, test_org, test_user, default_stage, org_email, action, expected
):
    from app.services.workflow_action_preview import build_action_preview

    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    preview = build_action_preview(
        db, {"action_type": "send_email", "template_id": str(org_email.id), **action}, surrogate
    )
    assert preview == f"Send 'Staff alert' {expected}"
