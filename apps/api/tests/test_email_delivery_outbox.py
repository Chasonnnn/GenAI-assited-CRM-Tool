"""Public-contract tests for the transactional email delivery outbox."""

from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.db.enums import (
    EmailDeliveryAttemptOutcome,
    EmailDeliveryStatus,
    EmailSuppressionPolicy,
    EmailStatus,
    SuppressionReason,
)
from app.db.models import (
    Attachment,
    EmailDelivery,
    EmailDeliveryAttempt,
    EmailLog,
    EmailLogAttachment,
    EmailReconciliationCase,
    EmailSuppression,
    Organization,
)
from app.db.session import SessionLocal
from app.services.email_delivery_service import (
    DeliveryRoute,
    DeliveryLeaseLost,
    EmailDeliveryConflict,
    EmailSource,
    RenderedEmail,
    claim_due_deliveries,
    queue_rendered_email,
    record_delivery_failure,
    record_delivery_success,
    renew_delivery_lease,
)


def _rendered_email(*, subject: str = "Your next step") -> RenderedEmail:
    return RenderedEmail(
        recipient_email="recipient@example.com",
        subject=subject,
        html="<p>Welcome to Surrogacy Force.</p>",
        text="Welcome to Surrogacy Force.",
        from_email="Surrogacy Force <care@example.com>",
        reply_to_email="support@example.com",
        headers={"X-Transactional": "true"},
        safe_tags=({"name": "message_kind", "value": "test"},),
    )


def _attachment(
    *,
    organization_id,
    filename: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
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


@pytest.fixture
def committed_outbox_org(db_engine):
    setup = SessionLocal(bind=db_engine)
    org_id = uuid4()
    try:
        setup.add(
            Organization(
                id=org_id,
                name="Committed Outbox Test",
                slug=f"committed-outbox-{uuid4().hex[:10]}",
            )
        )
        setup.commit()
    finally:
        setup.close()

    yield org_id

    cleanup = SessionLocal(bind=db_engine)
    try:
        cleanup.query(Organization).filter(Organization.id == org_id).delete()
        cleanup.commit()
    finally:
        cleanup.close()


def test_queue_rendered_email_deduplicates_an_exact_business_operation(db, test_org):
    source = EmailSource(source_type="test", source_id=uuid4())

    first = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"test-delivery/{uuid4()}",
        source=source,
        commit=False,
    )
    duplicate = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=first.delivery.idempotency_key,
        source=source,
        commit=False,
    )

    assert duplicate.created is False
    assert duplicate.email_log.id == first.email_log.id
    assert duplicate.delivery.id == first.delivery.id
    assert duplicate.email_log.content_fingerprint == first.email_log.content_fingerprint
    assert duplicate.delivery.request_fingerprint == first.delivery.request_fingerprint
    assert duplicate.email_log.subject == "Your next step"
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == first.delivery.idempotency_key,
        )
        .count()
        == 1
    )
    assert (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.organization_id == test_org.id,
            EmailDelivery.idempotency_key == first.delivery.idempotency_key,
        )
        .count()
        == 1
    )


