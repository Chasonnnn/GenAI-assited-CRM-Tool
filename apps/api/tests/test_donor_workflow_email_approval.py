"""Donor template emails match surrogates: approval is optional."""

import uuid

import pytest

from app.core.policies import POLICIES
from app.db.enums import JobType, Role, WorkflowExecutionStatus, WorkflowTriggerType
from app.db.models import EmailTemplate, Job, Membership, User, UserPermissionOverride
from app.schemas.donor import DonorCreate
from app.schemas.workflow import WorkflowCreate
from app.services import donor_service, workflow_service
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


def _template(db, org_id, user_id) -> EmailTemplate:
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=org_id,
        created_by_user_id=user_id,
        name=f"Donor welcome {uuid.uuid4()}",
        subject="Welcome",
        body="<p>Thanks for applying</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()
    return template


def _email_jobs(db, org_id) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.organization_id == org_id, Job.job_type == JobType.WORKFLOW_EMAIL.value)
        .all()
    )


def test_unowned_donor_assign_then_email_runs_without_approval(
    db, test_org, test_user, monkeypatch
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Unowned Website Donor",
            email=f"unowned-{uuid.uuid4().hex[:8]}@example.com",
        ),
        emit_workflow_events=False,
    )
    assert donor.owner_id is None
    template = _template(db, test_org.id, test_user.id)
    _mock_email_provider(monkeypatch)

    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Assign and welcome {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[
                {
                    "action_type": "assign_donor",
                    "owner_type": "user",
                    "owner_id": str(test_user.id),
                },
                {
                    "action_type": "send_email",
                    "template_id": str(template.id),
                    "recipients": "donor",
                },
            ],
        ),
    )
    assert (
        "requires_approval" not in workflow.actions[1]
        or not workflow.actions[1]["requires_approval"]
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"donor_id": str(donor.id)},
    )

    assert execution is not None
    assert execution.status == WorkflowExecutionStatus.SUCCESS.value, execution.actions_executed
    db.refresh(donor)
    assert (donor.owner_type, donor.owner_id) == ("user", test_user.id)
    jobs = _email_jobs(db, test_org.id)
    assert len(jobs) == 1
    assert jobs[0].payload["recipient_email"] == donor.email


@pytest.mark.parametrize("access", ["authorized", "revoked"])
def test_unapproved_donor_email_still_filters_internal_recipients(
    db, test_org, test_user, monkeypatch, access
):
    recipient = User(
        id=uuid.uuid4(),
        email=f"donor-owner-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Donor Owner",
        is_active=True,
    )
    db.add(recipient)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            user_id=recipient.id,
            role=Role.ADMIN.value,
            is_active=True,
        )
    )
    if access == "revoked":
        db.add(
            UserPermissionOverride(
                organization_id=test_org.id,
                user_id=recipient.id,
                permission=POLICIES["donors"].default.value,
                override_type="revoke",
            )
        )
    db.flush()
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Owner Email Donor",
            email=f"owner-email-{uuid.uuid4().hex[:8]}@example.com",
            owner_type="user",
            owner_id=recipient.id,
        ),
        emit_workflow_events=False,
    )
    template = _template(db, test_org.id, test_user.id)
    _mock_email_provider(monkeypatch)
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Owner donor email {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[
                {
                    "action_type": "send_email",
                    "template_id": str(template.id),
                    "recipients": "owner",
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
        event_data={"donor_id": str(donor.id)},
    )

    assert execution is not None
    jobs = _email_jobs(db, test_org.id)
    if access == "authorized":
        assert execution.status == WorkflowExecutionStatus.SUCCESS.value
        assert [job.payload["recipient_email"] for job in jobs] == [recipient.email]
    else:
        assert execution.status == WorkflowExecutionStatus.PARTIAL.value
        assert jobs == []
        assert recipient.email not in str(execution.actions_executed)
