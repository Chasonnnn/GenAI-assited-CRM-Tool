"""Workflow paths must preserve shared record behavior after async boundaries."""

import uuid
from datetime import timedelta

import pytest

from app.db.enums import TaskStatus, WorkflowTriggerType
from app.db.models import EmailLog, EmailTemplate, EntityActivityLog, EntityNote, Job, Task
from app.schemas.donor import DonorCreate
from app.schemas.workflow import WorkflowCreate
from app.services import donor_service, email_service, workflow_service, workflow_triggers
from app.services.workflow_engine import engine


@pytest.fixture
def owned_donor(db, test_org, test_user):
    return donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Synthetic Donor",
            email=f"shared-workflow-{uuid.uuid4()}@example.com",
            owner_type="user",
            owner_id=test_user.id,
        ),
    )


def _workflow(db, test_org, test_user, *, requires_approval=False):
    return workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Shared donor note {uuid.uuid4()}",
            subject_type="egg_donor",
            trigger_type=WorkflowTriggerType.DONOR_UPDATED,
            trigger_config={"fields": ["education"]},
            actions=[
                {
                    "action_type": "add_note",
                    "content": '<p>Reviewed</p><img src="x" onerror="alert(1)">',
                    "requires_approval": requires_approval,
                }
            ],
        ),
    )


def _execute(db, workflow, donor, **kwargs):
    return engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"changed_fields": ["education"]},
        **kwargs,
    )


@pytest.mark.parametrize("bypass_dedupe", [False, True], ids=["initial", "retry"])
def test_archived_donor_cannot_start_or_retry_workflow(
    db, test_org, test_user, owned_donor, bypass_dedupe
):
    workflow = _workflow(db, test_org, test_user)
    donor_service.archive_donor(db, owned_donor, test_user.id)

    execution = _execute(db, workflow, owned_donor, bypass_dedupe=bypass_dedupe)

    assert execution is None
    assert db.query(EntityNote).filter(EntityNote.entity_id == owned_donor.id).count() == 0


def test_archived_donor_approval_resume_stops_before_actions(db, test_org, test_user, owned_donor):
    workflow = _workflow(db, test_org, test_user, requires_approval=True)
    execution = _execute(db, workflow, owned_donor)
    assert execution.status == "paused"
    task = db.query(Task).filter(Task.workflow_execution_id == execution.id).one()
    donor_service.archive_donor(db, owned_donor, test_user.id)
    task.status = TaskStatus.COMPLETED.value
    db.commit()

    engine.continue_execution(db, execution.id, task, "approve")

    db.refresh(execution)
    assert execution.status == "failed"
    assert execution.paused_task_id is None
    assert execution.paused_at_action_index is None
    assert db.query(EntityNote).filter(EntityNote.entity_id == owned_donor.id).count() == 0


def test_archived_donor_action_rechecks_subject_after_dispatch(db, test_user, owned_donor):
    donor_service.archive_donor(db, owned_donor, test_user.id)

    result = engine.adapter.execute_action(
        db=db,
        action={"action_type": "add_note", "content": "Must not be written"},
        entity=owned_donor,
        entity_type="donor",
        event_id=uuid.uuid4(),
        depth=0,
        subject_type="egg_donor",
        subject_id=owned_donor.id,
    )

    assert result["success"] is False
    assert db.query(EntityNote).filter(EntityNote.entity_id == owned_donor.id).count() == 0


def test_workflow_note_sanitizes_and_records_durable_activity_without_recursion(
    db, test_org, test_user, owned_donor, monkeypatch
):
    workflow = _workflow(db, test_org, test_user)

    def reject_recursive_trigger(*args, **kwargs):
        pytest.fail("Workflow-authored notes must not dispatch a fresh depth-zero event")

    monkeypatch.setattr(workflow_triggers, "trigger_note_added", reject_recursive_trigger)
    execution = _execute(db, workflow, owned_donor)

    assert execution.status == "success"
    note = db.query(EntityNote).filter(EntityNote.entity_id == owned_donor.id).one()
    assert note.content == "<p>Reviewed</p>"
    activity = (
        db.query(EntityActivityLog)
        .filter(
            EntityActivityLog.donor_id == owned_donor.id,
            EntityActivityLog.activity_type == "note_added",
        )
        .one()
    )
    assert activity.details == {"note_id": str(note.id)}