def test_queue_rendered_email_snapshots_ordered_attachment_manifest_before_deduplication(
    db,
    test_org,
):
    first = _attachment(
        organization_id=test_org.id,
        filename="first.txt",
        content_type="text/plain",
        size_bytes=11,
        sha256="e811e1ebb5f584ba17b364d7bac66bad0de3e0e223757e48c386de0e31ac63db",
    )
    second = _attachment(
        organization_id=test_org.id,
        filename="second.txt",
        content_type="text/plain",
        size_bytes=12,
        sha256="d7b0717202604f4941983807ee1dbed5cab2458921145e952cf6230aa400da46",
    )
    db.add_all([first, second])
    db.flush()
    idempotency_key = f"attachment-manifest/{uuid4()}"

    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=idempotency_key,
        source=EmailSource(source_type="test", source_id=uuid4()),
        attachments=[second, first],
        commit=False,
    )

    assert queued.email_log.attachment_manifest == [
        {
            "attachment_id": str(second.id),
            "filename": "second.txt",
            "content_type": "text/plain",
            "size_bytes": 12,
            "sha256": "d7b0717202604f4941983807ee1dbed5cab2458921145e952cf6230aa400da46",
        },
        {
            "attachment_id": str(first.id),
            "filename": "first.txt",
            "content_type": "text/plain",
            "size_bytes": 11,
            "sha256": "e811e1ebb5f584ba17b364d7bac66bad0de3e0e223757e48c386de0e31ac63db",
        },
    ]
    assert [link.attachment_id for link in queued.email_log.attachment_links] == [
        second.id,
        first.id,
    ]
    assert queued.delivery.request_fingerprint != queued.email_log.content_fingerprint

    with pytest.raises(EmailDeliveryConflict, match="different email payload"):
        queue_rendered_email(
            db,
            organization_id=test_org.id,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{test_org.id}",
            rendered_email=_rendered_email(),
            idempotency_key=idempotency_key,
            source=EmailSource(source_type="test", source_id=queued.email_log.source_id),
            attachments=[first, second],
            commit=False,
        )

    assert (
        db.query(EmailLogAttachment)
        .filter(EmailLogAttachment.email_log_id == queued.email_log.id)
        .count()
        == 2
    )


def test_queue_rendered_email_adds_valid_opaque_webhook_correlation_tags(db, test_org):
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"correlation-tags/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        commit=False,
    )

    assert queued.email_log.safe_tags == [
        {"name": "message_kind", "value": "test"},
        {"name": "organization_id", "value": str(test_org.id)},
        {"name": "email_log_id", "value": str(queued.email_log.id)},
    ]
    # The provider request includes system correlation tags while operation
    # deduplication remains stable before those generated IDs exist.
    assert queued.delivery.request_fingerprint != queued.email_log.content_fingerprint


def test_queue_rendered_email_rejects_provider_invalid_tags_before_persisting(db, test_org):
    rendered = _rendered_email()
    invalid_rendered = RenderedEmail(
        recipient_email=rendered.recipient_email,
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        from_email=rendered.from_email,
        safe_tags=({"name": "contains space", "value": "unsafe"},),
    )

    with pytest.raises(ValueError, match="ASCII letters"):
        queue_rendered_email(
            db,
            organization_id=test_org.id,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{test_org.id}",
            rendered_email=invalid_rendered,
            idempotency_key=f"invalid-tags/{uuid4()}",
            source=EmailSource(source_type="test", source_id=uuid4()),
            commit=False,
        )

    assert db.query(EmailLog).filter(EmailLog.organization_id == test_org.id).count() == 0


def test_queue_rendered_email_records_suppression_without_a_delivery(db, test_org):
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email="recipient@example.com",
            reason=SuppressionReason.COMPLAINT.value,
            source_type="provider_webhook",
        )
    )
    db.flush()

    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"suppressed-delivery/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        commit=False,
    )

    assert queued.created is True
    assert queued.email_log.status == EmailStatus.SKIPPED.value
    assert queued.email_log.error == "suppressed"
    assert queued.delivery is None
    assert db.query(EmailDelivery).filter(EmailDelivery.organization_id == test_org.id).count() == 0


@pytest.mark.parametrize(
    ("reason", "should_queue"),
    [
        (SuppressionReason.OPT_OUT.value, True),
        (SuppressionReason.BOUNCED.value, False),
        (SuppressionReason.COMPLAINT.value, False),
    ],
)
def test_allow_opt_out_policy_never_bypasses_provider_safety_suppressions(
    db,
    test_org,
    reason,
    should_queue,
):
    db.add(
        EmailSuppression(
            organization_id=test_org.id,
            email="recipient@example.com",
            reason=reason,
            source_type="provider_webhook",
        )
    )
    db.flush()

    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"suppression-policy/{reason}/{uuid4()}",
        source=EmailSource(
            source_type="campaign_recipient",
            source_id=uuid4(),
            suppression_policy=EmailSuppressionPolicy.ALLOW_OPT_OUT,
        ),
        commit=False,
    )

    assert queued.email_log.suppression_policy == "allow_opt_out"
    assert (queued.delivery is not None) is should_queue
    assert queued.email_log.status == (
        EmailStatus.PENDING.value if should_queue else EmailStatus.SKIPPED.value
    )


