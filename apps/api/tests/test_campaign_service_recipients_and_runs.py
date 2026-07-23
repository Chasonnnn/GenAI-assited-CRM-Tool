from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread
from types import SimpleNamespace
from uuid import UUID, uuid4


from app.core.encryption import hash_email
from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus, JobStatus, JobType
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    EmailSuppression,
    EmailTemplate,
    Job,
    Surrogate,
)
from app.services import campaign_service
from app.utils.normalization import normalize_email


def _create_template(db, org_id: UUID) -> EmailTemplate:
    template = EmailTemplate(
        id=uuid4(),
        organization_id=org_id,
        name=f"Template-{uuid4().hex[:6]}",
        subject="Hello {{full_name}}",
        body="<p>Body</p>",
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template


def _create_campaign(
    db, org_id: UUID, user_id: UUID, template_id: UUID, *, status: str = CampaignStatus.DRAFT.value
) -> Campaign:
    campaign = Campaign(
        id=uuid4(),
        organization_id=org_id,
        name=f"Campaign-{uuid4().hex[:6]}",
        description="test",
        email_template_id=template_id,
        recipient_type="case",
        filter_criteria={},
        status=status,
        include_unsubscribed=False,
        created_by_user_id=user_id,
    )
    db.add(campaign)
    db.flush()
    return campaign


def _create_run(db, org_id: UUID, campaign_id: UUID, *, status: str = "running") -> CampaignRun:
    run = CampaignRun(
        id=uuid4(),
        organization_id=org_id,
        campaign_id=campaign_id,
        status=status,
        email_provider="smtp",
        started_at=datetime.now(timezone.utc),
        total_count=0,
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()
    return run


def _create_surrogate(
    db,
    *,
    org_id: UUID,
    user_id: UUID,
    stage_id: UUID,
    status_label: str,
    email: str | None,
    name: str,
) -> Surrogate:
    normalized = normalize_email(email) if email else None
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        stage_id=stage_id,
        status_label=status_label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name=name,
        email=normalized,
        email_hash=hash_email(normalized) if normalized else None,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _configure_resend_provider(db, org_id: UUID) -> None:
    from app.db.models import ResendSettings
    from app.services import resend_settings_service

    db.add(
        ResendSettings(
            organization_id=org_id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="campaigns@example.com",
            from_name="Campaign Team",
            verified_domain="example.com",
        )
    )
    db.flush()


def test_campaign_enqueue_send_now_and_scheduled(monkeypatch, db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign_now = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.DRAFT.value
    )
    campaign_later = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.DRAFT.value
    )
    campaign_later.scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)
    db.commit()

    monkeypatch.setattr(
        "app.services.email_provider_service.resolve_campaign_provider",
        lambda _db, _org_id: ("resend", {}),
    )

    message, run_id, scheduled_at = campaign_service.enqueue_campaign_send(
        db,
        org_id=test_org.id,
        campaign_id=campaign_now.id,
        user_id=test_user.id,
        send_now=True,
    )
    assert message == "Campaign queued for sending"
    assert run_id is not None
    assert scheduled_at is None

    queued_job = (
        db.query(Job)
        .filter(
            Job.job_type == JobType.CAMPAIGN_SEND.value,
            Job.payload["campaign_id"].astext == str(campaign_now.id),
        )
        .first()
    )
    assert queued_job is not None
    assert queued_job.status == JobStatus.PENDING.value

    message, run_id, scheduled_at = campaign_service.enqueue_campaign_send(
        db,
        org_id=test_org.id,
        campaign_id=campaign_later.id,
        user_id=test_user.id,
        send_now=False,
    )
    assert message == "Campaign scheduled"
    assert run_id is not None
    assert scheduled_at is not None


