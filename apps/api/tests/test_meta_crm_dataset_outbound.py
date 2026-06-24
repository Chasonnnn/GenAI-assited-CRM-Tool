"""Tests for direct Meta CRM dataset outbound events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest


def _create_form_submission_for_meta_event(db, org_id):
    from app.db.enums import FormSubmissionMatchStatus, FormSubmissionStatus, FormStatus
    from app.db.models import Form, FormSubmission

    form = Form(
        id=uuid4(),
        organization_id=org_id,
        name=f"Meta Website Lead Form {uuid4().hex[:6]}",
        status=FormStatus.PUBLISHED.value,
        published_schema_json={"pages": []},
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        id=uuid4(),
        organization_id=org_id,
        form_id=form.id,
        answers_json={},
        schema_snapshot={},
        source_mode="shared",
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        match_status=FormSubmissionMatchStatus.WORKFLOW_PENDING.value,
        match_reason="workflow_pending",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    db.flush()
    return submission.id


@pytest.mark.asyncio
async def test_meta_crm_dataset_settings_update(authed_client):
    payload = {
        "dataset_id": "1428122951556949",
        "access_token": "meta-dataset-token",
        "enabled": True,
        "crm_name": "Surrogacy Force CRM",
        "send_hashed_pii": True,
        "test_event_code": "TEST123",
        "event_mapping": [
            {"stage_key": "new_unread", "event_name": "Lead", "enabled": True},
            {
                "stage_key": "pre_qualified",
                "event_name": "Qualified",
                "bucket": "qualified",
                "enabled": True,
            },
        ],
    }

    res = await authed_client.patch("/integrations/meta/crm-dataset/settings", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert data["dataset_id"] == payload["dataset_id"]
    assert data["access_token_configured"] is True
    assert data["crm_name"] == "Surrogacy Force CRM"
    assert data["send_hashed_pii"] is True
    assert data["test_event_code"] == "TEST123"
    by_stage = {item["stage_key"]: item for item in data["event_mapping"]}
    assert by_stage["new_unread"]["event_name"] == "Lead"
    assert by_stage["new_unread"]["enabled"] is True
    assert by_stage["new_unread"]["bucket"] is None
    assert by_stage["contacted"]["event_name"] == ""
    assert by_stage["contacted"]["enabled"] is False
    assert by_stage["contacted"]["bucket"] is None

    res2 = await authed_client.get("/integrations/meta/crm-dataset/settings")
    assert res2.status_code == 200
    settings = res2.json()
    assert settings["enabled"] is True
    assert settings["dataset_id"] == payload["dataset_id"]
    assert settings["access_token_configured"] is True
    assert settings["crm_name"] == "Surrogacy Force CRM"
    assert settings["send_hashed_pii"] is True
    assert settings["test_event_code"] == "TEST123"


@pytest.mark.asyncio
async def test_meta_crm_dataset_test_event_queues_job(authed_client, db, test_org):
    from app.db.enums import JobType
    from app.db.models import Job
    from app.services import meta_crm_dataset_settings_service

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.crm_name = "Surrogacy Force CRM"
    settings.test_event_code = "TEST-EVENT-CODE"
    settings.event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "enabled": True}
    ]
    db.commit()

    res = await authed_client.post(
        "/integrations/meta/crm-dataset/test-outbound",
        json={
            "stage_key": "pre_qualified",
            "lead_id": "1559954882011881",
            "fbc": "fb.1.1772942400.test-click-id",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert data["event_name"] == "Qualified"
    assert data["lead_id"] == "1559954882011881"

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["dataset_id"] == "1428122951556949"
    assert "access_token" not in job.payload
    assert job.payload["body"]["test_event_code"] == "TEST-EVENT-CODE"
    event_data = job.payload["body"]["data"][0]
    assert event_data["event_name"] == "Qualified"
    assert event_data["custom_data"]["event_source"] == "crm"
    assert event_data["custom_data"]["lead_event_source"] == "Surrogacy Force CRM"
    assert event_data["user_data"]["lead_id"] == "1559954882011881"
    assert event_data["user_data"]["fbc"] == "fb.1.1772942400.test-click-id"


def test_build_meta_crm_dataset_payload_uses_crm_shape():
    from app.services import meta_crm_dataset_service

    event_time = datetime(2026, 3, 8, 4, 0, 0, tzinfo=timezone.utc)
    payload = meta_crm_dataset_service.build_stage_event_payload(
        lead_id="1559954882011881",
        event_name="Qualified",
        event_time=event_time,
        crm_name="Surrogacy Force CRM",
        include_hashed_pii=True,
        email="Lead@example.com",
        phone="+1 (555) 123-4567",
        fbc="fb.1.1772942400.test-click-id",
        event_id="meta-crm-event-1",
        test_event_code="TEST123",
    )

    assert payload["test_event_code"] == "TEST123"
    event_data = payload["data"][0]
    assert event_data["event_name"] == "Qualified"
    assert event_data["event_time"] == int(event_time.timestamp())
    assert event_data["action_source"] == "system_generated"
    assert event_data["event_id"] == "meta-crm-event-1"
    assert event_data["custom_data"] == {
        "event_source": "crm",
        "lead_event_source": "Surrogacy Force CRM",
    }
    assert event_data["user_data"]["lead_id"] == "1559954882011881"
    assert event_data["user_data"]["fbc"] == "fb.1.1772942400.test-click-id"
    assert event_data["user_data"]["em"]
    assert event_data["user_data"]["ph"]


def test_build_meta_crm_dataset_payload_ignores_invalid_click_ids():
    from app.services import meta_crm_dataset_service

    payload = meta_crm_dataset_service.build_stage_event_payload(
        lead_id="1559954882011881",
        event_name="Lead",
        event_time=datetime(2026, 3, 8, 4, 0, 0, tzinfo=timezone.utc),
        crm_name="Surrogacy Force CRM",
        include_hashed_pii=False,
        email=None,
        phone=None,
        fbc="not-a-meta-fbc",
    )

    assert "fbc" not in payload["data"][0]["user_data"]


def test_build_website_lead_payload_uses_website_shape_without_sensitive_fields():
    from app.services import meta_crm_dataset_service

    event_time = datetime(2026, 3, 8, 4, 0, 0, tzinfo=timezone.utc)
    payload = meta_crm_dataset_service.build_website_lead_event_payload(
        event_time=event_time,
        event_source_url="https://ewi-surrogacy.com",
        include_hashed_pii=True,
        email="Lead@example.com",
        phone="+1 (555) 123-4567",
        fbc="fb.1.1772942400.test-click-id",
        fbp="fb.1.1772942400.browser-id",
        event_id="sf_lead_submission-1",
        source="meta",
        campaign="spring-surrogate",
        test_event_code="TEST123",
    )

    assert payload["test_event_code"] == "TEST123"
    event_data = payload["data"][0]
    assert event_data["event_name"] == "Lead"
    assert event_data["event_time"] == int(event_time.timestamp())
    assert event_data["event_id"] == "sf_lead_submission-1"
    assert event_data["action_source"] == "website"
    assert event_data["event_source_url"] == "https://ewi-surrogacy.com"
    assert event_data["custom_data"] == {
        "content_name": "lead_capture",
        "content_category": "intake",
        "event_source": "website",
        "source": "meta",
        "campaign": "spring-surrogate",
    }
    user_data = event_data["user_data"]
    assert user_data["fbc"] == "fb.1.1772942400.test-click-id"
    assert user_data["fbp"] == "fb.1.1772942400.browser-id"
    assert user_data["em"]
    assert user_data["ph"]
    assert "fn" not in user_data
    assert "ln" not in user_data
    assert "answers" not in event_data
    assert "height" not in str(event_data).lower()
    assert "weight" not in str(event_data).lower()


def test_enqueue_website_lead_event_skips_without_match_keys(db, test_org):
    from app.db.enums import JobType
    from app.db.models import Job, MetaCrmDatasetEvent
    from app.services import meta_crm_dataset_service, meta_crm_dataset_settings_service

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.send_hashed_pii = False
    db.commit()

    submission_id = _create_form_submission_for_meta_event(db, test_org.id)
    result = meta_crm_dataset_service.enqueue_website_lead_event(
        db,
        organization_id=test_org.id,
        lead_id="intake-lead-1",
        submission_id=submission_id,
        event_source_url="https://ewi-surrogacy.com",
        attribution={},
        email="lead@example.com",
        phone="+1 (555) 123-4567",
    )

    assert result["queued"] is False
    assert result["reason"] == "missing_user_data"
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .first()
        is None
    )
    monitor_event = (
        db.query(MetaCrmDatasetEvent)
        .filter(MetaCrmDatasetEvent.event_id == f"sf_lead_{submission_id}")
        .one()
    )
    assert monitor_event.status == "skipped"
    assert monitor_event.reason == "missing_user_data"


def test_enqueue_website_lead_event_is_submission_owned_and_can_attach_lead_later(
    db, test_org
):
    from app.db.enums import JobType
    from app.db.models import Job, MetaCrmDatasetEvent
    from app.services import (
        meta_crm_dataset_monitor_service,
        meta_crm_dataset_service,
        meta_crm_dataset_settings_service,
    )

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.send_hashed_pii = True
    db.commit()

    submission_id = _create_form_submission_for_meta_event(db, test_org.id)
    intake_lead_id = uuid4()
    result = meta_crm_dataset_service.enqueue_website_lead_event(
        db,
        organization_id=test_org.id,
        submission_id=submission_id,
        intake_lead_id=None,
        event_source_url="https://ewi-surrogacy.com",
        attribution={"fbc": "fb.1.1772942400.test-click"},
        email="lead@example.com",
        phone=None,
    )

    assert result["queued"] is True
    assert result["event_id"] == f"sf_lead_{submission_id}"
    assert result["lead_id"] is None

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .one()
    )
    event_data = job.payload["body"]["data"][0]
    assert event_data["event_id"] == f"sf_lead_{submission_id}"
    assert "lead_id" not in event_data["user_data"]

    monitor_event = (
        db.query(MetaCrmDatasetEvent)
        .filter(MetaCrmDatasetEvent.event_id == f"sf_lead_{submission_id}")
        .one()
    )
    assert monitor_event.status == "queued"
    assert monitor_event.form_submission_id == submission_id
    assert monitor_event.intake_lead_id is None
    assert monitor_event.lead_id is None
    assert monitor_event.stage_key == "form_submitted"

    meta_crm_dataset_monitor_service.attach_intake_lead_to_submission_event(
        db=db,
        org_id=test_org.id,
        submission_id=submission_id,
        intake_lead_id=intake_lead_id,
    )
    db.refresh(monitor_event)
    assert monitor_event.intake_lead_id == intake_lead_id


def test_enqueue_meta_crm_dataset_stage_event_includes_fbc_from_meta_lead(db, test_org, test_user):
    from app.db.enums import JobType, SurrogateSource
    from app.db.models import Job, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import (
        meta_crm_dataset_service,
        meta_crm_dataset_settings_service,
        surrogate_service,
    )

    meta_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=f"lead-{uuid4().hex[:8]}",
        meta_form_id="form_1",
        meta_page_id="page_1",
        field_data={"email": "lead@example.com"},
        field_data_raw={
            "email": "lead@example.com",
            "fbc": "fb.1.1772942400.persisted-click-id",
        },
        received_at=datetime.now(timezone.utc),
    )
    db.add(meta_lead)
    db.commit()
    db.refresh(meta_lead)

    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Fresh Meta Lead",
            email="lead@example.com",
            source=SurrogateSource.META,
        ),
    )
    surrogate.meta_lead_id = meta_lead.id
    surrogate.meta_form_id = meta_lead.meta_form_id

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.send_hashed_pii = True
    settings.event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        }
    ]
    db.commit()

    result = meta_crm_dataset_service.enqueue_stage_event(
        db,
        surrogate,
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_label="Pre Qualified",
    )

    assert result["queued"] is True
    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    event_data = job.payload["body"]["data"][0]
    assert event_data["user_data"]["lead_id"] == meta_lead.meta_lead_id
    assert event_data["user_data"]["fbc"] == "fb.1.1772942400.persisted-click-id"
    assert event_data["user_data"]["em"]
    assert "ph" not in event_data["user_data"]


def test_enqueue_meta_crm_dataset_stage_event_skips_meta_leads_older_than_90_days(
    db, test_org, test_user
):
    from app.db.enums import JobType, SurrogateSource
    from app.db.models import Job, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import (
        meta_crm_dataset_service,
        meta_crm_dataset_settings_service,
        surrogate_service,
    )

    meta_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=f"lead-{uuid4().hex[:8]}",
        meta_form_id="form_1",
        meta_page_id="page_1",
        field_data={"email": "stale@example.com"},
        field_data_raw={"email": "stale@example.com"},
        received_at=datetime.now(timezone.utc) - timedelta(days=91),
    )
    db.add(meta_lead)
    db.commit()
    db.refresh(meta_lead)

    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Stale Meta Lead",
            email="stale@example.com",
            source=SurrogateSource.META,
        ),
    )
    surrogate.meta_lead_id = meta_lead.id
    surrogate.meta_form_id = meta_lead.meta_form_id

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        }
    ]
    db.commit()

    result = meta_crm_dataset_service.enqueue_stage_event(
        db,
        surrogate,
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_label="Pre Qualified",
    )

    assert result["queued"] is False
    assert result["reason"] == "stale_meta_lead"
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_meta_crm_dataset_job_handler_posts_dataset_payload(monkeypatch, db, test_org):
    from app.db.enums import JobType
    from app.core.config import settings as app_settings
    from app.db.models import MetaCrmDatasetEvent
    from app.services import job_service, meta_crm_dataset_settings_service
    from app.jobs.handlers import meta

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    db.commit()

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return SimpleNamespace(status_code=200, json=lambda: {"events_received": 1}, text="ok")

    monkeypatch.setattr("app.services.meta_crm_dataset_service.httpx.AsyncClient", FakeClient)

    job = job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.META_CRM_DATASET_EVENT,
        payload={
            "settings_id": str(settings.id),
            "dataset_id": settings.dataset_id,
            "body": {
                "data": [
                    {
                        "event_name": "Qualified",
                        "event_time": 1772942400,
                        "action_source": "system_generated",
                        "custom_data": {
                            "event_source": "crm",
                            "lead_event_source": "Surrogacy Force CRM",
                        },
                        "user_data": {"lead_id": "1559954882011881"},
                    }
                ]
            },
        },
    )
    monitor_event = MetaCrmDatasetEvent(
        organization_id=test_org.id,
        job_id=job.id,
        source="test",
        status="queued",
        event_id="meta-crm-event-provider-response",
        event_name="Qualified",
        stage_key="pre_qualified",
        attempts=0,
    )
    db.add(monitor_event)
    db.commit()

    await meta.process_meta_crm_dataset_event(db, job)

    assert captured["url"] == (
        f"https://graph.facebook.com/{app_settings.META_API_VERSION}/1428122951556949/events"
        "?access_token=meta-token"
    )
    assert captured["json"]["data"][0]["user_data"]["lead_id"] == "1559954882011881"
    db.refresh(monitor_event)
    assert monitor_event.provider_response_json["status_code"] == 200
    assert monitor_event.provider_response_json["body"] == {"events_received": 1}
    assert "access_token" not in str(monitor_event.provider_response_json)
