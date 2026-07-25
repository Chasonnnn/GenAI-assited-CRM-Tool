from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("delete_template_after_queue", [False, True])
async def test_queued_workflow_email_uses_the_template_selected_when_queued(
    db,
    test_org,
    test_user,
    default_stage,
    monkeypatch,
    delete_template_after_queue,
):
    from app.core.encryption import hash_email
    from app.db.enums import JobType
    from app.db.models import EmailLog, EmailTemplate, Job, Surrogate
    from app.services import workflow_email_provider
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter
    from app.utils.normalization import normalize_email
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Queued workflow snapshot",
        subject="Queued hello {{full_name}}",
        body="<p>Queued body for {{full_name}}</p>",
        from_email="Original Workflow <workflow-original@example.com>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        current_version=4,
    )
    recipient_email = normalize_email("queued-workflow@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Queued Recipient",
        email=recipient_email,
        email_hash=hash_email(recipient_email),
    )
    db.add_all([template, surrogate])
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
                "reply_to": "reply@example.com",
            },
        ),
    )
    adapter = DefaultWorkflowDomainAdapter()
    monkeypatch.setattr(
        adapter,
        "_resolve_email_variables",
        lambda _db, _entity: {"full_name": "Queued Recipient"},
    )
    queued = adapter._action_send_email(
        db=db,
        action={
            "action_type": "send_email",
            "template_id": str(template.id),
            "recipients": "surrogate",
        },
        entity=surrogate,
        event_id=uuid.uuid4(),
        workflow_scope="org",
        workflow_owner_id=None,
    )
    assert queued["success"] is True
    job = (
        db.query(Job)
        .filter(
            Job.id == uuid.UUID(queued["job_ids"][0]),
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .one()
    )

    template.subject = "Edited hello {{full_name}}"
    template.body = "<p>Edited body for {{full_name}}</p>"
    template.from_email = "Edited Workflow <workflow-edited@example.com>"
    template.current_version = 5
    db.commit()
    if delete_template_after_queue:
        db.delete(template)
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
    assert email_log.template_id == (None if delete_template_after_queue else template.id)
    assert email_log.email_template_snapshot["template_id"] == str(template.id)
    assert email_log.email_template_snapshot["template_version"] == 4
    assert email_log.subject == "Queued hello Queued Recipient"
    assert "Queued body for Queued Recipient" in email_log.body
    assert "Edited body" not in email_log.body
    assert email_log.from_email == "Original Workflow <workflow-original@example.com>"


@pytest.mark.asyncio
async def test_workflow_worker_rejects_snapshot_for_another_personal_owner(
    db,
    test_org,
    test_user,
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, Job
    from app.worker import process_workflow_email

    template_id = uuid.uuid4()
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template_id),
            "recipient_email": "wrong-owner@example.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(uuid.uuid4()),
            "email_template_snapshot": {
                "schema_version": 1,
                "organization_id": str(test_org.id),
                "template_id": str(template_id),
                "template_version": 3,
                "subject": "Owner-scoped subject",
                "body": "<p>Owner-scoped body</p>",
                "from_email": test_user.email,
                "scope": "personal",
                "owner_user_id": str(test_user.id),
                "system_key": None,
            },
        },
    )
    db.add(job)
    db.commit()

    with pytest.raises(Exception, match="does not match workflow owner"):
        await process_workflow_email(db, job)

    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_personal_workflow_fails_closed_when_gmail_sender_changed_after_queue(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, Job, UserIntegration
    from app.services import gmail_service
    from app.worker import process_workflow_email

    integration = UserIntegration(
        user_id=test_user.id,
        integration_type="gmail",
        access_token_encrypted="unused-provider-token",
        account_email="current-sender@example.com",
    )
    template_id = uuid.uuid4()
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template_id),
            "recipient_email": "recipient@example.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(test_user.id),
            "email_template_snapshot": {
                "schema_version": 1,
                "organization_id": str(test_org.id),
                "template_id": str(template_id),
                "template_version": 2,
                "subject": "Queued subject",
                "body": "<p>Queued body</p>",
                "from_email": "queued-sender@example.com",
                "scope": "personal",
                "owner_user_id": str(test_user.id),
                "system_key": None,
            },
        },
    )
    db.add_all([integration, job])
    db.commit()

    async def unexpected_send(**_kwargs):
        pytest.fail("Gmail must not be called after the queued sender changes")

    monkeypatch.setattr(gmail_service, "send_email", unexpected_send)

    with pytest.raises(
        Exception,
        match="Workflow Gmail sender changed after this email was queued",
    ):
        await process_workflow_email(db, job)

    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_org_workflow_queues_resend_outbox_without_provider_io(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.enums import EmailDeliveryStatus, EmailStatus, JobType
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job, ResendSettings
    from app.services import resend_transport
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
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted="write-only",
            from_email="care@example.com",
            from_name="Care Team",
            reply_to_email="reply@example.com",
        )
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
    db.refresh(job)

    assert job.payload["email_template_snapshot"]["from_email"] == ("Care Team <care@example.com>")

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
    assert email_log.email_template_snapshot["from_email"] == "Care Team <care@example.com>"
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
    from app.db.models import EmailDelivery, EmailLog, EmailTemplate, Job, UserIntegration
    from app.services import gmail_service
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
    db.add(
        UserIntegration(
            user_id=test_user.id,
            integration_type="gmail",
            access_token_encrypted="unused-provider-token",
            account_email="workflow-owner@example.com",
        )
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
    db.refresh(job)

    assert job.payload["email_template_snapshot"]["from_email"] == "workflow-owner@example.com"

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
