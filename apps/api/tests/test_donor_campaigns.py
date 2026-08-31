from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.encryption import hash_email, hash_phone
from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    Donor,
    EmailLog,
    EmailTemplate,
    MessageTemplate,
    Organization,
    Pipeline,
    PipelineStage,
)
from app.schemas.campaign import CampaignCreate, CampaignRecipientResponse, PreviewFiltersRequest
from app.services import campaign_service, pipeline_dependency_service, pipeline_service
from app.utils.normalization import normalize_email, normalize_phone


def _donor_pipeline_stage(
    db,
    *,
    organization_id: UUID,
    recipient_type: str,
    stage_key: str = "new",
) -> tuple[Pipeline, PipelineStage]:
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        organization_id,
        entity_type=recipient_type,
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    assert stage is not None
    return pipeline, stage


def _create_donor(
    db,
    *,
    organization_id: UUID,
    donor_type: str,
    stage_id: UUID,
    email: str,
    phone: str | None = None,
    full_name: str = "Donor Recipient",
    owner_id: UUID | None = None,
    archived: bool = False,
) -> Donor:
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone) if phone else None
    donor = Donor(
        id=uuid4(),
        organization_id=organization_id,
        donor_number=f"D{uuid4().int % 90000 + 10000:05d}",
        donor_type=donor_type,
        full_name=full_name,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
        state="NY",
        education="Bachelor's degree",
        source="campaign-test",
        owner_type="user" if owner_id else None,
        owner_id=owner_id,
        stage_id=stage_id,
        is_archived=archived,
        archived_at=datetime.now(UTC) if archived else None,
    )
    db.add(donor)
    db.flush()
    return donor


def _create_email_template(db, organization_id: UUID) -> EmailTemplate:
    template = EmailTemplate(
        id=uuid4(),
        organization_id=organization_id,
        name=f"Donor campaign {uuid4().hex[:8]}",
        subject="Hello {{first_name}} — {{donor_number}}",
        body="<p>{{donor_type}} | {{education}} | {{status_label}}</p>",
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template


def _create_run(
    db,
    *,
    organization_id: UUID,
    campaign_id: UUID,
    status: str = "running",
) -> CampaignRun:
    run = CampaignRun(
        id=uuid4(),
        organization_id=organization_id,
        campaign_id=campaign_id,
        status=status,
        email_provider="resend",
        started_at=datetime.now(UTC),
        total_count=0,
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()
    return run


def _configure_resend_provider(db, organization_id: UUID) -> None:
    from app.db.models import ResendSettings
    from app.services import resend_settings_service

    db.add(
        ResendSettings(
            organization_id=organization_id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="campaigns@example.com",
            from_name="Campaign Team",
            verified_domain="example.com",
        )
    )
    db.flush()


def _create_other_org(db) -> Organization:
    organization = Organization(
        id=uuid4(),
        name="Other Donor Organization",
        slug=f"other-donor-{uuid4().hex[:8]}",
    )
    db.add(organization)
    db.flush()
    return organization


def test_campaign_recipient_contract_accepts_exact_donor_subtypes_only():
    template_id = uuid4()

    for recipient_type in ("egg_donor", "sperm_donor"):
        campaign = CampaignCreate(
            name=f"{recipient_type} campaign",
            email_template_id=template_id,
            recipient_type=recipient_type,
        )
        preview = PreviewFiltersRequest(recipient_type=recipient_type)
        assert campaign.recipient_type == recipient_type
        assert preview.recipient_type == recipient_type

    with pytest.raises(ValidationError):
        CampaignCreate(
            name="Ambiguous donor campaign",
            email_template_id=template_id,
            recipient_type="donor",
        )


def test_donor_campaign_stage_filters_are_subtype_and_tenant_scoped(
    db,
    test_org,
    test_user,
):
    egg_pipeline, egg_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
    )
    _sperm_pipeline, sperm_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="sperm_donor",
    )
    other_org = _create_other_org(db)
    _other_pipeline, other_egg_stage = _donor_pipeline_stage(
        db,
        organization_id=other_org.id,
        recipient_type="egg_donor",
    )
    template = _create_email_template(db, test_org.id)

    campaign = campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Exact egg stage",
            email_template_id=template.id,
            recipient_type="egg_donor",
            filter_criteria={"stage_ids": [egg_stage.id]},
        ),
    )
    assert campaign.filter_criteria["stage_ids"] == [str(egg_stage.id)]
    assert campaign.filter_criteria["stage_keys"] == [egg_stage.stage_key]

    for forbidden_stage in (sperm_stage, other_egg_stage):
        with pytest.raises(ValueError, match="Stage filter not found in egg donor pipeline"):
            campaign_service.create_campaign(
                db,
                test_org.id,
                test_user.id,
                CampaignCreate(
                    name=f"Forbidden stage {forbidden_stage.id}",
                    email_template_id=template.id,
                    recipient_type="egg_donor",
                    filter_criteria={"stage_ids": [forbidden_stage.id]},
                ),
            )

    graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, egg_pipeline)
    new_stage_dependencies = next(
        item for item in graph["stages"] if item["stage_id"] == egg_stage.id
    )
    assert [item["id"] for item in new_stage_dependencies["campaign_refs"]] == [str(campaign.id)]