def test_workflow_and_campaign_donor_template_context_matches(db, owned_donor):
    expected = email_service.build_donor_template_variables(db, owned_donor)
    actual = engine.adapter._resolve_email_variables(db, owned_donor)

    # Unsubscribe tokens are independently minted opaque identities.
    assert actual.pop("unsubscribe_url").startswith("https://")
    assert expected.pop("unsubscribe_url").startswith("https://")
    assert actual == expected
    assert actual["first_name"] == "Synthetic"
    assert actual["donor_type"] == "Egg Donor"


@pytest.fixture
def queued_donor_email(db, test_org, test_user, owned_donor, monkeypatch):
    from app.services import workflow_email_provider

    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Synthetic donor email",
        subject="Hello {{first_name}}",
        body="<p>Reviewed content</p>",
        from_email="workflow@example.com",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()
    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: ("resend", {"from_email": "workflow@example.com"}),
    )
    queued = engine.adapter._action_send_email(
        db,
        {"template_id": str(template.id), "recipients": "donor"},
        owned_donor,
        uuid.uuid4(),
    )
    return db.get(Job, uuid.UUID(queued["job_ids"][0]))


@pytest.mark.asyncio
@pytest.mark.parametrize("subject_state", ["archived", "wrong_type", "foreign_org", "missing"])
async def test_queued_donor_workflow_email_rechecks_subject_before_provider_admission(
    db, test_user, owned_donor, monkeypatch, subject_state, queued_donor_email
):
    from app.jobs.handlers.email import process_workflow_email
    from app.services import workflow_email_provider

    job = queued_donor_email
    if subject_state == "archived":
        donor_service.archive_donor(db, owned_donor, test_user.id)
    elif subject_state == "wrong_type":
        job.payload = {**job.payload, "subject_type": "sperm_donor"}
    elif subject_state == "foreign_org":
        # Use a donor identifier from a different organization without moving its rows.
        from app.db.models import Organization

        other_org = Organization(name="Synthetic Other Org", slug=f"other-{uuid.uuid4()}")
        db.add(other_org)
        db.flush()
        other_donor = donor_service.create_donor(
            db,
            other_org.id,
            test_user.id,
            DonorCreate(donor_type="egg", full_name="Foreign Donor", email="foreign@example.com"),
        )
        job.payload = {**job.payload, "subject_id": str(other_donor.id)}
    else:
        job.payload = {**job.payload, "subject_id": str(uuid.uuid4())}
    db.commit()

    def reject_provider_access(**kwargs):
        pytest.fail("Unavailable donor must be rejected before provider resolution")

    monkeypatch.setattr(
        workflow_email_provider, "resolve_workflow_email_provider", reject_provider_access
    )
    await process_workflow_email(db, job)

    email_log = db.query(EmailLog).filter(EmailLog.job_id == job.id).one()
    assert email_log.status == "skipped"
    assert email_log.error == "donor_subject_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("prior_attempt", [False, True], ids=["unsent", "unknown_provider_outcome"])
