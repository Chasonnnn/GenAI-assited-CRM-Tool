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


def _attach_meta_lead(db, donor, *, org_id=None, meta_lead_id=None, meta_created_time=None):
    lead = MetaLead(
        organization_id=org_id or donor.organization_id,
        meta_lead_id=meta_lead_id or f"meta-{uuid.uuid4().hex}",
        meta_created_time=meta_created_time,
        meta_form_id="meta-form-1",
        meta_page_id="meta-page-1",
        field_data_raw={
            "email": "must-not-leak@example.com",
            "medical_condition": "must-not-leak",
            # Tracking keys written by the Zapier inbound handler, read like surrogate leads.
            "meta_ad_id": "ad-123",
            "meta_ad_name": "Donor ad",
            "meta_adset_id": "adset-123",
            "meta_adset_name": "Donor ad set",
            "meta_campaign_id": "campaign-123",
            "meta_campaign_name": "Donor campaign",
            "meta_platform": "facebook",
            "fbc": "fb.1.1772942400.meta-donor-click",
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
    assert event.event_id == f"zapier_donor:{donor.id}:qualified"
    assert payload["event_id"] == event.event_id
    assert job.idempotency_key == f"zapier_donor_stage:{history.id}"
    assert payload["lead_id"] == meta_lead.meta_lead_id
    assert payload["event_name"] == "Qualified"
    assert payload["record_type"] == "egg_donor"
    assert payload["meta_form_id"] == meta_lead.meta_form_id
    assert payload["meta_page_id"] == meta_lead.meta_page_id
    assert payload["meta_ad_id"] == "ad-123"
    assert payload["meta_ad_name"] == "Donor ad"
    assert payload["meta_adset_id"] == "adset-123"
    assert payload["meta_adset_name"] == "Donor ad set"
    assert payload["meta_campaign_id"] == "campaign-123"
    assert payload["meta_campaign_name"] == "Donor campaign"
    assert payload["meta_platform"] == "facebook"
    assert payload["fbc"] == "fb.1.1772942400.meta-donor-click"
    assert payload["facebook_click_id"] == "fb.1.1772942400.meta-donor-click"
    for excluded_key in ("ad_id", "adset_id", "campaign_id", "fbp", "fbclid"):
        assert excluded_key not in payload
    # Hashed PII on: the same contact fields surrogate payloads carry.
    assert payload["customer_email"] == donor.email
    assert payload["customer_phone_number"] == donor.phone
    assert set(payload["user_data"]) == {"email_hash", "phone_hash"}
    serialized = str(payload)
    for forbidden in (
        donor.full_name,
        "medical_condition",
        "must-not-leak",
        "sensitive-nested-meta-ad",
        "sensitive-nested-meta-adset",
        "sensitive-nested-meta-campaign",
        "sensitive-nested-meta-fbc",
        ready_stage.label,
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


def test_donor_payload_hashes_meta_normalized_phone_and_skips_placeholder_email(
    db, test_org, test_user
):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    donor.email = "meta-1234567890abcdef@placeholder.invalid"
    db.commit()
    _attach_meta_lead(db, donor)
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

    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == result["history"].id)
        .one()
    )
    payload = db.get(Job, event.job_id).payload["data"]
    # sha256("16075550102"): digits with country code and no "+", as Meta expects.
    assert payload["user_data"] == {
        "phone_hash": "7515397f91001442b8a497e2562bc8e7ee3c914396f7da402a59cc40f66dd0d1"
    }
    assert "placeholder" not in str(payload)


@pytest.mark.parametrize(
    ("lead_kwargs", "reason"),
    [
        ({"meta_lead_id": f"zapier-{uuid.uuid4()}"}, "synthetic_meta_lead_id"),
        (
            {"meta_created_time": datetime.now(UTC) - timedelta(days=91)},
            "stale_meta_lead",
        ),
    ],
    ids=["synthetic-lead-id", "older-than-90-days"],
)
def test_meta_donor_events_skip_unreportable_leads_like_surrogates(
    db, test_org, test_user, lead_kwargs, reason
):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor, **lead_kwargs)
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

    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == result["history"].id)
        .one()
    )
    assert event.status == "skipped"
    assert event.reason == reason
    assert event.job_id is None
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 0


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
    assert sent_payload["record_type"] == "egg_donor"
    assert sent_payload["customer_email"] == donor.email
    assert sent_payload["customer_phone_number"] == donor.phone
    assert sent_payload["meta_ad_id"] == "ad-123"