def test_donor_email_preview_filters_subtype_archive_suppression_and_org(
    db,
    test_org,
    test_user,
):
    _egg_pipeline, egg_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
        stage_key="contacted",
    )
    _sperm_pipeline, sperm_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="sperm_donor",
        stage_key="contacted",
    )
    egg = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=egg_stage.id,
        email="egg-preview@example.com",
    )
    _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=egg_stage.id,
        email="egg-archived@example.com",
        archived=True,
    )
    _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="sperm",
        stage_id=sperm_stage.id,
        email="sperm-preview@example.com",
    )
    other_org = _create_other_org(db)
    _other_pipeline, other_stage = _donor_pipeline_stage(
        db,
        organization_id=other_org.id,
        recipient_type="egg_donor",
        stage_key="contacted",
    )
    _create_donor(
        db,
        organization_id=other_org.id,
        donor_type="egg",
        stage_id=other_stage.id,
        email="other-egg@example.com",
    )

    preview = campaign_service.preview_recipients(
        db,
        test_org.id,
        "egg_donor",
        {"stage_keys": ["contacted"], "states": ["NY"]},
    )
    assert preview.total_count == 1
    assert preview.eligible_count == 1
    assert [
        (item.entity_type, item.entity_id, item.stage) for item in preview.sample_recipients
    ] == [("egg_donor", egg.id, egg_stage.label)]

    campaign_service.add_to_suppression(
        db,
        test_org.id,
        egg.email,
        "opt_out",
        source_type="donor",
        source_id=egg.id,
    )
    suppressed = campaign_service.preview_recipients(
        db,
        test_org.id,
        "egg_donor",
        {"stage_ids": [str(egg_stage.id)]},
    )
    assert suppressed.total_count == 1
    assert suppressed.eligible_count == 0
    assert suppressed.suppressed_count == 1
    assert suppressed.sample_recipients == []


def test_donor_template_variables_include_identity_owner_brand_and_unsubscribe(
    db,
    test_org,
    test_user,
):
    from app.services import email_service

    _pipeline, stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
        stage_key="medical_records_review",
    )
    donor = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=stage.id,
        email="template-egg@example.com",
        phone="+16075550111",
        full_name="Avery Donor",
        owner_id=test_user.id,
    )
    donor.stage = stage

    variables = email_service.build_donor_template_variables(db, donor)

    assert variables == {
        "first_name": "Avery",
        "full_name": "Avery Donor",
        "email": "template-egg@example.com",
        "phone": "+16075550111",
        "donor_number": donor.donor_number,
        "donor_type": "Egg Donor",
        "education": "Bachelor's degree",
        "status_label": stage.label,
        "state": "NY",
        "owner_name": test_user.display_name,
        "org_name": test_org.name,
        "org_logo_url": "",
        "unsubscribe_url": variables["unsubscribe_url"],
    }
    assert variables["unsubscribe_url"].startswith("http")


def test_donor_email_campaign_send_is_exact_and_idempotent(
    db,
    test_org,
    test_user,
):
    _pipeline, stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="sperm_donor",
        stage_key="available",
    )
    donor = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="sperm",
        stage_id=stage.id,
        email="send-sperm@example.com",
        full_name="Jordan Sample",
    )
    donor.stage = stage
    template = _create_email_template(db, test_org.id)
    campaign = campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Sperm donor send",
            email_template_id=template.id,
            recipient_type="sperm_donor",
            filter_criteria={"stage_keys": ["available"]},
        ),
    )
    run = _create_run(
        db,
        organization_id=test_org.id,
        campaign_id=campaign.id,
    )
    _configure_resend_provider(db, test_org.id)
    db.commit()

    campaign_service.execute_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )
    campaign_service.execute_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )

    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run.id).one()
    logs = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "campaign_recipient",
            EmailLog.source_id == recipient.id,
        )
        .all()
    )
    assert recipient.entity_type == "sperm_donor"
    assert recipient.entity_id == donor.id
    assert recipient.status == CampaignRecipientStatus.PENDING.value
    assert len(logs) == 1
    assert recipient.donor_launch_snapshot == {
        "version": 1,
        "recipient_email": logs[0].recipient_email,
        "recipient_name": recipient.recipient_name,
        "subject": logs[0].subject,
        "body": logs[0].body,
    }
    assert "donor_launch_snapshot" not in CampaignRecipientResponse.model_validate(
        recipient
    ).model_dump()
    assert donor.donor_number in logs[0].subject
    assert "Sperm Donor" in logs[0].body
    assert "Bachelor&#x27;s degree" in logs[0].body