def test_execute_campaign_run_queues_versioned_immutable_recipient_delivery(
    db,
    test_org,
    test_user,
    default_stage,
):
    from app.db.models import EmailDelivery, EmailLog

    _configure_resend_provider(db, test_org.id)
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    run.email_provider = "resend"
    entity = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        email="initial-campaign@example.com",
        name="Initial Campaign Recipient",
    )
    db.commit()

    campaign_service.execute_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )

    recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run.id,
            CampaignRecipient.entity_id == entity.id,
        )
        .one()
    )
    assert recipient.send_revision == 0
    assert recipient.email_log_id is not None
    assert recipient.external_message_id is None

    email_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.id == recipient.email_log_id,
        )
        .one()
    )
    assert email_log.source_type == "campaign_recipient"
    assert email_log.source_id == recipient.id
    assert email_log.purpose == "marketing"
    assert email_log.idempotency_key == f"campaign-recipient/{recipient.id}/v0"

    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == email_log.id,
        )
        .one()
    )
    assert delivery.idempotency_key == f"campaign-recipient/{recipient.id}/v0"


def test_campaign_retry_queue_and_cancel(monkeypatch, db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="failed@example.com",
        recipient_name="Failed",
        status=CampaignRecipientStatus.FAILED.value,
    )
    db.add(recipient)
    db.flush()

    msg, run_id, job_id, failed_count = campaign_service.enqueue_campaign_retry_failed(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        user_id=test_user.id,
    )
    assert msg == "Retry queued"
    assert run_id == run.id
    assert job_id is not None
    assert failed_count == 1

    msg, _, existing_job_id, _ = campaign_service.enqueue_campaign_retry_failed(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        user_id=test_user.id,
    )
    assert msg == "Retry already queued"
    assert existing_job_id == job_id

    pending_job = db.query(Job).filter(Job.id == existing_job_id).first()
    assert pending_job is not None
    pending_job.status = JobStatus.PENDING.value
    db.add(pending_job)
    db.commit()

    from sqlalchemy import event as sqlalchemy_event

    statements: list[str] = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        cancelled = campaign_service.cancel_campaign(db, test_org.id, campaign.id)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)
    assert cancelled is True
    locking_selects = [statement for statement in statements if "for update" in statement]
    run_lock_index = next(
        index
        for index, statement in enumerate(locking_selects)
        if "from campaign_runs" in statement
    )
    campaign_lock_index = next(
        index for index, statement in enumerate(locking_selects) if "from campaigns" in statement
    )
    assert run_lock_index < campaign_lock_index
    assert campaign.status == CampaignStatus.CANCELLED.value
    assert pending_job.status == JobStatus.FAILED.value