@pytest.mark.asyncio
async def test_dispatch_drops_contact_fields_when_hashed_pii_turned_off(
    db, test_org, test_user, monkeypatch
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
    assert job.payload["data"]["customer_email"] == donor.email
    settings.outbound_send_hashed_pii = False
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
            sent.update({"json": json})
            return Response()

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", Client)
    await zapier_handler.process_zapier_stage_event(db, job)

    sent_payload = sent["json"]
    assert isinstance(sent_payload, dict)
    for contact_key in ("customer_email", "customer_phone_number", "user_data"):
        assert contact_key not in sent_payload
    assert sent_payload["lead_id"] == job.payload["data"]["lead_id"]


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
    assert payload["record_type"] == "sperm_donor"
    assert payload["attribution_source"] == "website"
    assert "lead_id" not in payload
    assert "facebook_lead_id" not in payload
    assert "medical_answer" not in str(payload)


def test_backdated_donor_change_reports_its_effective_time(db, test_org, test_user):
    # Surrogate stage events send the backdated effective time unchanged; donors match.
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    now = datetime.now(UTC)
    donor.created_at = now - timedelta(days=5)
    db.commit()
    _attach_meta_lead(db, donor, meta_created_time=now - timedelta(days=5))
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
    )
    effective_at = (now - timedelta(days=2)).replace(hour=15, minute=30, second=0, microsecond=0)

    result = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        reason="Recorded late",
        effective_at=effective_at,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    history = result["history"]
    assert history.effective_at == effective_at
    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == history.id)
        .one()
    )
    assert event.status == "queued"
    payload = db.get(Job, event.job_id).payload["data"]
    assert payload["event_time"] == effective_at.isoformat()


def _hosted_submission(db, org_id, donor, *, submitted_at, fbc=None):
    form = Form(
        organization_id=org_id,
        name=f"Hosted donor form {uuid.uuid4().hex[:6]}",
        status="published",
        purpose="shared_intake",
        lead_kind="egg_donor",
    )
    db.add(form)
    db.flush()
    link = FormIntakeLink(
        organization_id=org_id,
        form_id=form.id,
        slug=f"hosted-{uuid.uuid4().hex[:8]}",
    )
    db.add(link)
    db.flush()
    submission = FormSubmission(
        organization_id=org_id,
        form_id=form.id,
        donor_id=donor.id,
        intake_link_id=link.id,
        lead_kind="egg_donor",
        answers_json={},
        submitted_at=submitted_at,
    )
    db.add(submission)
    db.flush()
    if fbc:
        db.add(
            LeadAttribution(
                organization_id=org_id,
                form_submission_id=submission.id,
                intake_link_id=link.id,
                source_surface="hosted_intake",
                source="meta",
                fbc=fbc,
            )
        )
    db.commit()
    return submission


def test_website_donor_uses_latest_attributed_submission(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    now = datetime.now(UTC)
    _hosted_submission(
        db, test_org.id, donor, submitted_at=now - timedelta(days=3), fbc="fb.1.1.first-click"
    )
    attributed = _hosted_submission(
        db, test_org.id, donor, submitted_at=now - timedelta(days=2), fbc="fb.1.2.second-click"
    )
    _hosted_submission(db, test_org.id, donor, submitted_at=now - timedelta(days=1))
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

    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == result["history"].id)
        .one()
    )
    assert event.first_party_submission_id == attributed.id
    payload = db.get(Job, event.job_id).payload["data"]
    assert payload["first_party_submission_id"] == str(attributed.id)
    assert payload["fbc"] == "fb.1.2.second-click"


