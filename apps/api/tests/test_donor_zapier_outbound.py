"""Donor stage reporting through the existing Zapier delivery worker."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.enums import JobStatus, JobType, Role
from app.db.models import (
    DonorStatusHistory,
    Form,
    FormIntakeLink,
    FormSubmission,
    Job,
    LeadAttribution,
    MetaLead,
    Organization,
    Pipeline,
    PipelineStage,
    ZapierOutboundEvent,
)
from app.schemas.donor import DonorCreate
from app.services import (
    donor_service,
    status_change_request_service,
    zapier_outbound_service,
    zapier_settings_service,
)


def _seed_donor_pipeline(db, org_id, donor_type: str):
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_type=f"{donor_type}_donor",
        name=f"{donor_type.title()} donor reporting",
        is_default=True,
        current_version=1,
        feature_config={
            "role_visibility": {
                Role.CASE_MANAGER.value: {
                    "stage_types": ["intake", "post_approval"],
                    "stage_keys": [],
                    "capabilities": [],
                }
            },
            "role_mutation": {
                Role.CASE_MANAGER.value: {
                    "stage_types": ["intake", "post_approval"],
                    "stage_keys": [],
                    "capabilities": [],
                }
            },
        },
    )
    db.add(pipeline)
    db.flush()
    new_stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        stage_key="new",
        slug="new",
        label="New donor",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    ready_stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        stage_key="ready_to_match",
        slug="ready-to-match",
        label="Internal donor ready label",
        color="#F59E0B",
        stage_type="post_approval",
        order=2,
        is_active=True,
        is_intake_stage=False,
    )
    db.add_all([new_stage, ready_stage])
    db.flush()
    return pipeline, new_stage, ready_stage


def _create_donor(db, org_id, user_id, donor_type: str = "egg"):
    return donor_service.create_donor(
        db,
        org_id,
        user_id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Private Donor Name",
            email=f"private-{uuid.uuid4().hex[:8]}@example.com",
            phone="+1 607 555 0102",
            source="Website",
        ),
        emit_workflow_events=False,
    )


def _configure_reporting(db, org_id, *, donor_type, pipeline, stage, event_name="Qualified"):
    settings = zapier_settings_service.get_or_create_settings(db, org_id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/donor"
    settings.donor_outbound_enabled = True
    settings.outbound_send_hashed_pii = True
    settings.donor_outbound_event_mapping = [
        {
            "donor_type": donor_type,
            "pipeline_id": str(pipeline.id),
            "stage_id": str(stage.id),
            "event_name": event_name,
            "enabled": True,
        }
    ]
    db.commit()
    return settings


def _attach_meta_lead(db, donor, *, org_id=None):
    lead = MetaLead(
        organization_id=org_id or donor.organization_id,
        meta_lead_id=f"meta-{uuid.uuid4().hex}",
        meta_form_id="meta-form-1",
        meta_page_id="meta-page-1",
        field_data_raw={
            "email": "must-not-leak@example.com",
            "medical_condition": "must-not-leak",
            "ad_id": "sensitive-ad-answer",
            "campaign_id": "sensitive-campaign-answer",
            "fbc": "sensitive-fbc-answer",
            "nested_answers": {
                "meta_ad_id": "sensitive-nested-meta-ad",
                "meta_adset_id": "sensitive-nested-meta-adset",
                "meta_campaign_id": "sensitive-nested-meta-campaign",
                "meta_fbc": "sensitive-nested-meta-fbc",
            },
        },
        converted_donor_id=donor.id,
        is_converted=True,
        converted_at=datetime.now(UTC),
    )
    db.add(lead)
    db.commit()
    return lead


@pytest.mark.asyncio
async def test_donor_reporting_defaults_off_and_validates_exact_pipeline_mapping(
    authed_client, db, test_org
):
    egg_pipeline, _egg_new, egg_ready = _seed_donor_pipeline(db, test_org.id, "egg")
    sperm_pipeline, _sperm_new, sperm_ready = _seed_donor_pipeline(db, test_org.id, "sperm")
    db.commit()

    initial = await authed_client.get("/integrations/zapier/settings")
    assert initial.status_code == 200
    assert initial.json()["donor_outbound_enabled"] is False
    assert initial.json()["donor_event_mapping"] == []

    payload = {
        "donor_outbound_enabled": True,
        "donor_event_mapping": [
            {
                "donor_type": "egg",
                "pipeline_id": str(egg_pipeline.id),
                "stage_id": str(egg_ready.id),
                "event_name": "Qualified",
            },
            {
                "donor_type": "sperm",
                "pipeline_id": str(sperm_pipeline.id),
                "stage_id": str(sperm_ready.id),
                "event_name": "Converted",
            },
        ],
    }
    updated = await authed_client.post("/integrations/zapier/settings/outbound", json=payload)
    assert updated.status_code == 200, updated.text
    assert updated.json()["donor_event_mapping"] == [
        payload["donor_event_mapping"][0] | {"enabled": True},
        payload["donor_event_mapping"][1] | {"enabled": True},
    ]

    invalid_subtype = payload | {
        "donor_event_mapping": [payload["donor_event_mapping"][0] | {"donor_type": "sperm"}]
    }
    invalid = await authed_client.post(
        "/integrations/zapier/settings/outbound", json=invalid_subtype
    )
    assert invalid.status_code == 400
    assert "selected donor pipeline" in invalid.json()["detail"]

    unsupported = await authed_client.post(
        "/integrations/zapier/settings/outbound",
        json=payload
        | {
            "donor_event_mapping": [
                payload["donor_event_mapping"][0] | {"event_name": "Egg Donor Approved"}
            ]
        },
    )
    assert unsupported.status_code == 422


@pytest.mark.asyncio
async def test_donor_mapping_rejects_cross_org_stage(authed_client, db, test_org):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other reporting tenant",
        slug=f"other-reporting-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, other_org.id, "egg")
    db.commit()

    response = await authed_client.post(
        "/integrations/zapier/settings/outbound",
        json={
            "donor_outbound_enabled": True,
            "donor_event_mapping": [
                {
                    "donor_type": "egg",
                    "pipeline_id": str(pipeline.id),
                    "stage_id": str(ready_stage.id),
                    "event_name": "Qualified",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "selected donor pipeline" in response.json()["detail"]


def test_applied_donor_stage_queues_one_minimal_meta_payload(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    meta_lead = _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )

    result = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    history = result["history"]
    assert history is not None
    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == history.id)
        .one()
    )
    job = db.query(Job).filter(Job.id == event.job_id).one()
    payload = job.payload["data"]
    assert "url" not in job.payload
    assert "headers" not in job.payload
    assert event.event_id == f"zapier_donor_stage:{history.id}"
    assert job.idempotency_key == event.event_id
    assert payload["lead_id"] == meta_lead.meta_lead_id
    assert payload["event_name"] == "Qualified"
    assert payload["meta_form_id"] == meta_lead.meta_form_id
    assert payload["meta_page_id"] == meta_lead.meta_page_id
    for excluded_key in (
        "meta_ad_id",
        "meta_adset_id",
        "meta_campaign_id",
        "ad_id",
        "adset_id",
        "campaign_id",
        "fbc",
        "fbp",
        "fbclid",
    ):
        assert excluded_key not in payload
    assert set(payload["user_data"]) == {"email_hash", "phone_hash"}
    serialized = str(payload)
    for forbidden in (
        donor.full_name,
        donor.email,
        donor.phone,
        "medical_condition",
        "must-not-leak",
        "sensitive-ad-answer",
        "sensitive-campaign-answer",
        "sensitive-fbc-answer",
        "sensitive-nested-meta-ad",
        "sensitive-nested-meta-adset",
        "sensitive-nested-meta-campaign",
        "sensitive-nested-meta-fbc",
        ready_stage.label,
        "egg",
    ):
        assert forbidden not in serialized

    duplicate = zapier_outbound_service.enqueue_donor_stage_event(
        db,
        donor=donor,
        history=history,
        new_stage=ready_stage,
    )
    assert duplicate["reason"] == "duplicate"
    assert (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == history.id)
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_dispatch_uses_positive_payload_allowlist(db, test_org, test_user, monkeypatch):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    job = db.query(Job).filter(Job.organization_id == test_org.id).one()
    tampered_payload = dict(job.payload)
    tampered_data = dict(tampered_payload["data"])
    tampered_data["health_answer"] = "must-not-send"
    tampered_data["stage_label"] = "must-not-send"
    tampered_data["user_data"] = dict(tampered_data["user_data"]) | {
        "raw_email": "must-not-send@example.com"
    }
    tampered_payload["data"] = tampered_data
    job.payload = tampered_payload
    db.commit()

    sent: dict[str, object] = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            sent.update({"url": url, "json": json, "headers": headers})
            return Response()

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", Client)
    await zapier_handler.process_zapier_stage_event(db, job)

    sent_payload = sent["json"]
    assert isinstance(sent_payload, dict)
    assert "health_answer" not in sent_payload
    assert "stage_label" not in sent_payload
    assert "raw_email" not in sent_payload["user_data"]
    assert set(sent_payload["user_data"]) == {"email_hash", "phone_hash"}


def test_website_donor_uses_first_party_submission_not_meta_lead_id(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "sperm")
    donor = _create_donor(db, test_org.id, test_user.id, "sperm")
    form = Form(
        organization_id=test_org.id,
        name="Hosted donor form",
        status="published",
        purpose="shared_intake",
        lead_kind="sperm_donor",
    )
    db.add(form)
    db.flush()
    link = FormIntakeLink(
        organization_id=test_org.id,
        form_id=form.id,
        slug=f"hosted-{uuid.uuid4().hex[:8]}",
    )
    db.add(link)
    db.flush()
    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        donor_id=donor.id,
        intake_link_id=link.id,
        lead_kind="sperm_donor",
        answers_json={"medical_answer": "must-not-leak"},
    )
    db.add(submission)
    db.flush()
    db.add(
        LeadAttribution(
            organization_id=test_org.id,
            form_submission_id=submission.id,
            intake_link_id=link.id,
            source_surface="hosted_intake",
            source="meta",
            campaign="website-campaign",
            campaign_id="campaign-website-1",
            fbc="fb.1.1772942400.website-click",
        )
    )
    db.commit()
    _configure_reporting(
        db,
        test_org.id,
        donor_type="sperm",
        pipeline=pipeline,
        stage=ready_stage,
    )

    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id, Job.job_type == JobType.ZAPIER_STAGE_EVENT.value
        )
        .one()
    )
    payload = job.payload["data"]
    assert payload["first_party_submission_id"] == str(submission.id)
    assert "lead_id" not in payload
    assert "facebook_lead_id" not in payload
    assert "medical_answer" not in str(payload)


def test_pending_and_rejected_donor_changes_do_not_enqueue_but_approved_change_does(
    db, test_org, test_user
):
    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=new_stage,
    )
    donor.stage_id = ready_stage.id
    donor.stage = ready_stage
    db.commit()

    first_pending = donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Return for review",
        user_role=Role.CASE_MANAGER,
        emit_workflow_events=False,
    )
    assert first_pending["status"] == "pending_approval"
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 0

    status_change_request_service.reject_request(
        db,
        first_pending["request_id"],
        test_org.id,
        test_user.id,
        Role.DEVELOPER,
        "Keep current stage",
    )
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 0

    second_pending = donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Approved correction",
        user_role=Role.CASE_MANAGER,
        emit_workflow_events=False,
    )
    status_change_request_service.approve_request(
        db,
        second_pending["request_id"],
        test_org.id,
        test_user.id,
        Role.DEVELOPER,
    )
    job = db.query(Job).filter(Job.organization_id == test_org.id).one()
    event = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job.id).one()
    history = (
        db.query(DonorStatusHistory)
        .filter(DonorStatusHistory.request_id == second_pending["request_id"])
        .one()
    )
    assert event.donor_status_history_id == history.id


def test_undo_records_history_but_does_not_queue_conversion(db, test_org, test_user):
    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
        event_name="Converted",
    )
    settings.donor_outbound_event_mapping = [
        *settings.donor_outbound_event_mapping,
        {
            "donor_type": "egg",
            "pipeline_id": str(pipeline.id),
            "stage_id": str(new_stage.id),
            "event_name": "Qualified",
            "enabled": True,
        },
    ]
    db.commit()

    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    undo = donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Undo accidental change",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    assert undo["history"] is not None and undo["history"].is_undo is True
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 1
    undo_event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == undo["history"].id)
        .one()
    )
    assert undo_event.status == "skipped"
    assert undo_event.reason == "donor_stage_undo"
    assert db.query(DonorStatusHistory).filter_by(donor_id=donor.id).count() == 3


def test_repeated_non_undo_stage_visits_get_distinct_occurrence_ids(db, test_org, test_user):
    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
        event_name="Converted",
    )
    settings.donor_outbound_event_mapping = [
        *settings.donor_outbound_event_mapping,
        {
            "donor_type": "egg",
            "pipeline_id": str(pipeline.id),
            "stage_id": str(new_stage.id),
            "event_name": "Qualified",
            "enabled": True,
        },
    ]
    db.commit()

    first = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    first["history"].recorded_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()
    second = donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Reviewed regression",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    third = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    assert second["history"].is_undo is False
    event_ids = {
        row.event_id
        for row in db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.donor_status_history_id.in_(
                [first["history"].id, second["history"].id, third["history"].id]
            )
        )
        .all()
    }
    assert len(event_ids) == 3
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 3


@pytest.mark.asyncio
async def test_dispatch_skips_donor_job_disabled_after_enqueue(
    db, test_org, test_user, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler
    from app.services import zapier_monitor_service

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    job = db.query(Job).filter(Job.organization_id == test_org.id).one()
    event = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job.id).one()
    settings.donor_outbound_enabled = False
    db.commit()

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Disabled donor delivery must not make an HTTP request")

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", UnexpectedClient)
    await zapier_handler.process_zapier_stage_event(db, job)
    db.refresh(event)
    assert event.status == "skipped"
    assert event.reason == "donor_dispatch_disabled"

    job.status = JobStatus.COMPLETED.value
    db.commit()
    zapier_monitor_service.mark_job_delivered(db=db, job_id=job.id, attempts=1)
    db.refresh(event)
    assert event.status == "skipped"


@pytest.mark.asyncio
async def test_donor_skip_persistence_failure_requeues_without_false_delivery(
    db, test_org, test_user, monkeypatch
):
    from sqlalchemy.orm import Session

    from app import worker
    from app.db.enums import IntegrationStatus, IntegrationType
    from app.jobs.handlers import zapier as zapier_handler
    from app.services import job_service, ops_service

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    job = db.query(Job).filter(Job.organization_id == test_org.id).one()
    event = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job.id).one()
    settings.donor_outbound_enabled = False
    db.commit()
    health = ops_service.record_error(
        db=db,
        org_id=test_org.id,
        integration_type=IntegrationType.ZAPIER,
        integration_key="outbound",
        error_message="existing Zapier failure",
    )
    event_id = event.id
    health_id = health.id
    prior_success_at = health.last_success_at

    worker_db = Session(
        bind=db.get_bind(),
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    claimed = job_service.claim_pending_jobs(
        worker_db,
        limit=1,
        job_types=[JobType.ZAPIER_STAGE_EVENT],
    )[0]
    job_id = claimed.id
    claim_token = claimed.claim_token
    retry_run_at = claimed.run_at
    original_commit = worker_db.commit
    commit_attempts = 0

    def fail_first_commit():
        nonlocal commit_attempts
        commit_attempts += 1
        if commit_attempts == 1:
            raise RuntimeError("simulated skip persistence failure")
        original_commit()

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Disabled donor delivery must not make an HTTP request")

    monkeypatch.setattr(worker_db, "commit", fail_first_commit)
    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", UnexpectedClient)

    try:
        with pytest.raises(RuntimeError, match="simulated skip persistence failure") as exc_info:
            await worker.process_job(worker_db, claimed)

        worker_db.rollback()
        retried = job_service.fail_claimed_job(
            worker_db,
            job_id=job_id,
            claim_token=claim_token,
            error=str(exc_info.value),
            retry_run_at=retry_run_at,
        )
        worker._record_job_failure(
            worker_db,
            retried,
            str(exc_info.value),
            exception=exc_info.value,
        )
    finally:
        worker_db.close()

    db.expire_all()
    retried_job = db.get(Job, job_id)
    event = db.get(ZapierOutboundEvent, event_id)
    health = db.get(type(health), health_id)
    assert retried_job is not None
    assert event is not None
    assert health is not None
    assert retried_job.status == JobStatus.PENDING.value
    assert event.status == "queued"
    assert event.delivered_at is None
    assert health.status == IntegrationStatus.ERROR.value
    assert health.last_success_at == prior_success_at


@pytest.mark.asyncio
@pytest.mark.parametrize("change_kind", ["destination", "event_name"])
async def test_dispatch_skips_donor_job_after_config_changes(
    db, test_org, test_user, monkeypatch, change_kind
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    job = db.query(Job).filter(Job.organization_id == test_org.id).one()
    event = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job.id).one()
    if change_kind == "destination":
        settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/changed/donor"
    else:
        settings.donor_outbound_event_mapping = [
            dict(settings.donor_outbound_event_mapping[0]) | {"event_name": "Converted"}
        ]
    db.commit()

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Changed donor configuration must not send an old event")

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", UnexpectedClient)
    await zapier_handler.process_zapier_stage_event(db, job)
    db.refresh(event)
    assert event.status == "skipped"
    assert event.reason == "donor_config_changed"


def test_delivery_job_failure_rolls_back_stage_history_and_audit(
    db, test_org, test_user, monkeypatch
):
    from sqlalchemy.orm import Session

    from app.db.models import AuditLog
    from app.services import job_service

    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    initial_history_count = db.query(DonorStatusHistory).filter_by(donor_id=donor.id).count()
    initial_audit_count = db.query(AuditLog).filter_by(target_id=donor.id).count()
    org_id = test_org.id
    donor_id = donor.id
    ready_stage_id = ready_stage.id
    user_id = test_user.id

    def fail_enqueue(*args, **kwargs):
        raise RuntimeError("simulated durable enqueue failure")

    monkeypatch.setattr(job_service, "enqueue_job", fail_enqueue)
    mutation_db = Session(
        bind=db.connection(),
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        mutation_donor = donor_service.get_donor(mutation_db, org_id, donor_id)
        assert mutation_donor is not None
        with pytest.raises(RuntimeError, match="durable enqueue failure"):
            donor_service.change_status(
                mutation_db,
                mutation_donor,
                ready_stage_id,
                user_id,
                user_role=Role.DEVELOPER,
                emit_workflow_events=False,
            )
    finally:
        mutation_db.close()

    db.expire_all()
    restored = donor_service.get_donor(db, org_id, donor_id)
    assert restored is not None and restored.stage_id == new_stage.id
    assert (
        db.query(DonorStatusHistory).filter_by(donor_id=donor_id).count() == initial_history_count
    )
    assert db.query(AuditLog).filter_by(target_id=donor_id).count() == initial_audit_count
    assert db.query(ZapierOutboundEvent).filter_by(donor_id=donor_id).count() == 0
