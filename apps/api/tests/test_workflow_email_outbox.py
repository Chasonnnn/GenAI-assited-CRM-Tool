from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_org_workflow_queues_resend_outbox_without_provider_io(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailDeliveryStatus, EmailStatus, JobType
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job
    from app.services import resend_transport, workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Durable workflow",
        subject="Hello {{full_name}}",
        body="<p>Welcome</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.flush()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **_kwargs: (
            "resend",
            {
                "api_key_encrypted": "write-only",
                "from_email": "care@example.com",
                "from_name": "Care Team",
                "reply_to": "reply@example.com",
            },
        ),
    )

    async def fail_direct_send(**_kwargs):
        raise AssertionError("org workflow must not call Resend in the workflow job")

    monkeypatch.setattr(resend_transport, "send_email", fail_direct_send)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@example.com",
            "variables": {"full_name": "Jordan Smith"},
            "workflow_scope": "org",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .one()
    )
    delivery = db.query(EmailDelivery).filter(EmailDelivery.email_log_id == email_log.id).one()

    assert email_log.status == EmailStatus.PENDING.value
    assert email_log.job_id == job.id
    assert email_log.actor_user_id == test_user.id
    assert email_log.from_email == "Care Team <care@example.com>"
    assert email_log.reply_to_email == "reply@example.com"
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.idempotency_key == f"workflow-email/{job.id}"


@pytest.mark.asyncio
async def test_suppressed_org_workflow_retry_reuses_one_skipped_occurrence(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailStatus, JobType
    from app.db.models import EmailDelivery, EmailLog, EmailSuppression, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Suppressed durable workflow",
        subject="Hello",
        body="<p>Welcome</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email="suppressed-workflow@example.com",
            reason="opt_out",
        )
    )
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "suppressed-workflow@example.com",
            "variables": {},
            "workflow_scope": "org",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add(job)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **_kwargs: (
            "resend",
            {
                "api_key_encrypted": "write-only",
                "from_email": "care@example.com",
                "from_name": "Care Team",
                "reply_to": None,
            },
        ),
    )

    await process_workflow_email(db, job)
    await process_workflow_email(db, job)

    messages = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .all()
    )
    assert len(messages) == 1
    assert messages[0].status == EmailStatus.SKIPPED.value
    assert messages[0].error == "suppressed"
    assert messages[0].idempotency_key == f"workflow-email/{job.id}"
    assert db.query(EmailDelivery).filter(EmailDelivery.email_log_id == messages[0].id).count() == 0


@pytest.mark.asyncio
async def test_org_workflow_configuration_failure_retry_reuses_diagnostic_record(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailStatus, JobType
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Recoverable workflow configuration",
        subject="Hello",
        body="<p>Welcome</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "config-retry@example.com",
            "variables": {},
            "workflow_scope": "org",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add_all([template, job])
    db.commit()

    def fail_provider_resolution(**_kwargs):
        raise workflow_email_provider.EmailProviderError("Resend sender is not configured")

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        fail_provider_resolution,
    )

    for _attempt in range(2):
        with pytest.raises(Exception, match="Resend sender is not configured"):
            await process_workflow_email(db, job)

    messages = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .all()
    )
    assert len(messages) == 1
    assert messages[0].status == EmailStatus.FAILED.value
    assert messages[0].error == "Resend sender is not configured"
    assert messages[0].idempotency_key == f"workflow-email-config/{job.id}"
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == f"workflow-email/{job.id}",
        )
        .count()
        == 0
    )
    assert db.query(EmailDelivery).filter(EmailDelivery.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_org_workflow_configuration_recovery_queues_exact_send_occurrence(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailDeliveryStatus, EmailStatus, JobType
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Recovered workflow configuration",
        subject="Hello",
        body="<p>Welcome</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "configured-after-retry@example.com",
            "variables": {},
            "workflow_scope": "org",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add_all([template, job])
    db.commit()

    configured = False

    def resolve_provider(**_kwargs):
        if not configured:
            raise workflow_email_provider.EmailProviderError("Resend sender is not configured")
        return (
            "resend",
            {
                "api_key_encrypted": "write-only",
                "from_email": "care@example.com",
                "from_name": "Care Team",
                "reply_to": "reply@example.com",
            },
        )

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        resolve_provider,
    )

    with pytest.raises(Exception, match="Resend sender is not configured"):
        await process_workflow_email(db, job)

    configured = True
    await process_workflow_email(db, job)
    await process_workflow_email(db, job)

    diagnostic = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == f"workflow-email-config/{job.id}",
        )
        .one()
    )
    queued_message = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == f"workflow-email/{job.id}",
        )
        .one()
    )
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == queued_message.id,
        )
        .one()
    )

    assert diagnostic.status == EmailStatus.FAILED.value
    assert diagnostic.purpose == "configuration_diagnostic"
    assert queued_message.status == EmailStatus.PENDING.value
    assert queued_message.provider == "resend"
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.idempotency_key == f"workflow-email/{job.id}"
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .count()
        == 2
    )


@pytest.mark.asyncio
async def test_suppressed_personal_workflow_retry_never_calls_gmail(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailStatus, JobType
    from app.db.models import EmailLog, EmailSuppression, EmailTemplate, Job
    from app.services import gmail_service, workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Suppressed personal workflow",
        subject="Hello",
        body="<p>Welcome</p>",
        scope="personal",
        owner_user_id=test_user.id,
        is_active=True,
    )
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "suppressed-personal@example.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add_all(
        [
            template,
            job,
            EmailSuppression(
                organization_id=test_org.id,
                email="suppressed-personal@example.com",
                reason="opt_out",
            ),
        ]
    )
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **_kwargs: ("user_gmail", {"user_id": test_user.id}),
    )

    async def fail_gmail_send(**_kwargs):
        raise AssertionError("suppressed personal workflow must not call Gmail")

    monkeypatch.setattr(gmail_service, "send_email", fail_gmail_send)

    await process_workflow_email(db, job)
    await process_workflow_email(db, job)

    message = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .one()
    )
    assert message.status == EmailStatus.SKIPPED.value
    assert message.error == "suppressed"
    assert message.idempotency_key == f"workflow-email/{job.id}"


@pytest.mark.asyncio
async def test_personal_workflow_stays_on_user_gmail(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import JobType
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job
    from app.services import gmail_service, workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Personal workflow",
        subject="Hello",
        body="<p>Welcome</p>",
        scope="personal",
        owner_user_id=test_user.id,
        is_active=True,
    )
    db.add(template)
    db.flush()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **_kwargs: (
            "user_gmail",
            {"user_id": test_user.id},
        ),
    )

    async def fake_gmail_send(**_kwargs):
        return {"success": True, "message_id": "gmail-message"}

    monkeypatch.setattr(gmail_service, "send_email", fake_gmail_send)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@example.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(test_user.id),
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.job_id == job.id,
        )
        .one()
    )
    assert email_log.external_id == "gmail-message"
    assert db.query(EmailDelivery).filter(EmailDelivery.email_log_id == email_log.id).count() == 0
