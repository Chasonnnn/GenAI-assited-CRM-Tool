"""Tests for outbound Zapier stage events."""

from __future__ import annotations

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