def test_cancel_campaign_cancels_only_unleased_run_deliveries(
    db,
    test_org,
    test_user,
):
    from app.db.enums import EmailDeliveryStatus
    from app.db.models import EmailDelivery, EmailLog

    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    run.started_at = datetime.now(timezone.utc)
    older_run = _create_run(db, test_org.id, campaign.id, status="running")
    older_run.started_at = datetime.now(timezone.utc) - timedelta(days=1)

    def queue_recipient(target_run, email: str):
        recipient = CampaignRecipient(
            id=uuid4(),
            run_id=target_run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email=email,
            recipient_name=email,
            status=CampaignRecipientStatus.PENDING.value,
        )
        db.add(recipient)
        db.flush()
        idempotency_key = f"campaign-recipient/{recipient.id}/v0"
        email_log = EmailLog(
            id=uuid4(),
            organization_id=test_org.id,
            template_id=template.id,
            recipient_email=email,
            subject="Campaign cancellation",
            body="<p>Campaign cancellation</p>",
            status=EmailStatus.PENDING.value,
            idempotency_key=idempotency_key,
            source_type="campaign_recipient",
            source_id=recipient.id,
            purpose="marketing",
            provider="resend",
            provider_scope="organization",
            provider_account_id=f"organization:{test_org.id}",
        )
        db.add(email_log)
        db.flush()
        delivery = EmailDelivery(
            organization_id=test_org.id,
            email_log_id=email_log.id,
            provider="resend",
            provider_scope="organization",
            provider_account_id=f"organization:{test_org.id}",
            idempotency_key=idempotency_key,
            request_fingerprint=uuid4().hex * 2,
            status=EmailDeliveryStatus.PENDING.value,
        )
        db.add(delivery)
        db.flush()
        recipient.email_log_id = email_log.id
        return recipient, email_log, delivery

    pending_recipient, pending_log, pending_delivery = queue_recipient(
        run, "pending-cancel@example.com"
    )
    prior_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email=pending_recipient.recipient_email,
        subject="Prior immutable campaign message",
        body="<p>Prior immutable campaign message</p>",
        status=EmailStatus.PENDING.value,
        idempotency_key=f"campaign-recipient/{pending_recipient.id}/v-prior",
        source_type="campaign_recipient",
        source_id=pending_recipient.id,
        purpose="marketing",
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
    )
    db.add(prior_log)
    db.flush()
    prior_delivery = EmailDelivery(
        organization_id=test_org.id,
        email_log_id=prior_log.id,
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        idempotency_key=prior_log.idempotency_key,
        request_fingerprint=uuid4().hex * 2,
        status=EmailDeliveryStatus.PENDING.value,
    )
    db.add(prior_delivery)
    db.flush()

    retry_recipient, retry_log, retry_delivery = queue_recipient(run, "retry-cancel@example.com")
    retry_delivery.status = EmailDeliveryStatus.RETRY_SCHEDULED.value
    retry_delivery.run_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    leased_recipient, leased_log, leased_delivery = queue_recipient(
        run, "leased-cancel@example.com"
    )
    leased_delivery.status = EmailDeliveryStatus.LEASED.value
    leased_delivery.attempt_count = 1
    leased_delivery.lease_token = uuid4()
    leased_delivery.lease_owner = "worker-1"
    leased_delivery.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)

    older_recipient, older_log, older_delivery = queue_recipient(older_run, "older-run@example.com")
    db.commit()

    assert campaign_service.cancel_campaign(db, test_org.id, campaign.id) is True
    db.flush()

    for recipient, email_log, delivery in (
        (pending_recipient, pending_log, pending_delivery),
        (retry_recipient, retry_log, retry_delivery),
    ):
        assert delivery.status == EmailDeliveryStatus.CANCELLED.value
        assert delivery.completed_at is not None
        assert email_log.status == EmailStatus.SKIPPED.value
        assert email_log.error == "cancelled"
        assert recipient.status == CampaignRecipientStatus.SKIPPED.value
        assert recipient.skip_reason == "cancelled"

    assert prior_delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert prior_log.status == EmailStatus.SKIPPED.value
    assert prior_log.error == "cancelled"

    assert leased_delivery.status == EmailDeliveryStatus.LEASED.value
    assert leased_log.status == EmailStatus.PENDING.value
    assert leased_recipient.status == CampaignRecipientStatus.PENDING.value

    assert older_delivery.status == EmailDeliveryStatus.PENDING.value
    assert older_log.status == EmailStatus.PENDING.value
    assert older_recipient.status == CampaignRecipientStatus.PENDING.value

    assert (
        db.query(EmailDelivery)
        .join(EmailLog, EmailLog.id == EmailDelivery.email_log_id)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailLog.source_type == "campaign_recipient",
            EmailDelivery.status == EmailDeliveryStatus.CANCELLED.value,
        )
        .count()
        == 3
    )


def test_campaign_recipient_delivery_eligibility_is_tenant_scoped_and_current(
    db,
    test_org,
    test_user,
):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="eligible@example.com",
        recipient_name="Eligible",
        status=CampaignRecipientStatus.PENDING.value,
    )
    db.add(recipient)
    db.flush()

    assert (
        campaign_service.is_campaign_recipient_delivery_eligible(
            db,
            test_org.id,
            recipient.id,
        )
        is True
    )
    assert (
        campaign_service.is_campaign_recipient_delivery_eligible(
            db,
            uuid4(),
            recipient.id,
        )
        is False
    )

    campaign.status = CampaignStatus.CANCELLED.value
    db.flush()
    assert (
        campaign_service.is_campaign_recipient_delivery_eligible(
            db,
            test_org.id,
            recipient.id,
        )
        is False
    )


def test_campaign_recipient_status_sync_uses_email_log_foreign_key(
    db,
    test_org,
    test_user,
):
    from app.db.models import EmailLog
    from app.services import email_service

    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email="status-sync@example.com",
        subject="Status sync",
        body="<p>Status sync</p>",
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.flush()
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email=email_log.recipient_email,
        recipient_name="Status Sync",
        status=CampaignRecipientStatus.PENDING.value,
        email_log_id=email_log.id,
        external_message_id="provider-message-id",
    )
    db.add(recipient)
    db.commit()

    email_service.mark_email_sent(db, email_log)

    db.refresh(recipient)
    assert recipient.status == CampaignRecipientStatus.SENT.value
    assert recipient.external_message_id == "provider-message-id"