def test_website_donor_without_attribution_uses_latest_submission(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    now = datetime.now(UTC)
    _hosted_submission(db, test_org.id, donor, submitted_at=now - timedelta(days=2))
    latest = _hosted_submission(db, test_org.id, donor, submitted_at=now - timedelta(days=1))
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

    event = (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == result["history"].id)
        .one()
    )
    assert event.first_party_submission_id == latest.id
    assert event.status == "queued"


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


def _history_event(db, history):
    return (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.donor_status_history_id == history.id)
        .one()
    )


def _add_stage(db, pipeline, *, stage_key, stage_type, order, label=None):
    stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        stage_key=stage_key,
        slug=stage_key.replace("_", "-"),
        label=label or stage_key.replace("_", " ").title(),
        color="#64748B",
        stage_type=stage_type,
        order=order,
        is_active=True,
        is_intake_stage=False,
    )
    db.add(stage)
    db.flush()
    return stage


def _add_mapping(db, settings, pipeline, stage, event_name):
    settings.donor_outbound_event_mapping = [
        *settings.donor_outbound_event_mapping,
        {
            "donor_type": "egg",
            "pipeline_id": str(pipeline.id),
            "stage_id": str(stage.id),
            "event_name": event_name,
            "enabled": True,
        },
    ]
    db.commit()


@pytest.mark.asyncio
async def test_undo_withdraws_the_undone_event_before_dispatch(
    db, test_org, test_user, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
        event_name="Converted",
    )

    forward = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Undo accidental change",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    forward_event = _history_event(db, forward["history"])
    assert forward_event.status == "skipped"
    assert forward_event.reason == "donor_stage_undone"

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("An undone donor event must not be sent")

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", UnexpectedClient)
    await zapier_handler.process_zapier_stage_event(db, db.get(Job, forward_event.job_id))
    db.refresh(forward_event)
    assert forward_event.status == "skipped"
    assert forward_event.reason == "donor_stage_undone"

    # Nothing reached Meta, so the next real entry is still the first Converted event.
    reentry = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    reentry_event = _history_event(db, reentry["history"])
    assert reentry_event.status == "queued"
    assert reentry_event.event_id == forward_event.event_id