def test_donor_campaign_retry_uses_immutable_launch_identity_and_content(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    from app.services import email_service

    _pipeline, stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
        stage_key="contacted",
    )
    donor = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=stage.id,
        email="launch-egg@example.com",
        full_name="Launch Identity",
    )
    donor.stage = stage
    template = _create_email_template(db, test_org.id)
    campaign = campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Immutable egg retry",
            email_template_id=template.id,
            recipient_type="egg_donor",
            filter_criteria={"stage_keys": ["contacted"]},
        ),
    )
    run = _create_run(
        db,
        organization_id=test_org.id,
        campaign_id=campaign.id,
    )
    _configure_resend_provider(db, test_org.id)
    db.commit()

    real_send_email = email_service.send_email

    def fail_first_attempt(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(email_service, "send_email", fail_first_attempt)
    campaign_service.execute_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )

    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run.id).one()
    assert recipient.status == CampaignRecipientStatus.FAILED.value
    snapshot = recipient.donor_launch_snapshot
    assert snapshot is not None
    assert snapshot["version"] == 1
    assert snapshot["recipient_email"] == "launch-egg@example.com"
    assert snapshot["recipient_name"] == "Launch Identity"
    assert snapshot["subject"] == f"Hello Launch — {donor.donor_number}"
    assert "Bachelor&#x27;s degree" in snapshot["body"]
    assert stage.label in snapshot["body"]

    donor.email = "changed-egg@example.com"
    donor.email_hash = hash_email(donor.email)
    donor.full_name = "Changed Identity"
    donor.education = "Changed education"
    db.commit()

    monkeypatch.setattr(email_service, "send_email", real_send_email)
    result = campaign_service.retry_failed_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )

    assert result["retried_count"] == 1
    log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "campaign_recipient",
            EmailLog.source_id == recipient.id,
        )
        .one()
    )
    assert log.recipient_email == "launch-egg@example.com"
    assert "Launch" in log.subject
    assert "Changed" not in log.subject
    assert "Bachelor&#x27;s degree" in log.body
    assert "Changed education" not in log.body


def test_donor_campaign_retry_links_queue_time_suppression_audit_log(
    monkeypatch,
    db,
    test_org,
    test_user,
):
    from app.services import email_service

    _pipeline, stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
        stage_key="contacted",
    )
    donor = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=stage.id,
        email="suppressed-at-queue@example.com",
        full_name="Suppressed Donor",
    )
    template = _create_email_template(db, test_org.id)
    campaign = campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Queue-time donor suppression",
            email_template_id=template.id,
            recipient_type="egg_donor",
        ),
    )
    campaign.status = CampaignStatus.FAILED.value
    run = _create_run(
        db,
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="failed",
    )
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="egg_donor",
        entity_id=donor.id,
        recipient_email=donor.email,
        recipient_name=donor.full_name,
        donor_launch_snapshot={
            "version": 1,
            "recipient_email": donor.email,
            "recipient_name": donor.full_name,
            "subject": "Frozen subject",
            "body": "<p>Frozen body</p>",
        },
        status=CampaignRecipientStatus.FAILED.value,
    )
    db.add(recipient)
    _configure_resend_provider(db, test_org.id)
    db.commit()

    real_send_email = email_service.send_email

    def suppress_before_queue(**kwargs):
        campaign_service.add_to_suppression(
            db,
            test_org.id,
            kwargs["recipient_email"],
            "opt_out",
            source_type="donor",
            source_id=donor.id,
        )
        return real_send_email(**kwargs)

    monkeypatch.setattr(email_service, "send_email", suppress_before_queue)
    result = campaign_service.retry_failed_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )

    db.refresh(recipient)
    log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "campaign_recipient",
            EmailLog.source_id == recipient.id,
        )
        .one()
    )
    assert result["retried_count"] == 0
    assert recipient.status == CampaignRecipientStatus.SKIPPED.value
    assert recipient.skip_reason == "suppressed"
    assert recipient.email_log_id == log.id
    assert log.status == EmailStatus.SKIPPED.value