def test_campaign_delivery_success_projection_is_atomic_and_monotonic(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.db.models import EmailLog

    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    run.total_count = 1
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email="project-success@example.com",
        subject="Projection success",
        body="<p>Projection success</p>",
        status=EmailStatus.SENT.value,
    )
    db.add(email_log)
    db.flush()
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email=email_log.recipient_email,
        recipient_name="Projection Success",
        status=CampaignRecipientStatus.PENDING.value,
        email_log_id=email_log.id,
        error="old error",
        skip_reason="old skip",
    )
    db.add(recipient)
    db.flush()

    def fail_commit():
        raise AssertionError("commit=False must not commit")

    monkeypatch.setattr(db, "commit", fail_commit)
    from sqlalchemy import event as sqlalchemy_event

    statements: list[str] = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    sent_at = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    try:
        projected = campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=test_org.id,
            email_log_id=email_log.id,
            status=EmailStatus.SENT.value,
            provider_message_id="provider-success-id",
            occurred_at=sent_at,
            commit=False,
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)
    assert projected is True
    locking_selects = [statement for statement in statements if "for update" in statement]
    run_lock_index = next(
        index
        for index, statement in enumerate(locking_selects)
        if "from campaign_runs" in statement
    )
    campaign_lock_index = next(
        index for index, statement in enumerate(locking_selects) if "from campaigns" in statement
    )
    recipient_lock_index = next(
        index
        for index, statement in enumerate(locking_selects)
        if "from campaign_recipients" in statement
    )
    assert run_lock_index < campaign_lock_index < recipient_lock_index
    assert "organization_id" in locking_selects[run_lock_index]
    assert "organization_id" in locking_selects[campaign_lock_index]
    assert recipient.status == CampaignRecipientStatus.SENT.value
    assert recipient.sent_at == sent_at
    assert recipient.external_message_id == "provider-success-id"
    assert recipient.error is None
    assert recipient.skip_reason is None
    assert run.status == "completed"
    assert run.completed_at is not None
    assert run.sent_count == 1
    assert campaign.status == CampaignStatus.COMPLETED.value
    assert campaign.sent_count == 1

    recipient.status = CampaignRecipientStatus.DELIVERED.value
    db.flush()
    assert (
        campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=test_org.id,
            email_log_id=email_log.id,
            status=EmailStatus.SENT.value,
            provider_message_id="provider-success-id",
            occurred_at=sent_at + timedelta(minutes=1),
            commit=False,
        )
        is True
    )
    assert recipient.status == CampaignRecipientStatus.DELIVERED.value
    assert recipient.sent_at == sent_at


def test_campaign_delivery_failure_projection_is_tenant_scoped(
    db,
    test_org,
    test_user,
):
    from app.db.models import EmailLog

    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email="project-failure@example.com",
        subject="Projection failure",
        body="<p>Projection failure</p>",
        status=EmailStatus.FAILED.value,
    )
    db.add(email_log)
    db.flush()
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email=email_log.recipient_email,
        recipient_name="Projection Failure",
        status=CampaignRecipientStatus.PENDING.value,
        email_log_id=email_log.id,
    )
    db.add(recipient)
    db.flush()

    assert (
        campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=uuid4(),
            email_log_id=email_log.id,
            status=EmailStatus.FAILED.value,
            error="provider rejected",
            commit=False,
        )
        is False
    )
    assert recipient.status == CampaignRecipientStatus.PENDING.value

    assert (
        campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=test_org.id,
            email_log_id=email_log.id,
            status=EmailStatus.FAILED.value,
            error="provider rejected",
            commit=False,
        )
        is True
    )
    assert recipient.status == CampaignRecipientStatus.FAILED.value
    assert recipient.error == "provider rejected"
    assert recipient.skip_reason is None
    assert recipient.external_message_id is None