def test_claim_due_deliveries_creates_a_durable_fenced_lease(db, test_org):
    now = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"claim-delivery/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=now - timedelta(seconds=1),
        commit=False,
    )

    claims = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=now,
        lease_for=timedelta(minutes=2),
        limit=10,
    )

    assert len(claims) == 1
    claim = claims[0]
    assert claim.delivery_id == queued.delivery.id
    assert claim.organization_id == test_org.id
    assert claim.email_log_id == queued.email_log.id
    assert claim.lease_owner == "worker-a"
    assert claim.attempt_number == 1

    db.expire_all()
    delivery = db.get(EmailDelivery, queued.delivery.id)
    assert delivery.status == EmailDeliveryStatus.LEASED.value
    assert delivery.lease_token == claim.lease_token
    assert delivery.lease_expires_at == now + timedelta(minutes=2)
    assert delivery.attempt_count == 1
    assert delivery.idempotency_expires_at == now + timedelta(hours=24)

    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(
            EmailDeliveryAttempt.delivery_id == delivery.id,
            EmailDeliveryAttempt.lease_token == claim.lease_token,
        )
        .one()
    )
    assert attempt.attempt_number == 1
    assert attempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value


def test_claim_due_deliveries_prioritizes_transactional_mail_over_older_bulk_mail(
    db,
    test_org,
):
    now = datetime.now(timezone.utc)
    marketing = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(subject="Older campaign"),
        idempotency_key=f"claim-priority/marketing/{uuid4()}",
        source=EmailSource(
            source_type="campaign_recipient",
            source_id=uuid4(),
            purpose="marketing",
        ),
        schedule_at=now - timedelta(minutes=10),
        commit=False,
    )
    transactional = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(subject="Newer invitation"),
        idempotency_key=f"claim-priority/transactional/{uuid4()}",
        source=EmailSource(
            source_type="org_invite",
            source_id=uuid4(),
            purpose="transactional",
        ),
        schedule_at=now - timedelta(seconds=1),
        commit=False,
    )

    claim = claim_due_deliveries(
        db,
        worker_id="priority-worker",
        now=now,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]

    assert claim.delivery_id == transactional.delivery.id
    assert claim.delivery_id != marketing.delivery.id


def test_retry_after_idempotency_expiry_requires_reconciliation(db, test_org):
    claimed_at = datetime.now(timezone.utc)
    queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"idempotency-expiry/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]

    delivery = record_delivery_failure(
        db,
        claim=claim,
        retryable=True,
        error_type="network_error",
        error_message="Provider outcome is unknown",
        retry_after=timedelta(hours=25),
        now=claimed_at + timedelta(seconds=1),
    )

    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.completed_at == claimed_at + timedelta(seconds=1)
    assert delivery.lease_token is None
    assert delivery.last_error_type == "idempotency_window_expired"
    assert delivery.email_log.status == EmailStatus.PENDING.value
    assert "reconciliation" in (delivery.email_log.error or "").lower()
    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(EmailDeliveryAttempt.delivery_id == delivery.id)
        .one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    assert attempt.retry_after_seconds is None
    reconciliation_case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == test_org.id,
            EmailReconciliationCase.email_delivery_id == delivery.id,
        )
        .one()
    )
    assert reconciliation_case.case_type == "unknown_delivery"
    assert reconciliation_case.status == "action_required"
    assert reconciliation_case.reason_code == "idempotency_window_expired"
    assert not hasattr(reconciliation_case, "last_error")