def test_donor_campaign_retry_reloads_only_exact_subtype_and_org(
    db,
    test_org,
    test_user,
):
    _sperm_pipeline, sperm_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="sperm_donor",
    )
    _egg_pipeline, egg_stage = _donor_pipeline_stage(
        db,
        organization_id=test_org.id,
        recipient_type="egg_donor",
    )
    egg = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="egg",
        stage_id=egg_stage.id,
        email="wrong-subtype@example.com",
    )
    sperm = _create_donor(
        db,
        organization_id=test_org.id,
        donor_type="sperm",
        stage_id=sperm_stage.id,
        email="retry-sperm@example.com",
    )
    other_org = _create_other_org(db)
    _other_pipeline, other_stage = _donor_pipeline_stage(
        db,
        organization_id=other_org.id,
        recipient_type="sperm_donor",
    )
    other_sperm = _create_donor(
        db,
        organization_id=other_org.id,
        donor_type="sperm",
        stage_id=other_stage.id,
        email="other-retry@example.com",
    )
    template = _create_email_template(db, test_org.id)
    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name="Exact retry",
        channel="email",
        email_template_id=template.id,
        recipient_type="sperm_donor",
        filter_criteria={},
        status=CampaignStatus.FAILED.value,
        created_by_user_id=test_user.id,
    )
    db.add(campaign)
    db.flush()
    run = _create_run(
        db,
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="failed",
    )
    recipients = [
        CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="sperm_donor",
            entity_id=entity.id,
            recipient_email=entity.email,
            recipient_name=entity.full_name,
            status=CampaignRecipientStatus.FAILED.value,
        )
        for entity in (sperm, egg, other_sperm)
    ]
    db.add_all(recipients)
    _configure_resend_provider(db, test_org.id)
    db.commit()

    result = campaign_service.retry_failed_campaign_run(
        db,
        test_org.id,
        campaign.id,
        run.id,
        actor_user_id=test_user.id,
    )

    db.refresh(recipients[0])
    db.refresh(recipients[1])
    db.refresh(recipients[2])
    assert result["retried_count"] == 1
    assert recipients[0].status == CampaignRecipientStatus.PENDING.value
    assert recipients[0].send_revision == 1
    assert recipients[1].status == CampaignRecipientStatus.SKIPPED.value
    assert recipients[1].skip_reason == "missing_recipient"
    assert recipients[2].status == CampaignRecipientStatus.SKIPPED.value
    assert recipients[2].skip_reason == "missing_recipient"


def test_donor_messaging_campaigns_are_rejected_until_consent_is_donor_linked(
    db,
    test_org,
    test_user,
):
    with pytest.raises(ValueError, match="Messaging campaigns are not available for donors"):
        campaign_service.preview_recipients(
            db,
            test_org.id,
            "egg_donor",
            {},
            channel="messaging",
        )

    with pytest.raises(ValueError, match="Messaging campaigns are not available for donors"):
        campaign_service.create_campaign(
            db,
            test_org.id,
            test_user.id,
            CampaignCreate(
                name="Rejected donor messaging",
                channel="messaging",
                message_template_version_id=uuid4(),
                recipient_type="sperm_donor",
            ),
        )
    assert db.query(Campaign).filter(Campaign.organization_id == test_org.id).count() == 0

    body = "Donor opportunities. Msg & data rates may apply. Reply STOP to opt out."
    template = MessageTemplate(
        organization_id=test_org.id,
        template_key=uuid4(),
        version=1,
        name="Egg donor promotional v1",
        purpose="promotional",
        body=body,
        content_hash=hashlib.sha256(body.encode()).hexdigest(),
        status="published",
        published_at=datetime.now(UTC),
        created_by_user_id=test_user.id,
        is_enrollment_confirmation=True,
    )
    db.add(template)
    db.flush()
    legacy_campaign = Campaign(
        organization_id=test_org.id,
        name="Legacy donor messaging",
        channel="messaging",
        message_template_version_id=template.id,
        recipient_type="egg_donor",
        filter_criteria={},
        include_unsubscribed=False,
        status=CampaignStatus.DRAFT.value,
        created_by_user_id=test_user.id,
    )
    db.add(legacy_campaign)
    db.commit()

    with pytest.raises(ValueError, match="Messaging campaigns are not available for donors"):
        campaign_service.enqueue_campaign_send(
            db,
            test_org.id,
            legacy_campaign.id,
            test_user.id,
            send_now=True,
        )
    assert (
        db.query(CampaignRun)
        .filter(CampaignRun.organization_id == test_org.id, CampaignRun.campaign_id == legacy_campaign.id)
        .count()
        == 0
    )