def test_campaign_delivery_skipped_projection_does_not_regress_delivered_recipient(
    db,
    test_org,
    test_user,
):
    from app.db.models import EmailLog

    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")

    suppressed_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email="project-skipped@example.com",
        subject="Projection skipped",
        body="<p>Projection skipped</p>",
        status=EmailStatus.SKIPPED.value,
    )
    delivered_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        template_id=template.id,
        recipient_email="already-delivered@example.com",
        subject="Already delivered",
        body="<p>Already delivered</p>",
        status=EmailStatus.SENT.value,
    )
    db.add_all([suppressed_log, delivered_log])
    db.flush()
    suppressed_recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email=suppressed_log.recipient_email,
        recipient_name="Projection Skipped",
        status=CampaignRecipientStatus.PENDING.value,
        email_log_id=suppressed_log.id,
    )
    delivered_recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email=delivered_log.recipient_email,
        recipient_name="Already Delivered",
        status=CampaignRecipientStatus.DELIVERED.value,
        email_log_id=delivered_log.id,
        external_message_id="delivered-provider-id",
        sent_at=datetime(2026, 7, 23, 11, 0, tzinfo=timezone.utc),
    )
    db.add_all([suppressed_recipient, delivered_recipient])
    db.flush()

    assert (
        campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=test_org.id,
            email_log_id=suppressed_log.id,
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
            commit=False,
        )
        is True
    )
    assert suppressed_recipient.status == CampaignRecipientStatus.SKIPPED.value
    assert suppressed_recipient.skip_reason == "suppressed"
    assert suppressed_recipient.error is None

    assert (
        campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=test_org.id,
            email_log_id=delivered_log.id,
            status=EmailStatus.SKIPPED.value,
            error="campaign cancelled",
            commit=False,
        )
        is True
    )
    assert delivered_recipient.status == CampaignRecipientStatus.DELIVERED.value
    assert delivered_recipient.external_message_id == "delivered-provider-id"


def test_concurrent_campaign_delivery_projections_finalize_consistently(db_engine):
    if db_engine.dialect.name != "postgresql":
        return

    from app.db.models import EmailLog, Organization
    from app.db.session import SessionLocal

    organization_id = uuid4()
    run_id = uuid4()
    email_log_ids = [uuid4(), uuid4()]
    setup = SessionLocal(bind=db_engine)
    try:
        organization = Organization(
            id=organization_id,
            name="Campaign Projection Concurrency",
            slug=f"campaign-projection-{uuid4().hex[:10]}",
        )
        template = EmailTemplate(
            id=uuid4(),
            organization_id=organization_id,
            name="Concurrent campaign projection",
            subject="Concurrent campaign",
            body="<p>Concurrent campaign</p>",
            is_active=True,
        )
        campaign = Campaign(
            id=uuid4(),
            organization_id=organization_id,
            name="Concurrent campaign projection",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={},
            status=CampaignStatus.SENDING.value,
        )
        run = CampaignRun(
            id=run_id,
            organization_id=organization_id,
            campaign_id=campaign.id,
            status="running",
            total_count=2,
            sent_count=0,
            delivered_count=0,
            failed_count=0,
            skipped_count=0,
            opened_count=0,
            clicked_count=0,
        )
        setup.add_all([organization, template, campaign, run])
        for index, email_log_id in enumerate(email_log_ids):
            email_log = EmailLog(
                id=email_log_id,
                organization_id=organization_id,
                template_id=template.id,
                recipient_email=f"concurrent-{index}@example.com",
                subject="Concurrent campaign",
                body="<p>Concurrent campaign</p>",
                status=EmailStatus.PENDING.value,
            )
            setup.add(email_log)
            setup.add(
                CampaignRecipient(
                    id=uuid4(),
                    run_id=run_id,
                    entity_type="case",
                    entity_id=uuid4(),
                    recipient_email=email_log.recipient_email,
                    status=CampaignRecipientStatus.PENDING.value,
                    email_log_id=email_log_id,
                )
            )
        setup.commit()
    finally:
        setup.close()

    ready = Barrier(2)
    errors: list[BaseException] = []

    def project(email_log_id, sequence: int) -> None:
        session = SessionLocal(bind=db_engine)
        try:
            ready.wait(timeout=5)
            assert (
                campaign_service.project_campaign_recipient_delivery(
                    session,
                    organization_id=organization_id,
                    email_log_id=email_log_id,
                    status=EmailStatus.SENT.value,
                    provider_message_id=f"resend-concurrent-{sequence}",
                    commit=True,
                )
                is True
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            session.close()

    threads = [
        Thread(target=project, args=(email_log_id, index))
        for index, email_log_id in enumerate(email_log_ids)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verification = SessionLocal(bind=db_engine)
    try:
        assert all(not thread.is_alive() for thread in threads)
        assert errors == []
        run = verification.get(CampaignRun, run_id)
        assert run is not None
        assert run.sent_count == 2
        assert run.status == "completed"
        assert run.completed_at is not None
        campaign = verification.get(Campaign, run.campaign_id)
        assert campaign is not None
        assert campaign.status == CampaignStatus.COMPLETED.value
    finally:
        verification.query(Organization).filter(Organization.id == organization_id).delete()
        verification.commit()
        verification.close()


def test_recompute_campaign_run_aggregates_finalizes_from_recipient_truth(
    db,
    test_org,
    test_user,
):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.SENDING.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    run.total_count = 4
    stale_completed_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    run.completed_at = stale_completed_at
    recipients = [
        CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="sent@example.com",
            status=CampaignRecipientStatus.SENT.value,
            opened_at=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        ),
        CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="delivered@example.com",
            status=CampaignRecipientStatus.DELIVERED.value,
            clicked_at=datetime(2026, 7, 23, 12, 1, tzinfo=timezone.utc),
        ),
        CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="failed@example.com",
            status=CampaignRecipientStatus.FAILED.value,
        ),
        CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="skipped@example.com",
            status=CampaignRecipientStatus.SKIPPED.value,
        ),
    ]
    db.add_all(recipients)
    db.flush()

    assert (
        campaign_service.recompute_campaign_run_aggregates(
            db,
            organization_id=test_org.id,
            run_id=run.id,
            commit=False,
        )
        is True
    )

    assert run.sent_count == 2
    assert run.delivered_count == 1
    assert run.failed_count == 1
    assert run.skipped_count == 1
    assert run.opened_count == 1
    assert run.clicked_count == 1
    assert run.status == "failed"
    assert run.completed_at is not None
    assert run.completed_at != stale_completed_at
    assert campaign.sent_count == 2
    assert campaign.delivered_count == 1
    assert campaign.failed_count == 1
    assert campaign.skipped_count == 1
    assert campaign.total_recipients == 4
    assert campaign.status == CampaignStatus.FAILED.value
    completed_at = run.completed_at

    assert (
        campaign_service.recompute_campaign_run_aggregates(
            db,
            organization_id=test_org.id,
            run_id=run.id,
            commit=False,
        )
        is True
    )
    assert run.completed_at == completed_at