def test_undo_keeps_an_event_already_claimed_for_delivery(db, test_org, test_user):
    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
        event_name="Converted",
    )
    forward = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    forward_event = _history_event(db, forward["history"])
    job = db.get(Job, forward_event.job_id)
    job.status = JobStatus.RUNNING.value
    db.commit()

    undo = donor_service.change_status(
        db,
        donor,
        new_stage.id,
        test_user.id,
        reason="Undo accidental change",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    assert undo["history"].is_undo is True
    db.refresh(forward_event)
    assert forward_event.status == "queued"
    assert forward_event.reason is None


def test_repeated_stage_visit_reports_the_event_once(db, test_org, test_user):
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
    _add_mapping(db, settings, pipeline, new_stage, "Qualified")

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
    first_event = _history_event(db, first["history"])
    second_event = _history_event(db, second["history"])
    third_event = _history_event(db, third["history"])
    assert first_event.status == "queued"
    assert second_event.status == "queued"
    assert third_event.status == "skipped"
    assert third_event.reason == "duplicate"
    assert third_event.event_id == first_event.event_id == f"zapier_donor:{donor.id}:converted"
    assert third_event.job_id is None
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 2


def test_two_stages_mapped_to_one_event_report_it_once(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    matched_stage = _add_stage(
        db, pipeline, stage_key="cycle_in_progress", stage_type="post_approval", order=3
    )
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
    _add_mapping(db, settings, pipeline, matched_stage, "Converted")

    first = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    second = donor_service.change_status(
        db,
        donor,
        matched_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    assert _history_event(db, first["history"]).status == "queued"
    second_event = _history_event(db, second["history"])
    assert second_event.status == "skipped"
    assert second_event.reason == "duplicate"
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 1


def test_resuming_from_on_hold_does_not_resend_the_event(db, test_org, test_user):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    on_hold_stage = _add_stage(db, pipeline, stage_key="on_hold", stage_type="paused", order=4)
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage,
        event_name="Converted",
    )

    first = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    donor_service.change_status(
        db,
        donor,
        on_hold_stage.id,
        test_user.id,
        reason="Travelling",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    db.query(DonorStatusHistory).filter_by(donor_id=donor.id).update(
        {DonorStatusHistory.recorded_at: datetime.now(UTC) - timedelta(minutes=10)}
    )
    db.commit()
    resumed = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        reason="Back from travel",
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    assert resumed["history"].is_undo is False
    assert _history_event(db, first["history"]).status == "queued"
    resumed_event = _history_event(db, resumed["history"])
    assert resumed_event.status == "skipped"
    assert resumed_event.reason == "duplicate"
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 1


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


META_DONOR_MAPPING_RULES = [
    {
        "csv_column": column,
        "surrogate_field": field,
        "transformation": None,
        "action": "map",
        "custom_field_key": None,
    }
    for column, field in (
        ("full_name", "full_name"),
        ("email", "email"),
        ("phone_number", "phone"),
    )
]


@pytest.fixture
def donor_storage(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)


def _creation_events(db, org_id):
    return (
        db.query(ZapierOutboundEvent)
        .join(
            DonorStatusHistory,
            DonorStatusHistory.id == ZapierOutboundEvent.donor_status_history_id,
        )
        .filter(
            ZapierOutboundEvent.organization_id == org_id,
            DonorStatusHistory.old_stage_id.is_(None),
        )
        .all()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
async def test_website_donor_creation_reports_mapped_entry_stage(
    authed_client, db, test_org, donor_storage, donor_type
):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote
    from app.services import form_intake_service
    from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form

    pipeline, new_stage, _ready_stage = _seed_donor_pipeline(db, test_org.id, donor_type)
    _configure_reporting(
        db,
        test_org.id,
        donor_type=donor_type,
        pipeline=pipeline,
        stage=new_stage,
        event_name="Lead",
    )
    _, slug = await _create_donor_form(authed_client, lead_kind=f"{donor_type}_donor")
    response = await _submit_donor_form(
        authed_client, slug=slug, email=f"website-{donor_type}@example.com"
    )
    assert response.status_code == 200, response.text
    submission = db.query(FormSubmission).filter_by(id=uuid.UUID(response.json()["id"])).one()
    db.add(
        LeadAttribution(
            organization_id=test_org.id,
            form_submission_id=submission.id,
            intake_link_id=submission.intake_link_id,
            source_surface="hosted_intake",
            source="meta",
            fbc="fb.1.1772942400.website-click",
        )
    )
    db.commit()
    form_intake_service.auto_match_submission(db, submission=submission)
    form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, source="website", auto_promote=True
    )
    promote_job = (
        db.query(Job).filter_by(organization_id=test_org.id, job_type="donor_intake_promote").one()
    )

    await process_donor_intake_promote(db, promote_job)

    db.refresh(submission)
    assert submission.donor_id is not None
    events = _creation_events(db, test_org.id)
    assert len(events) == 1
    event = events[0]
    assert event.status == "queued"
    assert event.donor_id == submission.donor_id
    assert event.stage_id == new_stage.id
    assert event.event_name == "Lead"
    assert event.attribution_source == "website"
    assert event.first_party_submission_id == submission.id
    payload = db.get(Job, event.job_id).payload["data"]
    assert payload["event_name"] == "Lead"
    assert payload["record_type"] == f"{donor_type}_donor"
    assert payload["fbc"] == "fb.1.1772942400.website-click"


@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
def test_meta_donor_conversion_reports_mapped_entry_stage(db, test_org, donor_type):
    from app.services import meta_lead_service

    pipeline, new_stage, _ready_stage = _seed_donor_pipeline(db, test_org.id, donor_type)
    _configure_reporting(
        db,
        test_org.id,
        donor_type=donor_type,
        pipeline=pipeline,
        stage=new_stage,
        event_name="Lead",
    )
    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=f"{donor_type}-lead-1001",
        meta_form_id="meta-form-1",
        meta_page_id="meta-page-1",
        field_data_raw={
            "full_name": "Meta Donor",
            "email": f"meta-{donor_type}@example.com",
            "phone_number": "+1 607 555 0198",
        },
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.commit()

    donor, error = meta_lead_service.convert_to_donor_with_mapping(
        db, lead, META_DONOR_MAPPING_RULES, donor_type=donor_type
    )

    assert error is None
    events = _creation_events(db, test_org.id)
    assert len(events) == 1
    event = events[0]
    assert (event.status, event.reason) == ("queued", None)
    assert event.donor_id == donor.id
    assert event.event_name == "Lead"
    assert event.attribution_source == "meta"
    assert event.lead_id == f"{donor_type}-lead-1001"
    payload = db.get(Job, event.job_id).payload["data"]
    assert payload["lead_id"] == f"{donor_type}-lead-1001"
    assert payload["record_type"] == f"{donor_type}_donor"


@pytest.mark.parametrize("mapping_state", ["unmapped", "disabled"])
def test_donor_creation_skips_when_entry_stage_is_not_reported(db, test_org, mapping_state):
    from app.services import meta_lead_service

    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    settings = _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=ready_stage if mapping_state == "unmapped" else new_stage,
        event_name="Lead",
    )
    if mapping_state == "disabled":
        settings.donor_outbound_event_mapping = [
            {**settings.donor_outbound_event_mapping[0], "enabled": False}
        ]
        db.commit()
    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="egg-lead-2002",
        meta_form_id="meta-form-1",
        meta_page_id="meta-page-1",
        field_data_raw={"full_name": "Meta Donor", "email": "meta-unmapped@example.com"},
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.commit()

    donor, error = meta_lead_service.convert_to_donor_with_mapping(
        db, lead, META_DONOR_MAPPING_RULES, donor_type="egg"
    )

    assert error is None
    assert donor is not None
    events = _creation_events(db, test_org.id)
    assert [(event.status, event.reason, event.job_id) for event in events] == [
        ("skipped", "unmapped_donor_stage", None)
    ]


def test_manual_donor_creation_sends_nothing(db, test_org, test_user):
    pipeline, new_stage, _ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    _configure_reporting(
        db,
        test_org.id,
        donor_type="egg",
        pipeline=pipeline,
        stage=new_stage,
        event_name="Lead",
    )

    _create_donor(db, test_org.id, test_user.id)

    assert db.query(ZapierOutboundEvent).filter_by(organization_id=test_org.id).count() == 0


def _capture_webhook(monkeypatch, zapier_handler):
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
    return sent


@pytest.mark.asyncio
async def test_donor_test_event_sends_a_meta_sample_through_the_donor_worker(
    authed_client, db, test_org, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "sperm")
    settings = _configure_reporting(
        db, test_org.id, donor_type="sperm", pipeline=pipeline, stage=ready_stage
    )
    settings.outbound_webhook_secret_encrypted = zapier_settings_service.encrypt_secret(
        "donor-test-secret"
    )
    db.commit()

    response = await authed_client.post(
        "/integrations/zapier/test-outbound/donor",
        json={
            "donor_type": "sperm",
            "event_name": "Qualified",
            "attribution_source": "meta",
            "lead_id": "real-meta-lead-1",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["event_name"] == "Qualified"
    assert body["lead_id"] == "real-meta-lead-1"
    event = (
        db.query(ZapierOutboundEvent)
        .filter_by(organization_id=test_org.id, event_id=body["event_id"])
        .one()
    )
    assert (event.source, event.status, event.donor_type) == ("test", "queued", "sperm")
    assert event.attribution_source == "meta"
    job = db.get(Job, event.job_id)
    assert job.organization_id == test_org.id
    assert job.payload["delivery_kind"] == "donor_test"
    assert "headers" not in job.payload
    assert "url" not in job.payload

    sent = _capture_webhook(monkeypatch, zapier_handler)
    await zapier_handler.process_zapier_stage_event(db, job)

    payload = sent["json"]
    assert sent["url"] == settings.outbound_webhook_url
    assert sent["headers"] == {"X-Webhook-Token": "donor-test-secret"}
    assert payload["test_mode"] is True
    assert payload["record_type"] == "sperm_donor"
    assert payload["event_name"] == "Qualified"
    assert payload["attribution_source"] == "meta"
    assert payload["lead_id"] == "real-meta-lead-1"
    assert payload["fbc"]
    assert set(payload["user_data"]) == {"email_hash", "phone_hash"}


@pytest.mark.asyncio
async def test_donor_test_event_sends_a_website_sample_without_a_lead_id(
    authed_client, db, test_org, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    settings = _configure_reporting(
        db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage
    )
    settings.outbound_send_hashed_pii = False
    db.commit()

    response = await authed_client.post(
        "/integrations/zapier/test-outbound/donor",
        json={"donor_type": "egg", "event_name": "Lead", "attribution_source": "website"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["lead_id"] is None
    event = (
        db.query(ZapierOutboundEvent)
        .filter_by(organization_id=test_org.id, event_id=response.json()["event_id"])
        .one()
    )
    sent = _capture_webhook(monkeypatch, zapier_handler)
    await zapier_handler.process_zapier_stage_event(db, db.get(Job, event.job_id))

    payload = sent["json"]
    assert payload["attribution_source"] == "website"
    assert payload["record_type"] == "egg_donor"
    assert payload["first_party_submission_id"]
    assert payload["fbc"]
    for absent in ("lead_id", "facebook_lead_id", "customer_email", "user_data"):
        assert absent not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configure", "detail"),
    [
        ("no_webhook", "Outbound webhook URL not configured."),
        ("donor_disabled", "Donor stage events are disabled."),
    ],
)
async def test_donor_test_event_requires_donor_reporting_setup(
    authed_client, db, test_org, configure, detail
):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    settings = _configure_reporting(
        db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage
    )
    if configure == "no_webhook":
        settings.outbound_webhook_url = None
    else:
        settings.donor_outbound_enabled = False
    db.commit()

    response = await authed_client.post(
        "/integrations/zapier/test-outbound/donor",
        json={"donor_type": "egg", "event_name": "Lead", "attribution_source": "meta"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == detail
    assert db.query(ZapierOutboundEvent).filter_by(organization_id=test_org.id).count() == 0


@pytest.mark.asyncio
async def test_donor_test_event_rejects_unsupported_event_names(authed_client, db, test_org):
    response = await authed_client.post(
        "/integrations/zapier/test-outbound/donor",
        json={"donor_type": "egg", "event_name": "Purchase", "attribution_source": "meta"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_donor_test_job_skips_when_donor_reporting_is_disabled_before_dispatch(
    authed_client, db, test_org, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    settings = _configure_reporting(
        db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage
    )
    response = await authed_client.post(
        "/integrations/zapier/test-outbound/donor",
        json={"donor_type": "egg", "event_name": "Lead", "attribution_source": "meta"},
    )
    assert response.status_code == 200, response.text
    event = (
        db.query(ZapierOutboundEvent)
        .filter_by(organization_id=test_org.id, event_id=response.json()["event_id"])
        .one()
    )
    settings.donor_outbound_enabled = False
    db.commit()

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A disabled donor test must not be sent")

    monkeypatch.setattr(zapier_handler.httpx, "AsyncClient", UnexpectedClient)
    await zapier_handler.process_zapier_stage_event(db, db.get(Job, event.job_id))

    db.refresh(event)
    assert (event.status, event.reason) == ("skipped", "donor_dispatch_disabled")
