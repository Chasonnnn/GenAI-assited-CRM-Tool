"""Tests for outbound Zapier stage events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_zapier_outbound_settings_update(authed_client):
    payload = {
        "outbound_webhook_url": "https://hooks.zapier.com/hooks/catch/123/abc",
        "outbound_webhook_secret": "zapier-secret",
        "outbound_enabled": True,
        "send_hashed_pii": True,
        "event_mapping": [
            {"stage_key": "new_unread", "event_name": "Lead", "enabled": True},
            {"stage_key": "pre_qualified", "event_name": "Qualified", "bucket": "qualified", "enabled": True},
            {"stage_key": "matched", "event_name": "ConvertedLead", "enabled": False},
        ],
    }

    res = await authed_client.post("/integrations/zapier/settings/outbound", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["outbound_enabled"] is True
    assert data["outbound_webhook_url"] == payload["outbound_webhook_url"]
    assert data["outbound_secret_configured"] is True
    assert data["send_hashed_pii"] is True
    assert any(
        m["stage_key"] == "pre_qualified" and m["enabled"] for m in data["event_mapping"]
    )
    assert any(
        m["stage_key"] == "pre_qualified" and m.get("bucket") == "qualified"
        for m in data["event_mapping"]
    )

    res2 = await authed_client.get("/integrations/zapier/settings")
    assert res2.status_code == 200
    settings = res2.json()
    assert settings["outbound_enabled"] is True
    assert settings["outbound_webhook_url"] == payload["outbound_webhook_url"]
    assert settings["outbound_secret_configured"] is True
    assert settings["send_hashed_pii"] is True


@pytest.mark.asyncio
async def test_zapier_outbound_test_event_queues_job(authed_client, db, test_org):
    from app.db.enums import JobType
    from app.db.models import Job
    from app.services import zapier_settings_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_webhook_secret_encrypted = zapier_settings_service.encrypt_secret("secret")
    settings.outbound_enabled = True
    settings.outbound_send_hashed_pii = True
    settings.outbound_event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "PreQualifiedLead", "enabled": True}
    ]
    db.commit()

    res = await authed_client.post(
        "/integrations/zapier/test-outbound",
        json={"stage_key": "pre_qualified", "lead_id": "lead-test-1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert data["event_name"] == "Qualified"

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["data"]["lead_id"] == "lead-test-1"
    assert job.payload["data"]["event_name"] == "Qualified"
    assert job.payload["data"]["lifecycle_stage_name"] == "Qualified"
    assert job.payload["data"]["customer_email"] == "zapier-test@example.com"
    assert job.payload["data"]["customer_phone_number"] == "+15551234567"
    assert data["lead_id"] == "lead-test-1"


def test_build_stage_event_payload_exposes_zapier_matching_fields():
    from app.services import meta_capi, zapier_outbound_service

    payload = zapier_outbound_service.build_stage_event_payload(
        lead_id="1559954882011881",
        event_name="Qualified",
        event_time=datetime(2026, 3, 8, 6, 56, 36, tzinfo=timezone.utc),
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_id=None,
        stage_label="Pre Qualified",
        surrogate_id=None,
        include_hashed_pii=True,
        email="lead@example.com",
        phone="+15551234567",
        meta_fields=None,
        fbc="fb.1.1772942400.persisted-click-id",
        event_id="zapier-stage-1",
        test_mode=False,
    )

    assert payload["lead_id"] == "1559954882011881"
    assert payload["event_name"] == "Qualified"
    assert payload["lifecycle_stage_name"] == "Qualified"
    assert payload["customer_email"] == "lead@example.com"
    assert payload["customer_phone_number"] == "+15551234567"
    assert payload["facebook_click_id"] == "fb.1.1772942400.persisted-click-id"
    assert payload["fbc"] == "fb.1.1772942400.persisted-click-id"
    assert payload["user_data"] == {
        "email_hash": meta_capi.hash_for_capi("lead@example.com"),
        "phone_hash": meta_capi.hash_for_capi("+15551234567"),
    }


def test_enqueue_stage_event_skips_meta_leads_older_than_90_days(db, test_org, test_user):
    from app.db.enums import JobType, SurrogateSource
    from app.db.models import Job, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service, zapier_outbound_service, zapier_settings_service

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

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_enabled = True
    settings.outbound_event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "bucket": "qualified", "enabled": True}
    ]
    db.commit()

    result = zapier_outbound_service.enqueue_stage_event(
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
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .count()
        == 0
    )


def test_enqueue_stage_event_includes_click_id_and_customer_fields(db, test_org, test_user):
    from app.db.enums import JobType, SurrogateSource
    from app.db.models import Job, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service, zapier_outbound_service, zapier_settings_service

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
            full_name="Zapier Meta Lead",
            email="lead@example.com",
            phone="+1 (555) 123-4567",
            source=SurrogateSource.META,
        ),
    )
    surrogate.meta_lead_id = meta_lead.id
    surrogate.meta_form_id = meta_lead.meta_form_id

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_enabled = True
    settings.outbound_send_hashed_pii = True
    settings.outbound_event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "bucket": "qualified", "enabled": True}
    ]
    db.commit()

    result = zapier_outbound_service.enqueue_stage_event(
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
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    payload = job.payload["data"]
    assert payload["lifecycle_stage_name"] == "Qualified"
    assert payload["customer_email"] == "lead@example.com"
    assert payload["customer_phone_number"] == "+15551234567"
    assert payload["facebook_click_id"] == "fb.1.1772942400.persisted-click-id"
    assert payload["fbc"] == "fb.1.1772942400.persisted-click-id"


def test_normalize_event_mapping_expands_meta_status_ranges():
    from app.services import zapier_settings_service

    mapping = zapier_settings_service.normalize_event_mapping(
        [
            {"stage_key": "pre_qualified", "event_name": "PreQualifiedLead", "enabled": True},
            {"stage_key": "matched", "event_name": "ConvertedLead", "enabled": True},
        ]
    )
    by_stage = {item["stage_key"]: item for item in mapping}

    assert by_stage["pre_qualified"]["event_name"] == "Qualified"
    assert by_stage["pre_qualified"]["bucket"] == "qualified"
    assert by_stage["application_submitted"]["event_name"] == "Qualified"
    assert by_stage["application_submitted"]["bucket"] == "qualified"
    assert by_stage["ready_to_match"]["event_name"] == "Converted"
    assert by_stage["ready_to_match"]["bucket"] == "converted"
    assert by_stage["lost"]["event_name"] == "Lost"
    assert by_stage["lost"]["bucket"] == "lost"
    assert by_stage["disqualified"]["event_name"] == "Not Qualified"
    assert by_stage["disqualified"]["bucket"] == "not_qualified"


def test_resolve_meta_stage_bucket_uses_configured_mapping():
    from app.services import zapier_settings_service

    mapping = zapier_settings_service.normalize_event_mapping(
        [
            {
                "stage_key": "approved",
                "event_name": "Converted",
                "bucket": "converted",
                "enabled": True,
            }
        ]
    )
    assert zapier_settings_service.resolve_meta_stage_bucket("approved", mapping) == "converted"

    disabled_mapping = zapier_settings_service.normalize_event_mapping(
        [
            {
                "stage_key": "approved",
                "event_name": "Converted",
                "bucket": "converted",
                "enabled": False,
            }
        ]
    )
    assert zapier_settings_service.resolve_meta_stage_bucket("approved", disabled_mapping) is None