def test_execute_campaign_run_with_duplicates_and_suppression(
    monkeypatch, db, test_org, test_user, default_stage
):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")

    recipients = [
        SimpleNamespace(
            id=uuid4(), email="alpha@example.com", full_name="Alpha", first_name="Alpha"
        ),
        SimpleNamespace(
            id=uuid4(),
            email="alpha@example.com",
            full_name="Duplicate Alpha",
            first_name="Duplicate",
        ),
        SimpleNamespace(
            id=uuid4(),
            email="suppressed@example.com",
            full_name="Suppressed",
            first_name="Suppressed",
        ),
        SimpleNamespace(id=uuid4(), email=None, full_name="No Email", first_name="No"),
    ]
    alpha_entity_id = recipients[0].id
    db.add(
        EmailSuppression(
            id=uuid4(),
            organization_id=test_org.id,
            email="suppressed@example.com",
            reason="opt_out",
        )
    )
    db.commit()

    class _FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def order_by(self, *args, **kwargs):
            return self

        def execution_options(self, **kwargs):
            return self

        def yield_per(self, _size):
            for row in self._rows:
                yield row

        def count(self):
            return len(self._rows)

    monkeypatch.setattr(
        campaign_service,
        "_build_recipient_query",
        lambda session, org_id, recipient_type, filters: _FakeQuery(recipients),
    )
    monkeypatch.setattr(campaign_service, "_load_existing_recipients", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        campaign_service,
        "_load_suppressed_emails",
        lambda *args, **kwargs: {"suppressed@example.com"},
    )
    monkeypatch.setattr(
        "app.services.org_service.get_org_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(slug="acme"),
    )
    monkeypatch.setattr(
        "app.services.org_service.get_org_portal_base_url",
        lambda *_args, **_kwargs: "https://acme.example.com",
    )
    monkeypatch.setattr(
        "app.services.email_composition_service.strip_legacy_unsubscribe_placeholders",
        lambda body: body,
    )
    monkeypatch.setattr(
        "app.services.email_composition_service.compose_template_email_html",
        lambda **kwargs: kwargs["rendered_body_html"],
    )
    monkeypatch.setattr(
        "app.services.tracking_service.generate_tracking_token", lambda: "tracking-token"
    )
    monkeypatch.setattr(
        "app.services.tracking_service.prepare_email_for_tracking",
        lambda body, token: f"{body}-{token}",
    )

    monkeypatch.setattr(
        "app.services.email_service.build_surrogate_template_variables",
        lambda db, entity: {"full_name": entity.full_name},
    )
    monkeypatch.setattr(
        "app.services.email_service.render_template",
        lambda subject, body, variables: (subject, body),
    )

    def _send_email(**kwargs):
        from app.db.models import EmailLog

        email_log = EmailLog(
            organization_id=kwargs["org_id"],
            template_id=kwargs["template_id"],
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            body=kwargs["body"],
            # Simulate a suppression added after the campaign's preload check
            # but before the durable queue performs its send-time check.
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
        )
        db.add(email_log)
        db.flush()
        return email_log, None

    monkeypatch.setattr("app.services.email_service.send_email", _send_email)

    result = campaign_service.execute_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )
    assert result["total_count"] == 4

    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run.id).all()
    assert any(r.recipient_email == "alpha@example.com" for r in recipients)
    assert any(r.skip_reason == "duplicate_email" for r in recipients)
    assert any(r.skip_reason == "suppressed" for r in recipients)
    raced_recipient = next(r for r in recipients if r.entity_id == alpha_entity_id)
    assert raced_recipient.status == CampaignRecipientStatus.SKIPPED.value
    assert raced_recipient.skip_reason == "suppressed"
    assert run.status == "completed"
    assert run.completed_at is not None
    assert campaign.status == CampaignStatus.COMPLETED.value