def test_due_retry_past_idempotency_expiry_is_not_sent_again(db, test_org):
    due_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"expired-before-claim/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=due_at - timedelta(seconds=1),
        commit=False,
    )
    queued.delivery.status = EmailDeliveryStatus.RETRY_SCHEDULED.value
    queued.delivery.idempotency_expires_at = due_at - timedelta(seconds=1)
    db.flush()

    claims = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=due_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )

    assert claims == []
    db.expire_all()
    delivery = db.get(EmailDelivery, queued.delivery.id)
    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.completed_at == due_at
    assert delivery.email_log.status == EmailStatus.PENDING.value


def test_stale_lease_cannot_complete_a_reclaimed_delivery(db, test_org):
    now = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"fenced-delivery/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=now - timedelta(seconds=1),
        commit=False,
    )
    first_claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=now,
        lease_for=timedelta(minutes=1),
        limit=1,
    )[0]
    second_claim = claim_due_deliveries(
        db,
        worker_id="worker-b",
        now=now + timedelta(minutes=2),
        lease_for=timedelta(minutes=1),
        limit=1,
    )[0]

    with pytest.raises(DeliveryLeaseLost):
        record_delivery_success(
            db,
            claim=first_claim,
            provider_message_id="resend-old-worker",
            now=now + timedelta(minutes=2, seconds=1),
        )

    db.expire_all()
    delivery = db.get(EmailDelivery, queued.delivery.id)
    email_log = db.get(EmailLog, queued.email_log.id)
    assert delivery.status == EmailDeliveryStatus.LEASED.value
    assert delivery.lease_token == second_claim.lease_token
    assert delivery.provider_message_id is None
    assert email_log.status == EmailStatus.PENDING.value
    assert email_log.external_id is None


def test_retryable_failure_schedules_bounded_retry_and_keeps_message_pending(db, test_org):
    claimed_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"retry-delivery/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        max_attempts=3,
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    failed_at = claimed_at + timedelta(seconds=5)

    delivery = record_delivery_failure(
        db,
        claim=claim,
        retryable=True,
        error_type="rate_limit",
        error_message="Provider rate limit",
        provider_http_status=429,
        retry_after=timedelta(seconds=90),
        now=failed_at,
    )

    assert delivery.status == EmailDeliveryStatus.RETRY_SCHEDULED.value
    assert delivery.run_at == failed_at + timedelta(seconds=90)
    assert delivery.completed_at is None
    assert delivery.lease_token is None
    assert delivery.last_error_type == "rate_limit"

    db.expire_all()
    email_log = db.get(EmailLog, queued.email_log.id)
    assert email_log.status == EmailStatus.PENDING.value
    assert email_log.error == "Provider rate limit"
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.RETRYABLE_ERROR.value
    assert attempt.provider_http_status == 429
    assert attempt.retry_after_seconds == 90


def test_expired_final_lease_requires_reconciliation_instead_of_reclaiming_forever(
    db,
    test_org,
):
    claimed_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"expired-final-lease/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        max_attempts=1,
        commit=False,
    )
    claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(seconds=30),
        limit=1,
    )
    expired_at = claimed_at + timedelta(minutes=1)

    reclaimed = claim_due_deliveries(
        db,
        worker_id="worker-b",
        now=expired_at,
        lease_for=timedelta(minutes=1),
        limit=1,
    )

    assert reclaimed == []
    db.expire_all()
    delivery = db.get(EmailDelivery, queued.delivery.id)
    email_log = db.get(EmailLog, queued.email_log.id)
    assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    assert delivery.completed_at == expired_at
    assert delivery.last_error_type == "lease_expired"
    assert delivery.lease_token is None
    assert email_log.status == EmailStatus.PENDING.value
    assert "operator reconciliation" in (email_log.error or "").lower()
    reconciliation_case = (
        db.query(EmailReconciliationCase)
        .filter(
            EmailReconciliationCase.organization_id == test_org.id,
            EmailReconciliationCase.email_delivery_id == delivery.id,
        )
        .one()
    )
    assert reconciliation_case.status == "action_required"
    assert reconciliation_case.reason_code == "delivery_lease_expired"
    assert reconciliation_case.detected_at == expired_at