async def test_donor_archived_after_outbox_admission_stops_send_without_losing_unknown_outcome(
    db, test_org, test_user, owned_donor, queued_donor_email, monkeypatch, prior_attempt
):
    from app.db.models import ResendSettings
    from app.jobs.handlers.email import process_workflow_email
    from app.services import email_delivery_dispatch, resend_settings_service
    from app.services.email_delivery_service import claim_due_deliveries
    from app.services.resend_transport import ResendSendResult

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_synthetic_test_key"),
            from_email="workflow@example.com",
            webhook_id=str(uuid.uuid4()),
        )
    )
    db.commit()
    await process_workflow_email(db, queued_donor_email)
    claim = claim_due_deliveries(
        db, worker_id="donor-test", lease_for=timedelta(minutes=2), limit=1
    )[0]

    if prior_attempt:

        async def unknown_send(**kwargs):
            return ResendSendResult(
                success=False,
                error="Synthetic timeout",
                error_type="timeout",
                retryable=True,
                ambiguous=True,
            )

        monkeypatch.setattr(email_delivery_dispatch.resend_transport, "send_email", unknown_send)
        attempted = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
        assert attempted.status == "retry_scheduled"
        claim = claim_due_deliveries(
            db,
            worker_id="donor-retry",
            now=attempted.run_at,
            lease_for=timedelta(minutes=2),
            limit=1,
        )[0]

    donor_service.archive_donor(db, owned_donor, test_user.id)

    async def reject_send(**kwargs):
        pytest.fail("Archived donor must not reach the provider")

    monkeypatch.setattr(email_delivery_dispatch.resend_transport, "send_email", reject_send)
    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    assert delivery.status == ("reconciliation_required" if prior_attempt else "cancelled")
    assert delivery.email_log.status == ("pending" if prior_attempt else "skipped")

    # Replaying the source job cannot relabel a durable outcome as a fresh skip.
    await process_workflow_email(db, queued_donor_email)
    db.refresh(delivery.email_log)
    assert delivery.email_log.status == ("pending" if prior_attempt else "skipped")


@pytest.mark.asyncio
async def test_personal_workflow_email_rechecks_donor_immediately_before_gmail(
    db, test_user, owned_donor, queued_donor_email, monkeypatch
):
    from app.jobs.handlers.email import process_workflow_email
    from app.services import gmail_service, workflow_email_provider

    queued_donor_email.payload = {
        **queued_donor_email.payload,
        "workflow_scope": "personal",
        "workflow_owner_id": str(test_user.id),
    }
    db.commit()

    def archive_during_preparation(**kwargs):
        donor_service.archive_donor(db, owned_donor, test_user.id)
        return "user_gmail", {"email": "workflow@example.com", "user_id": str(test_user.id)}

    async def reject_send(**kwargs):
        pytest.fail("Archived donor must not reach Gmail")

    monkeypatch.setattr(
        workflow_email_provider, "resolve_workflow_email_provider", archive_during_preparation
    )
    monkeypatch.setattr(gmail_service, "send_email", reject_send)
    await process_workflow_email(db, queued_donor_email)
    email_log = db.query(EmailLog).filter(EmailLog.job_id == queued_donor_email.id).one()
    assert email_log.status == "skipped"
    assert email_log.error == "donor_subject_unavailable"


def test_legacy_surrogate_outbox_without_source_job_remains_eligible(
    db, test_org, test_user, default_stage
):
    from app.core.encryption import hash_email
    from app.db.models import Surrogate
    from app.services.email_delivery_dispatch import _raise_if_source_ineligible
    from app.services.email_delivery_service import (
        DeliveryRoute,
        EmailSource,
        RenderedEmail,
        queue_rendered_email,
    )

    surrogate = Surrogate(
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Synthetic Legacy Surrogate",
        email="legacy@example.com",
        email_hash=hash_email("legacy@example.com"),
    )
    db.add(surrogate)
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=RenderedEmail(
            recipient_email="legacy@example.com",
            subject="Legacy approved email",
            html="<p>Reviewed legacy message</p>",
            text="Reviewed legacy message",
            from_email="workflow@example.com",
        ),
        idempotency_key=f"legacy-workflow/{uuid.uuid4()}",
        source=EmailSource(
            source_type="workflow_job",
            source_id=uuid.uuid4(),
            surrogate_id=surrogate.id,
        ),
        commit=False,
    )

    _raise_if_source_ineligible(db, queued.delivery)