def test_execute_campaign_run_completed_short_circuit(db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.COMPLETED.value
    )
    run = _create_run(db, test_org.id, campaign.id, status="completed")
    run.sent_count = 2
    run.delivered_count = 1
    run.failed_count = 0
    run.skipped_count = 1
    run.total_count = 3
    db.commit()

    result = campaign_service.execute_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )
    assert result == {
        "sent_count": 2,
        "delivered_count": 1,
        "failed_count": 0,
        "skipped_count": 1,
        "total_count": 3,
    }


def test_retry_failed_campaign_run_updates_recipients(
    monkeypatch, db, test_org, test_user, default_stage
):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.FAILED.value
    )
    run = _create_run(db, test_org.id, campaign.id, status="failed")

    entity = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        email="retry@example.com",
        name="Retry Person",
    )
    failed_recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=entity.id,
        recipient_email="retry@example.com",
        recipient_name="Retry Person",
        status=CampaignRecipientStatus.FAILED.value,
        opened_at=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        clicked_at=datetime(2026, 7, 23, 12, 1, tzinfo=timezone.utc),
    )
    db.add(failed_recipient)
    db.commit()

    monkeypatch.setattr(campaign_service, "_load_suppressed_emails", lambda *args, **kwargs: set())
    monkeypatch.setattr(
        "app.services.org_service.get_org_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(slug="acme"),
    )
    monkeypatch.setattr(
        "app.services.org_service.get_org_portal_base_url",
        lambda *_args, **_kwargs: "https://acme.example.com",
    )
    monkeypatch.setattr(
        "app.services.email_composition_service.strip_legacy_unsubscribe_placeholders",
        lambda body: body,
    )
    monkeypatch.setattr(
        "app.services.email_composition_service.compose_template_email_html",
        lambda **kwargs: kwargs["rendered_body_html"],
    )
    monkeypatch.setattr(
        "app.services.tracking_service.generate_tracking_token", lambda: "retry-token"
    )
    monkeypatch.setattr(
        "app.services.tracking_service.prepare_email_for_tracking",
        lambda body, token: f"{body}-{token}",
    )
    monkeypatch.setattr(
        "app.services.email_service.build_surrogate_template_variables",
        lambda db, entity: {"full_name": entity.full_name},
    )
    monkeypatch.setattr(
        "app.services.email_service.render_template",
        lambda subject, body, variables: (subject, body),
    )

    def _send_email(**kwargs):
        from app.db.models import EmailLog

        email_log = EmailLog(
            organization_id=kwargs["org_id"],
            template_id=kwargs["template_id"],
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            body=kwargs["body"],
            status=EmailStatus.PENDING.value,
        )
        db.add(email_log)
        db.flush()
        return email_log, SimpleNamespace(id=uuid4())

    monkeypatch.setattr("app.services.email_service.send_email", _send_email)

    result = campaign_service.retry_failed_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )
    assert result["retried_count"] == 1
    db.refresh(failed_recipient)
    db.refresh(run)
    assert failed_recipient.status == CampaignRecipientStatus.PENDING.value
    assert run.opened_count == 1
    assert run.clicked_count == 1