def test_queue_rendered_email_rolls_back_with_the_callers_transaction(
    db_engine,
    committed_outbox_org,
):
    session = SessionLocal(bind=db_engine)
    verification = SessionLocal(bind=db_engine)
    idempotency_key = f"rollback-delivery/{uuid4()}"
    email_log_id = None
    delivery_id = None
    try:
        queued = queue_rendered_email(
            session,
            organization_id=committed_outbox_org,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{committed_outbox_org}",
            rendered_email=_rendered_email(),
            idempotency_key=idempotency_key,
            source=EmailSource(source_type="test", source_id=uuid4()),
            commit=False,
        )
        email_log_id = queued.email_log.id
        delivery_id = queued.delivery.id
        session.rollback()

        assert verification.get(EmailLog, email_log_id) is None
        assert verification.get(EmailDelivery, delivery_id) is None
    finally:
        session.rollback()
        verification.rollback()
        session.close()
        verification.close()


def test_claim_due_deliveries_skips_a_row_locked_by_another_worker(
    db_engine,
    committed_outbox_org,
):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("SKIP LOCKED behavior requires PostgreSQL")

    setup = SessionLocal(bind=db_engine)
    locker = SessionLocal(bind=db_engine)
    worker = SessionLocal(bind=db_engine)
    now = datetime.now(timezone.utc)
    delivery_id = None
    try:
        queued = queue_rendered_email(
            setup,
            organization_id=committed_outbox_org,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{committed_outbox_org}",
            rendered_email=_rendered_email(),
            idempotency_key=f"skip-locked-delivery/{uuid4()}",
            source=EmailSource(source_type="test", source_id=uuid4()),
            schedule_at=now - timedelta(seconds=1),
            commit=True,
        )
        delivery_id = queued.delivery.id

        (
            locker.query(EmailDelivery)
            .filter(EmailDelivery.id == delivery_id)
            .with_for_update()
            .one()
        )
        assert (
            claim_due_deliveries(
                worker,
                worker_id="worker-b",
                now=now,
                lease_for=timedelta(minutes=2),
                limit=1,
            )
            == []
        )

        locker.rollback()
        claimed = claim_due_deliveries(
            worker,
            worker_id="worker-b",
            now=now,
            lease_for=timedelta(minutes=2),
            limit=1,
        )
        assert [claim.delivery_id for claim in claimed] == [delivery_id]
    finally:
        setup.rollback()
        locker.rollback()
        worker.rollback()
        setup.close()
        locker.close()
        worker.close()


def test_concurrent_exact_queue_calls_converge_on_one_message(
    db_engine,
    committed_outbox_org,
):
    barrier = Barrier(2)
    idempotency_key = f"concurrent-delivery/{uuid4()}"
    source = EmailSource(source_type="test", source_id=uuid4())
    results: list[tuple[bool, object, object]] = []
    errors: list[Exception] = []

    def queue_once() -> None:
        session = SessionLocal(bind=db_engine)

        @event.listens_for(session, "before_flush", once=True)
        def synchronize_first_flush(*_args) -> None:
            barrier.wait(timeout=5)

        try:
            queued = queue_rendered_email(
                session,
                organization_id=committed_outbox_org,
                route=DeliveryRoute.ORGANIZATION_RESEND,
                provider_account_id=f"organization:{committed_outbox_org}",
                rendered_email=_rendered_email(),
                idempotency_key=idempotency_key,
                source=source,
                commit=False,
            )
            session.commit()
            results.append(
                (
                    queued.created,
                    queued.email_log.id,
                    queued.delivery.id,
                )
            )
        except Exception as exc:
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [Thread(target=queue_once), Thread(target=queue_once)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(created for created, _, _ in results) == [False, True]
    assert len({email_log_id for _, email_log_id, _ in results}) == 1
    assert len({delivery_id for _, _, delivery_id in results}) == 1

    verification = SessionLocal(bind=db_engine)
    try:
        assert (
            verification.query(EmailLog)
            .filter(
                EmailLog.organization_id == committed_outbox_org,
                EmailLog.idempotency_key == idempotency_key,
            )
            .count()
            == 1
        )
        assert (
            verification.query(EmailDelivery)
            .filter(
                EmailDelivery.organization_id == committed_outbox_org,
                EmailDelivery.idempotency_key == idempotency_key,
            )
            .count()
            == 1
        )
    finally:
        verification.close()


def test_renewed_lease_is_not_reclaimed_at_its_original_expiry(db, test_org):
    claimed_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"renewed-lease/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        commit=False,
    )
    original_claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=1),
        limit=1,
    )[0]
    renewed_at = claimed_at + timedelta(seconds=30)

    renewed_claim = renew_delivery_lease(
        db,
        claim=original_claim,
        now=renewed_at,
        lease_for=timedelta(minutes=2),
    )

    assert renewed_claim.lease_expires_at == renewed_at + timedelta(minutes=2)
    assert (
        claim_due_deliveries(
            db,
            worker_id="worker-b",
            now=claimed_at + timedelta(minutes=1),
            lease_for=timedelta(minutes=1),
            limit=1,
        )
        == []
    )
    db.expire_all()
    delivery = db.get(EmailDelivery, queued.delivery.id)
    assert delivery.lease_token == original_claim.lease_token
    assert delivery.lease_expires_at == renewed_claim.lease_expires_at


