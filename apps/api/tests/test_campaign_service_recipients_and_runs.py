from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4


from app.core.encryption import hash_email
from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus, JobStatus, JobType
from app.db.models import Campaign, CampaignRecipient, CampaignRun, EmailSuppression, EmailTemplate, Job, Surrogate
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


def _create_campaign(db, org_id: UUID, user_id: UUID, template_id: UUID, *, status: str = CampaignStatus.DRAFT.value) -> Campaign:
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


def _create_surrogate(db, *, org_id: UUID, user_id: UUID, stage_id: UUID, status_label: str, email: str | None, name: str) -> Surrogate:
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


def test_campaign_enqueue_send_now_and_scheduled(monkeypatch, db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign_now = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.DRAFT.value)
    campaign_later = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.DRAFT.value)
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
        .filter(Job.job_type == JobType.CAMPAIGN_SEND.value, Job.payload["campaign_id"].astext == str(campaign_now.id))
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


def test_campaign_retry_queue_and_cancel(monkeypatch, db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value)
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

    pending_job = (
        db.query(Job)
        .filter(Job.id == existing_job_id)
        .first()
    )
    assert pending_job is not None
    pending_job.status = JobStatus.PENDING.value
    db.add(pending_job)
    db.commit()

    cancelled = campaign_service.cancel_campaign(db, test_org.id, campaign.id)
    assert cancelled is True
    assert campaign.status == CampaignStatus.CANCELLED.value
    assert pending_job.status == JobStatus.FAILED.value


def test_execute_campaign_run_with_duplicates_and_suppression(monkeypatch, db, test_org, test_user, default_stage):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value)
    run = _create_run(db, test_org.id, campaign.id, status="running")

    recipients = [
        SimpleNamespace(id=uuid4(), email="alpha@example.com", full_name="Alpha", first_name="Alpha"),
        SimpleNamespace(id=uuid4(), email="alpha@example.com", full_name="Duplicate Alpha", first_name="Duplicate"),
        SimpleNamespace(id=uuid4(), email="suppressed@example.com", full_name="Suppressed", first_name="Suppressed"),
        SimpleNamespace(id=uuid4(), email=None, full_name="No Email", first_name="No"),
    ]
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
    monkeypatch.setattr(campaign_service, "_load_suppressed_emails", lambda *args, **kwargs: {"suppressed@example.com"})
    monkeypatch.setattr("app.services.org_service.get_org_by_id", lambda *_args, **_kwargs: SimpleNamespace(slug="acme"))
    monkeypatch.setattr("app.services.org_service.get_org_portal_base_url", lambda *_args, **_kwargs: "https://acme.example.com")
    monkeypatch.setattr("app.services.email_composition_service.strip_legacy_unsubscribe_placeholders", lambda body: body)
    monkeypatch.setattr(
        "app.services.email_composition_service.compose_template_email_html",
        lambda **kwargs: kwargs["rendered_body_html"],
    )
    monkeypatch.setattr("app.services.tracking_service.generate_tracking_token", lambda: "tracking-token")
    monkeypatch.setattr("app.services.tracking_service.prepare_email_for_tracking", lambda body, token: f"{body}-{token}")

    monkeypatch.setattr("app.services.email_service.build_surrogate_template_variables", lambda db, entity: {"full_name": entity.full_name})
    monkeypatch.setattr("app.services.email_service.render_template", lambda subject, body, variables: (subject, body))

    def _send_email(**kwargs):
        return SimpleNamespace(id=uuid4(), status=EmailStatus.PENDING.value), SimpleNamespace(id=uuid4())

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
    assert campaign.status in {CampaignStatus.SENDING.value, CampaignStatus.FAILED.value, CampaignStatus.COMPLETED.value}


def test_execute_campaign_run_completed_short_circuit(db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.COMPLETED.value)
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


def test_retry_failed_campaign_run_updates_recipients(monkeypatch, db, test_org, test_user, default_stage):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.FAILED.value)
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
    )
    db.add(failed_recipient)
    db.commit()

    monkeypatch.setattr(campaign_service, "_load_suppressed_emails", lambda *args, **kwargs: set())
    monkeypatch.setattr("app.services.org_service.get_org_by_id", lambda *_args, **_kwargs: SimpleNamespace(slug="acme"))
    monkeypatch.setattr("app.services.org_service.get_org_portal_base_url", lambda *_args, **_kwargs: "https://acme.example.com")
    monkeypatch.setattr("app.services.email_composition_service.strip_legacy_unsubscribe_placeholders", lambda body: body)
    monkeypatch.setattr(
        "app.services.email_composition_service.compose_template_email_html",
        lambda **kwargs: kwargs["rendered_body_html"],
    )
    monkeypatch.setattr("app.services.tracking_service.generate_tracking_token", lambda: "retry-token")
    monkeypatch.setattr("app.services.tracking_service.prepare_email_for_tracking", lambda body, token: f"{body}-{token}")
    monkeypatch.setattr("app.services.email_service.build_surrogate_template_variables", lambda db, entity: {"full_name": entity.full_name})
    monkeypatch.setattr("app.services.email_service.render_template", lambda subject, body, variables: (subject, body))
    monkeypatch.setattr(
        "app.services.email_service.send_email",
        lambda **kwargs: (SimpleNamespace(id=uuid4(), status=EmailStatus.PENDING.value), SimpleNamespace(id=uuid4())),
    )

    result = campaign_service.retry_failed_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
        actor_user_id=test_user.id,
    )
    assert result["retried_count"] == 1
    db.refresh(failed_recipient)
    assert failed_recipient.status == CampaignRecipientStatus.PENDING.value


def test_campaign_run_listing_helpers(db, test_org, test_user):
    template = _create_template(db, test_org.id)
    campaign = _create_campaign(db, test_org.id, test_user.id, template.id, status=CampaignStatus.SENDING.value)
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