def test_retry_failed_campaign_recipient_advances_revision_and_keeps_prior_message(
    db,
    test_org,
    test_user,
    default_stage,
):
    from app.db.enums import EmailDeliveryStatus
    from app.db.models import EmailDelivery, EmailLog
    from app.services import email_service

    _configure_resend_provider(db, test_org.id)
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db,
        test_org.id,
        test_user.id,
        template.id,
        status=CampaignStatus.FAILED.value,
    )
    run = _create_run(db, test_org.id, campaign.id, status="failed")
    run.email_provider = "resend"
    entity = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        email="immutable-retry@example.com",
        name="Immutable Retry",
    )
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=entity.id,
        recipient_email=entity.email,
        recipient_name=entity.full_name,
        status=CampaignRecipientStatus.FAILED.value,
        send_revision=0,
    )
    db.add(recipient)
    db.flush()

    prior_log, prior_delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=template.id,
        recipient_email=entity.email,
        subject="Prior campaign message",
        body="<p>Prior campaign message</p>",
        surrogate_id=entity.id,
        commit=False,
        idempotency_key=f"campaign-recipient/{recipient.id}/v0",
        source_type="campaign_recipient",
        source_id=recipient.id,
        purpose="marketing",
    )
    assert prior_delivery is not None
    prior_log.status = EmailStatus.FAILED.value
    prior_log.error = "provider rejected"
    prior_delivery.status = EmailDeliveryStatus.FAILED.value
    prior_delivery.completed_at = datetime.now(timezone.utc)
    recipient.email_log_id = prior_log.id
    db.commit()

    result = campaign_service.retry_failed_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )

    assert result["retried_count"] == 1
    db.refresh(recipient)
    assert recipient.status == CampaignRecipientStatus.PENDING.value
    assert recipient.send_revision == 1
    assert recipient.email_log_id != prior_log.id
    assert recipient.external_message_id is None

    messages = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "campaign_recipient",
            EmailLog.source_id == recipient.id,
        )
        .order_by(EmailLog.created_at, EmailLog.id)
        .all()
    )
    assert {message.id for message in messages} == {
        prior_log.id,
        recipient.email_log_id,
    }
    assert {message.idempotency_key for message in messages} == {
        f"campaign-recipient/{recipient.id}/v0",
        f"campaign-recipient/{recipient.id}/v1",
    }
    current_log = next(message for message in messages if message.id == recipient.email_log_id)
    assert current_log.purpose == "marketing"
    assert (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.email_log_id == current_log.id,
            EmailDelivery.idempotency_key == f"campaign-recipient/{recipient.id}/v1",
        )
        .one()
    )


def test_campaign_run_listing_helpers(db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(
        db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value
    )
    run = _create_run(db, test_org.id, campaign.id, status="running")
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="sample@example.com",
        recipient_name="Sample",
        status=CampaignRecipientStatus.PENDING.value,
    )
    db.add(recipient)
    db.commit()

    runs = campaign_service.list_campaign_runs(db, test_org.id, campaign.id)
    assert len(runs) == 1
    loaded_run = campaign_service.get_campaign_run(db, test_org.id, run.id)
    assert loaded_run is not None
    recipients = campaign_service.list_run_recipients(db, run.id)
    assert len(recipients) == 1
    latest = campaign_service.get_latest_run_for_campaign(db, campaign.id)
    assert latest is not None