def test_provider_acceptance_updates_delivery_attempt_and_message_atomically(db, test_org):
    claimed_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"accepted-delivery/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    accepted_at = claimed_at + timedelta(seconds=1)

    delivery = record_delivery_success(
        db,
        claim=claim,
        provider_message_id="resend-message-1",
        now=accepted_at,
    )

    assert delivery.status == EmailDeliveryStatus.SENT.value
    assert delivery.provider_message_id == "resend-message-1"
    assert delivery.completed_at == accepted_at
    assert delivery.lease_token is None

    db.expire_all()
    email_log = db.get(EmailLog, queued.email_log.id)
    assert email_log.status == EmailStatus.SENT.value
    assert email_log.external_id == "resend-message-1"
    assert email_log.sent_at == accepted_at
    assert email_log.resend_status == "sent"
    assert email_log.resend_status_at == accepted_at
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    assert attempt.outcome == EmailDeliveryAttemptOutcome.SUCCEEDED.value
    assert attempt.provider_message_id == "resend-message-1"
    assert attempt.completed_at == accepted_at


def test_provider_failure_diagnostics_do_not_persist_contact_pii(db, test_org):
    claimed_at = datetime.now(timezone.utc)
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=f"sanitized-failure/{uuid4()}",
        source=EmailSource(source_type="test", source_id=uuid4()),
        schedule_at=claimed_at - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]

    delivery = record_delivery_failure(
        db,
        claim=claim,
        retryable=False,
        error_type="validation_error",
        error_message=("Rejected recipient@example.com; contact +1 (212) 555-1212 for details"),
        provider_http_status=422,
        now=claimed_at + timedelta(seconds=1),
    )

    db.expire_all()
    email_log = db.get(EmailLog, queued.email_log.id)
    attempt = (
        db.query(EmailDeliveryAttempt).filter(EmailDeliveryAttempt.delivery_id == delivery.id).one()
    )
    diagnostics = " ".join(
        value for value in (delivery.last_error, email_log.error, attempt.error_message) if value
    )
    assert "recipient@example.com" not in diagnostics
    assert "555-1212" not in diagnostics
    assert "[redacted-email]" in diagnostics
    assert "[redacted-phone]" in diagnostics


def test_queue_accepts_resends_documented_256_character_idempotency_key(db, test_org):
    idempotency_key = "k" * 256

    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=_rendered_email(),
        idempotency_key=idempotency_key,
        source=EmailSource(source_type="test", source_id=uuid4()),
        commit=False,
    )

    assert queued.delivery.idempotency_key == idempotency_key
    with pytest.raises(ValueError, match="256 characters or fewer"):
        queue_rendered_email(
            db,
            organization_id=test_org.id,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{test_org.id}",
            rendered_email=_rendered_email(),
            idempotency_key="k" * 257,
            source=EmailSource(source_type="test", source_id=uuid4()),
            commit=False,
        )
