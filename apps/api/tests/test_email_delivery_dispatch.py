"""Provider-dispatch contract tests for the transactional email outbox."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.db.enums import (
    CampaignRecipientStatus,
    CampaignStatus,
    EmailDeliveryAttemptOutcome,
    EmailDeliveryStatus,
    EmailSuppressionPolicy,
    EmailStatus,
    SuppressionReason,
)
from app.db.models import (
    Attachment,
    Campaign,
    CampaignRecipient,
    CampaignRun,
    EmailDeliveryAttempt,
    EmailLogAttachment,
    EmailProviderAdmission,
    EmailSuppression,
    EmailTemplate,
    OrgInvite,
    Organization,
    ResendSettings,
)
from app.db.session import SessionLocal
from app.services import attachment_service, email_delivery_dispatch, resend_settings_service
from app.services.email_service import EmailAttachmentValidationError
from app.services.email_provider_admission_service import (
    reserve_provider_request_slot,
)
from app.services.email_delivery_service import (
    DeliveryRoute,
    DeliveryClaim,
    DeliveryLeaseLost,
    EmailSource,
    RenderedEmail,
    claim_due_deliveries,
    queue_rendered_email,
    record_delivery_success,
)
from app.services.resend_transport import ResendSendResult


def _rendered_email() -> RenderedEmail:
    return RenderedEmail(
        recipient_email="recipient@example.com",
        subject="A stored subject",
        html="<p>A stored body.</p>",
        text="A stored body.",
        from_email="Surrogacy Force <care@example.com>",
        reply_to_email="reply@example.com",
        headers={"X-Transactional": "true"},
        safe_tags=({"name": "message_kind", "value": "test"},),
    )


def _attachment(
    *,
    organization_id,
    filename: str = "guide.pdf",
    content_type: str = "application/pdf",
    size_bytes: int = 9,
    sha256: str = "29d1283686193dc1461a7deac4f53d9bc5402a28b95d854f69e94986756fd0a9",
) -> Attachment:
    attachment_id = uuid4()
    return Attachment(
        id=attachment_id,
        organization_id=organization_id,
        filename=filename,
        storage_key=f"{organization_id}/email-tests/{attachment_id}",
        content_type=content_type,
        file_size=size_bytes,
        checksum_sha256=sha256,
        scan_status="clean",
        quarantined=False,
    )


def _queue_and_claim(db, test_org, *, attachments=()):
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"dispatch/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        attachments=attachments,
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="dispatch-test",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    return queued, claim


def _queue_campaign_claim(db, test_org, test_user):
    template = EmailTemplate(
        id=uuid4(),
        organization_id=test_org.id,
        name=f"Dispatch projection {uuid4().hex[:6]}",
        subject="Campaign subject",
        body="<p>Campaign body</p>",
        is_active=True,
    )
    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name=f"Dispatch projection {uuid4().hex[:6]}",
        description="Dispatch projection test",
        email_template_id=template.id,
        recipient_type="case",
        filter_criteria={},
        status=CampaignStatus.SENDING.value,
        include_unsubscribed=False,
        created_by_user_id=test_user.id,
    )
    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="running",
        email_provider="resend",
        started_at=datetime.now(timezone.utc),
        total_count=1,
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
    )
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="recipient@example.com",
        recipient_name="Recipient",
        status=CampaignRecipientStatus.PENDING.value,
    )
    db.add_all([template, campaign, run, recipient])
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"campaign-projection/{recipient.id}",
        source=EmailSource(
            source_type="campaign_recipient",
            source_id=recipient.id,
            template_id=template.id,
            purpose="marketing",
        ),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    recipient.email_log_id = queued.email_log.id
    claim = claim_due_deliveries(
        db,
        worker_id="campaign-projection-worker",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    return queued, claim, campaign, recipient


def test_campaign_delivery_projection_locks_aggregate_before_delivery(
    db,
    test_org,
    test_user,
):
    from sqlalchemy import event as sqlalchemy_event

    _queued, claim, _campaign, _recipient = _queue_campaign_claim(
        db,
        test_org,
        test_user,
    )
    statements: list[str] = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        record_delivery_success(
            db,
            claim=claim,
            provider_message_id="resend-lock-order",
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)

    locking_selects = [statement for statement in statements if "for update" in statement]
    run_lock_index = next(
        index
        for index, statement in enumerate(locking_selects)
        if "from campaign_runs" in statement
    )
    campaign_lock_index = next(
        index for index, statement in enumerate(locking_selects) if "from campaigns" in statement
    )
    delivery_lock_index = next(
        index
        for index, statement in enumerate(locking_selects)
        if "from email_deliveries" in statement
    )
    assert run_lock_index < campaign_lock_index < delivery_lock_index


@pytest.fixture
def committed_dispatch_org(db_engine):
    session = SessionLocal(bind=db_engine)
    organization_id = uuid4()
    try:
        session.add(
            Organization(
                id=organization_id,
                name="Committed Dispatch Test",
                slug=f"committed-dispatch-{uuid4().hex[:10]}",
            )
        )
        session.commit()
    finally:
        session.close()

    yield organization_id

    cleanup = SessionLocal(bind=db_engine)
    try:
        cleanup.query(Organization).filter(Organization.id == organization_id).delete()
        cleanup.commit()
    finally:
        cleanup.close()


@pytest.mark.asyncio
async def test_dispatch_claim_sends_exact_stored_org_payload_without_open_db_transaction(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="ignored-by-immutable-payload@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    observed: dict[str, object] = {}

    async def fake_send_email(*, api_key, payload, idempotency_key):
        observed.update(
            api_key=api_key,
            payload=payload,
            idempotency_key=idempotency_key,
            db_transaction_open=db.in_transaction(),
        )
        return ResendSendResult(
            success=True,
            message_id="resend-dispatched-1",
            status_code=200,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivered = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert observed == {
        "api_key": "re_org_secret",
        "payload": {
            "from": "Surrogacy Force <care@example.com>",
            "to": ["recipient@example.com"],
            "subject": "A stored subject",
            "html": "<p>A stored body.</p>",
            "text": "A stored body.",
            "reply_to": "reply@example.com",
            "headers": {"X-Transactional": "true"},
            "tags": [
                {"name": "message_kind", "value": "test"},
                {"name": "organization_id", "value": str(test_org.id)},
                {"name": "email_log_id", "value": str(queued.email_log.id)},
            ],
        },
        "idempotency_key": queued.delivery.idempotency_key,
        "db_transaction_open": False,
    }
    assert delivered.status == EmailDeliveryStatus.SENT.value
    assert delivered.provider_message_id == "resend-dispatched-1"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SENT.value
    assert queued.email_log.external_id == "resend-dispatched-1"


@pytest.mark.asyncio
async def test_dispatch_claim_honors_suppression_added_after_queueing(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email="recipient@example.com",
            reason=SuppressionReason.COMPLAINT.value,
            source_type="provider_webhook",
        )
    )
    db.commit()
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "suppressed"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SKIPPED.value
    assert queued.email_log.error == "suppressed"
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    assert attempt.error_type == "suppressed"


@pytest.mark.asyncio
async def test_dispatch_claim_preserves_reviewed_opt_out_bypass_policy(
    monkeypatch,
    db,
    test_org,
):
    db.add_all(
        [
            ResendSettings(
                organization_id=test_org.id,
                email_provider="resend",
                api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
                from_email="care@example.com",
                webhook_id=str(uuid4()),
            ),
            EmailSuppression(
                organization_id=test_org.id,
                email="recipient@example.com",
                reason=SuppressionReason.OPT_OUT.value,
                source_type="manual",
            ),
        ]
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"reviewed-opt-out/{uuid4()}",
        source=EmailSource(
            source_type="test",
            source_id=uuid4(),
            purpose="marketing",
            suppression_policy=EmailSuppressionPolicy.ALLOW_OPT_OUT,
        ),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )

    assert queued.delivery is not None
    assert queued.email_log.suppression_policy == EmailSuppressionPolicy.ALLOW_OPT_OUT.value
    claim = claim_due_deliveries(
        db,
        worker_id="reviewed-opt-out-worker",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="resend-reviewed-opt-out")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is True
    assert delivery.status == EmailDeliveryStatus.SENT.value


@pytest.mark.asyncio
async def test_dispatch_claim_preserves_idempotency_and_provider_retry_after(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    sent_idempotency_key = None

    async def fake_send_email(*, api_key, payload, idempotency_key):
        del api_key, payload
        nonlocal sent_idempotency_key
        sent_idempotency_key = idempotency_key
        return ResendSendResult(
            success=False,
            error="Resend API error: 429",
            error_type="rate_limit_exceeded",
            status_code=429,
            retryable=True,
            retry_after_seconds=75,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )
    before_dispatch = datetime.now(timezone.utc)

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    after_dispatch = datetime.now(timezone.utc)
    assert sent_idempotency_key == queued.delivery.idempotency_key
    assert delivery.status == EmailDeliveryStatus.RETRY_SCHEDULED.value
    assert before_dispatch + timedelta(seconds=75) <= delivery.run_at
    assert delivery.run_at <= after_dispatch + timedelta(seconds=75)
    db.expire_all()
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.RETRYABLE_ERROR.value
    assert attempt.provider_http_status == 429
    assert attempt.retry_after_seconds == 75


@pytest.mark.asyncio
async def test_dispatch_claim_never_retries_through_a_changed_provider_credential(
    monkeypatch,
    db,
    test_org,
):
    resend_settings = ResendSettings(
        organization_id=test_org.id,
        email_provider="resend",
        api_key_encrypted=resend_settings_service.encrypt_api_key("re_original_secret"),
        from_email="care@example.com",
        webhook_id=str(uuid4()),
    )
    db.add(resend_settings)
    db.flush()
    queued, first_claim = _queue_and_claim(db, test_org)

    async def first_send(**_kwargs):
        return ResendSendResult(
            success=False,
            error="Connection timeout",
            error_type="timeout",
            retryable=True,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        first_send,
    )
    first_result = await email_delivery_dispatch.dispatch_claim(db, claim=first_claim)

    assert first_result.status == EmailDeliveryStatus.RETRY_SCHEDULED.value
    assert first_result.provider_credential_fingerprint is not None

    resend_settings.api_key_encrypted = resend_settings_service.encrypt_api_key(
        "re_different_team_secret"
    )
    db.commit()
    second_claim = claim_due_deliveries(
        db,
        worker_id="changed-credential-worker",
        now=first_result.run_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    provider_called = False

    async def second_send(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        second_send,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=second_claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.last_error_type == "provider_credential_changed"
    assert delivery.provider_credential_fingerprint == first_result.provider_credential_fingerprint
    db.expire_all()
    assert queued.email_log.status == EmailStatus.PENDING.value


@pytest.mark.asyncio
async def test_dispatch_claim_requires_reconciliation_for_ambiguous_success_response(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)

    async def fake_send_email(**_kwargs):
        return ResendSendResult(
            success=False,
            error="Resend API returned success without message id",
            error_type="invalid_success_response",
            status_code=202,
            ambiguous=True,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.last_error_type == "invalid_success_response"
    assert delivery.last_error == "Resend API returned success without message id"
    assert delivery.lease_token is None
    db.expire_all()
    assert queued.email_log.status == EmailStatus.PENDING.value
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    assert attempt.provider_http_status == 202


@pytest.mark.asyncio
async def test_dispatch_claim_retries_unknown_outcome_then_requires_reconciliation(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"ambiguous-timeout/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        max_attempts=2,
        commit=False,
    )
    first_claim = claim_due_deliveries(
        db,
        worker_id="ambiguous-timeout-worker-1",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]

    async def fake_send_email(**_kwargs):
        return ResendSendResult(
            success=False,
            error="Connection timeout",
            error_type="timeout",
            retryable=True,
            ambiguous=True,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    first_result = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=first_claim,
    )

    assert first_result.status == EmailDeliveryStatus.RETRY_SCHEDULED.value
    second_claim = claim_due_deliveries(
        db,
        worker_id="ambiguous-timeout-worker-2",
        now=first_result.run_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]

    final_result = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=second_claim,
    )

    assert final_result.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert final_result.last_error_type == "provider_outcome_unknown"
    assert "reconciliation" in (final_result.last_error or "").lower()
    db.expire_all()
    assert queued.email_log.status == EmailStatus.PENDING.value
    attempts = (
        db.query(EmailDeliveryAttempt)
        .filter(EmailDeliveryAttempt.delivery_id == final_result.id)
        .order_by(EmailDeliveryAttempt.attempt_number)
        .all()
    )
    assert [attempt.outcome for attempt in attempts] == [
        EmailDeliveryAttemptOutcome.RETRYABLE_ERROR.value,
        EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value,
    ]


@pytest.mark.asyncio
async def test_dispatch_due_batch_starts_all_claimed_network_calls_concurrently(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    claims = [
        DeliveryClaim(
            delivery_id=uuid4(),
            organization_id=uuid4(),
            email_log_id=uuid4(),
            lease_token=uuid4(),
            lease_owner="batch-worker",
            attempt_number=1,
            lease_expires_at=now + timedelta(minutes=2),
        )
        for _ in range(3)
    ]
    claim_calls: list[dict[str, object]] = []

    def fake_claim_due_deliveries(db, **kwargs):
        claim_calls.append({"db": db, **kwargs})
        return claims

    monkeypatch.setattr(
        email_delivery_dispatch,
        "claim_due_deliveries",
        fake_claim_due_deliveries,
    )
    active = 0
    max_active = 0
    all_started = asyncio.Event()

    async def fake_dispatch_claim(db, *, claim):
        del db, claim
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        if active == len(claims):
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=1)
        active -= 1
        return SimpleNamespace(status=EmailDeliveryStatus.SENT.value)

    monkeypatch.setattr(
        email_delivery_dispatch,
        "dispatch_claim",
        fake_dispatch_claim,
    )

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, traceback):
            return False

    summary = await email_delivery_dispatch.dispatch_due_delivery_batch(
        session_factory=SessionContext,
        worker_id="batch-worker",
        limit=3,
        lease_for=timedelta(minutes=2),
    )

    assert max_active == 3
    assert summary.claimed == 3
    assert summary.sent == 3
    assert summary.unexpected_errors == 0
    assert len(claim_calls) == 1
    assert claim_calls[0]["limit"] == 3


@pytest.mark.asyncio
async def test_dispatch_claim_fails_terminally_before_sending_partial_attachments(
    monkeypatch,
    caplog,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)

    def fail_attachment_load(*_args, **_kwargs):
        raise EmailAttachmentValidationError(
            "Attachment 'recipient@example.com-medical.pdf' is not clean"
        )

    monkeypatch.setattr(
        email_delivery_dispatch.email_service,
        "load_email_log_provider_attachments",
        fail_attachment_load,
    )
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.last_error_type == "payload_error"
    assert delivery.last_error == "Stored email attachments could not be prepared"
    assert "recipient@example.com" not in delivery.last_error
    assert "recipient@example.com" not in caplog.text
    db.expire_all()
    assert queued.email_log.status == EmailStatus.FAILED.value


@pytest.mark.asyncio
async def test_dispatch_claim_fails_closed_when_attachment_bytes_do_not_match_snapshot(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    attachment = _attachment(organization_id=test_org.id)
    db.add(attachment)
    db.flush()
    queued, claim = _queue_and_claim(db, test_org, attachments=[attachment])
    monkeypatch.setattr(
        attachment_service,
        "load_file_bytes",
        lambda _storage_key: b"tampered!",
    )
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.last_error_type == "payload_error"
    assert delivery.last_error == "Stored email attachments could not be prepared"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.FAILED.value


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_link",
        "filename",
        "content_type",
        "size_bytes",
        "sha256",
    ],
)
@pytest.mark.asyncio
async def test_dispatch_claim_fails_closed_when_attachment_link_or_metadata_changes(
    mutation,
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    attachment = _attachment(organization_id=test_org.id)
    db.add(attachment)
    db.flush()
    queued, claim = _queue_and_claim(db, test_org, attachments=[attachment])

    if mutation == "missing_link":
        (
            db.query(EmailLogAttachment)
            .filter(
                EmailLogAttachment.email_log_id == queued.email_log.id,
                EmailLogAttachment.attachment_id == attachment.id,
            )
            .delete(synchronize_session=False)
        )
    elif mutation == "filename":
        attachment.filename = "changed.pdf"
    elif mutation == "content_type":
        attachment.content_type = "application/octet-stream"
    elif mutation == "size_bytes":
        attachment.file_size = 10
    elif mutation == "sha256":
        attachment.checksum_sha256 = "0" * 64
    db.flush()
    monkeypatch.setattr(
        attachment_service,
        "load_file_bytes",
        lambda _storage_key: b"pdf-bytes",
    )
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.last_error_type == "payload_error"
    assert delivery.last_error == "Stored email attachments could not be prepared"


@pytest.mark.asyncio
async def test_dispatch_claim_fails_closed_when_attachment_file_is_unavailable(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    attachment = _attachment(organization_id=test_org.id)
    db.add(attachment)
    db.flush()
    _queued, claim = _queue_and_claim(db, test_org, attachments=[attachment])

    def missing_file(_storage_key):
        raise FileNotFoundError("test storage object is missing")

    monkeypatch.setattr(attachment_service, "load_file_bytes", missing_file)
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.last_error_type == "payload_error"
    assert delivery.last_error == "Stored email attachments could not be prepared"


@pytest.mark.asyncio
async def test_dispatch_claim_rejects_coordinated_attachment_manifest_mutation(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    attachment = _attachment(organization_id=test_org.id)
    db.add(attachment)
    db.flush()
    queued, claim = _queue_and_claim(db, test_org, attachments=[attachment])
    attachment.filename = "coordinated-change.pdf"
    queued.email_log.attachment_manifest = [
        {
            **queued.email_log.attachment_manifest[0],
            "filename": "coordinated-change.pdf",
        }
    ]
    db.flush()
    monkeypatch.setattr(
        attachment_service,
        "load_file_bytes",
        lambda _storage_key: b"pdf-bytes",
    )
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.last_error_type == "payload_error"
    assert delivery.last_error == "Stored email payload fingerprint does not match"


@pytest.mark.asyncio
async def test_dispatch_claim_encodes_all_linked_attachments_for_resend(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    pdf_attachment = _attachment(organization_id=test_org.id)
    text_attachment = _attachment(
        organization_id=test_org.id,
        filename="first.txt",
        content_type="text/plain",
        size_bytes=11,
        sha256="e811e1ebb5f584ba17b364d7bac66bad0de3e0e223757e48c386de0e31ac63db",
    )
    db.add_all([pdf_attachment, text_attachment])
    db.flush()
    _queued, claim = _queue_and_claim(
        db,
        test_org,
        attachments=[text_attachment, pdf_attachment],
    )
    content_by_storage_key = {
        text_attachment.storage_key: b"first-bytes",
        pdf_attachment.storage_key: b"pdf-bytes",
    }
    monkeypatch.setattr(
        attachment_service,
        "load_file_bytes",
        lambda storage_key: content_by_storage_key[storage_key],
    )
    provider_payload = None

    async def fake_send_email(*, api_key, payload, idempotency_key):
        del api_key, idempotency_key
        nonlocal provider_payload
        provider_payload = payload
        return ResendSendResult(success=True, message_id="resend-with-attachment")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert delivery.status == EmailDeliveryStatus.SENT.value
    assert provider_payload["attachments"] == [
        {
            "filename": "first.txt",
            "content": "Zmlyc3QtYnl0ZXM=",
            "content_type": "text/plain",
        },
        {
            "filename": "guide.pdf",
            "content": "cGRmLWJ5dGVz",
            "content_type": "application/pdf",
        },
    ]


@pytest.mark.asyncio
async def test_dispatch_claim_resolves_platform_credentials_from_platform_identity(
    monkeypatch,
    db,
    test_org,
):
    monkeypatch.setattr(
        settings,
        "PLATFORM_RESEND_API_KEY",
        SecretStr("re_platform_secret"),
    )
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.PLATFORM_RESEND,
        provider_account_id="platform:default",
        rendered_email=_rendered_email(),
        idempotency_key=f"platform-dispatch/{uuid4()}",
        source=EmailSource(source_type="platform_invite", source_id=uuid4()),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="dispatch-test",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    observed_api_key = None

    async def fake_send_email(*, api_key, payload, idempotency_key):
        del payload, idempotency_key
        nonlocal observed_api_key
        observed_api_key = api_key
        return ResendSendResult(success=True, message_id="resend-platform-1")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert observed_api_key == "re_platform_secret"
    assert delivery.status == EmailDeliveryStatus.SENT.value
    assert delivery.email_log_id == queued.email_log.id


@pytest.mark.asyncio
async def test_dispatch_claim_never_starts_provider_io_for_an_expired_lease(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    expired_claim_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"expired-dispatch/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=expired_claim_time - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="expired-worker",
        now=expired_claim_time,
        lease_for=timedelta(minutes=1),
        limit=1,
    )[0]
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    with pytest.raises(DeliveryLeaseLost, match="expired"):
        await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False


@pytest.mark.asyncio
async def test_dispatch_claim_commits_provider_admission_before_wait_and_network(
    monkeypatch,
    db_engine,
    committed_dispatch_org,
):
    organization_id = committed_dispatch_org
    credential_fingerprint = hashlib.sha256(b"re_org_secret").hexdigest()
    provider_account_id = f"credential:{credential_fingerprint}"
    db = SessionLocal(bind=db_engine)
    try:
        db.add(
            ResendSettings(
                organization_id=organization_id,
                email_provider="resend",
                api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
                from_email="care@example.com",
                webhook_id=str(uuid4()),
            )
        )
        db.commit()
        _queued, claim = _queue_and_claim(
            db,
            SimpleNamespace(id=organization_id),
        )
        future_base = datetime.now(timezone.utc) + timedelta(seconds=1)
        seed_session = SessionLocal(bind=db_engine)
        try:
            first = reserve_provider_request_slot(
                seed_session,
                provider="resend",
                provider_account_id=provider_account_id,
                requests_per_second=10,
                now=future_base,
            )
            assert first.send_at == future_base
        finally:
            seed_session.close()

        observed: dict[str, object] = {}

        async def fake_sleep(delay_seconds: float) -> None:
            observed["delay_seconds"] = delay_seconds
            observed["transaction_open_during_wait"] = db.in_transaction()
            verification = SessionLocal(bind=db_engine)
            try:
                next_slot = reserve_provider_request_slot(
                    verification,
                    provider="resend",
                    provider_account_id=provider_account_id,
                    requests_per_second=10,
                    now=future_base,
                )
                observed["next_committed_slot"] = next_slot.send_at
            finally:
                verification.close()

        async def fake_send_email(**_kwargs):
            observed["transaction_open_during_provider_io"] = db.in_transaction()
            return ResendSendResult(success=True, message_id="resend-admitted")

        monkeypatch.setattr(
            email_delivery_dispatch.resend_transport,
            "send_email",
            fake_send_email,
        )

        delivery = await email_delivery_dispatch.dispatch_claim(
            db,
            claim=claim,
            sleeper=fake_sleep,
        )
    finally:
        db.close()
        cleanup = SessionLocal(bind=db_engine)
        try:
            cleanup.query(EmailProviderAdmission).filter(
                EmailProviderAdmission.provider == "resend",
                EmailProviderAdmission.provider_account_id == provider_account_id,
            ).delete()
            cleanup.commit()
        finally:
            cleanup.close()

    assert delivery.status == EmailDeliveryStatus.SENT.value
    assert observed["delay_seconds"] > 0
    assert observed["transaction_open_during_wait"] is False
    assert observed["transaction_open_during_provider_io"] is False
    assert observed["next_committed_slot"] == future_base + timedelta(milliseconds=200)


@pytest.mark.asyncio
async def test_dispatch_claim_scopes_admission_to_the_bound_provider_credential(
    monkeypatch,
    db,
    test_org,
):
    api_key = "re_shared_org_secret"
    credential_scope = f"credential:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()}"
    synthetic_org_scope = f"organization:{test_org.id}"
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key(api_key),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    _queued, claim = _queue_and_claim(db, test_org)

    async def fake_send_email(**_kwargs):
        return ResendSendResult(success=True, message_id="resend-credential-scope")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert delivery.status == EmailDeliveryStatus.SENT.value
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == credential_scope,
        )
        .count()
        == 1
    )
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == synthetic_org_scope,
        )
        .count()
        == 0
    )
    db.query(EmailProviderAdmission).filter(
        EmailProviderAdmission.provider == "resend",
        EmailProviderAdmission.provider_account_id.in_([credential_scope, synthetic_org_scope]),
    ).delete(synchronize_session=False)
    db.commit()


@pytest.mark.asyncio
async def test_dispatch_claim_rechecks_suppression_after_provider_admission_wait(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    provider_called = False

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(
            send_at=datetime.now(timezone.utc) + timedelta(seconds=1)
        ),
    )

    async def add_suppression_during_wait(_delay_seconds: float) -> None:
        db.add(
            EmailSuppression(
                organization_id=test_org.id,
                email=queued.email_log.recipient_email,
                reason=SuppressionReason.COMPLAINT.value,
                source_type="provider_webhook",
            )
        )
        db.commit()

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=add_suppression_during_wait,
    )

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "suppressed"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_dispatch_claim_rechecks_lease_ownership_after_provider_admission_wait(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    provider_called = False

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(
            send_at=datetime.now(timezone.utc) + timedelta(seconds=1)
        ),
    )

    async def replace_lease_during_wait(_delay_seconds: float) -> None:
        queued.delivery.lease_token = uuid4()
        db.commit()

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    with pytest.raises(DeliveryLeaseLost, match="no longer owned"):
        await email_delivery_dispatch.dispatch_claim(
            db,
            claim=claim,
            sleeper=replace_lease_during_wait,
        )

    assert provider_called is False


@pytest.mark.asyncio
async def test_dispatch_claim_rechecks_campaign_eligibility_after_provider_admission_wait(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    queued, claim, campaign, recipient = _queue_campaign_claim(
        db,
        test_org,
        test_user,
    )
    provider_called = False

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(
            send_at=datetime.now(timezone.utc) + timedelta(seconds=1)
        ),
    )

    async def cancel_campaign_during_wait(_delay_seconds: float) -> None:
        campaign.status = CampaignStatus.CANCELLED.value
        db.commit()

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=cancel_campaign_during_wait,
    )

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "campaign_ineligible"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SKIPPED.value
    assert recipient.status == CampaignRecipientStatus.SKIPPED.value
    assert recipient.skip_reason == "campaign_ineligible"


@pytest.mark.asyncio
async def test_dispatch_claim_rechecks_invite_eligibility_after_provider_admission_wait(
    monkeypatch,
    db,
    test_org,
):
    monkeypatch.setattr(
        settings,
        "PLATFORM_RESEND_API_KEY",
        SecretStr("re_platform_secret"),
    )
    invite = OrgInvite(
        id=uuid4(),
        organization_id=test_org.id,
        email="recipient@example.com",
        role="case_manager",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        send_revision=0,
    )
    db.add(invite)
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.PLATFORM_RESEND,
        provider_account_id="platform:default",
        rendered_email=_rendered_email(),
        idempotency_key=f"invite:{invite.id}:v0",
        source=EmailSource(
            source_type="org_invite",
            source_id=invite.id,
            purpose="transactional",
        ),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="invite-dispatch-worker",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    provider_called = False

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(
            send_at=datetime.now(timezone.utc) + timedelta(seconds=1)
        ),
    )

    async def revoke_invite_during_wait(_delay_seconds: float) -> None:
        invite.revoked_at = datetime.now(timezone.utc)
        db.commit()

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=revoke_invite_during_wait,
    )

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "invite_ineligible"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_dispatch_claim_rechecks_idempotency_window_after_admission_wait(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued, claim = _queue_and_claim(db, test_org)
    base_time = datetime.now(timezone.utc)
    queued.delivery.idempotency_expires_at = base_time + timedelta(seconds=1)
    db.commit()

    class MutableDateTime(datetime):
        current = base_time

        @classmethod
        def now(cls, tz=None):
            del tz
            return cls.current

    monkeypatch.setattr(email_delivery_dispatch, "datetime", MutableDateTime)
    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *_args, **_kwargs: SimpleNamespace(send_at=base_time + timedelta(milliseconds=500)),
    )
    provider_called = False

    async def fake_sleep(_delay_seconds: float) -> None:
        MutableDateTime.current = base_time + timedelta(seconds=2)

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=fake_sleep,
    )

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.last_error_type == "idempotency_window_expired"
    assert delivery.lease_token is None
    db.expire_all()
    assert queued.email_log.status == EmailStatus.PENDING.value


@pytest.mark.asyncio
async def test_dispatch_claim_defers_when_provider_slot_outlives_the_lease(
    monkeypatch,
    db,
    test_org,
):
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"short-admission-lease/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="short-lease-worker",
        lease_for=timedelta(seconds=60),
        limit=1,
    )[0]
    provider_called = False
    sleeper_called = False

    async def fake_sleep(_delay_seconds: float) -> None:
        nonlocal sleeper_called
        sleeper_called = True

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(
        db,
        claim=claim,
        sleeper=fake_sleep,
    )

    assert provider_called is False
    assert sleeper_called is False
    assert delivery.status == EmailDeliveryStatus.RETRY_SCHEDULED.value
    assert delivery.last_error_type == "provider_admission_deferred"
    assert delivery.lease_token is None
    db.expire_all()
    assert queued.email_log.status == EmailStatus.PENDING.value


@pytest.mark.asyncio
async def test_dispatch_claim_cancels_a_campaign_recipient_that_is_no_longer_eligible(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    template = EmailTemplate(
        id=uuid4(),
        organization_id=test_org.id,
        name=f"Dispatch campaign {uuid4().hex[:6]}",
        subject="Campaign subject",
        body="<p>Campaign body</p>",
        is_active=True,
    )
    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name=f"Dispatch campaign {uuid4().hex[:6]}",
        description="Dispatch eligibility test",
        email_template_id=template.id,
        recipient_type="case",
        filter_criteria={},
        status=CampaignStatus.SENDING.value,
        include_unsubscribed=False,
        created_by_user_id=test_user.id,
    )
    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="running",
        email_provider="resend",
        started_at=datetime.now(timezone.utc),
        total_count=1,
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
    )
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="recipient@example.com",
        recipient_name="Recipient",
        status=CampaignRecipientStatus.PENDING.value,
    )
    db.add_all([template, campaign, run, recipient])
    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"campaign-dispatch/{recipient.id}",
        source=EmailSource(
            source_type="campaign_recipient",
            source_id=recipient.id,
            template_id=template.id,
            purpose="marketing",
        ),
        schedule_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        commit=False,
    )
    recipient.email_log_id = queued.email_log.id
    claim = claim_due_deliveries(
        db,
        worker_id="campaign-dispatch-worker",
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    campaign.status = CampaignStatus.CANCELLED.value
    db.commit()
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True
        return ResendSendResult(success=True, message_id="must-not-send")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "campaign_ineligible"
    db.expire_all()
    assert queued.email_log.status == EmailStatus.SKIPPED.value
    assert recipient.status == CampaignRecipientStatus.SKIPPED.value
    assert recipient.skip_reason == "campaign_ineligible"


@pytest.mark.asyncio
async def test_dispatch_success_atomically_projects_the_provider_id_to_campaign(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    queued, claim, _campaign, recipient = _queue_campaign_claim(
        db,
        test_org,
        test_user,
    )

    async def fake_send_email(**_kwargs):
        return ResendSendResult(success=True, message_id="resend-campaign-provider-id")

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert delivery.status == EmailDeliveryStatus.SENT.value
    db.expire_all()
    assert recipient.status == CampaignRecipientStatus.SENT.value
    assert recipient.email_log_id == queued.email_log.id
    assert recipient.external_message_id == "resend-campaign-provider-id"
    assert recipient.external_message_id != str(queued.email_log.id)


@pytest.mark.asyncio
async def test_dispatch_terminal_failure_atomically_projects_to_campaign(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    _queued, claim, _campaign, recipient = _queue_campaign_claim(
        db,
        test_org,
        test_user,
    )

    async def fake_send_email(**_kwargs):
        return ResendSendResult(
            success=False,
            error="Resend API error: 422",
            error_type="validation_error",
            status_code=422,
            retryable=False,
        )

    monkeypatch.setattr(
        email_delivery_dispatch.resend_transport,
        "send_email",
        fake_send_email,
    )

    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert delivery.status == EmailDeliveryStatus.FAILED.value
    db.expire_all()
    assert recipient.status == CampaignRecipientStatus.FAILED.value
    assert recipient.external_message_id is None
    assert recipient.error == "Resend API error: 422"
