"""Tests for direct Meta CRM dataset monitoring endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_meta_crm_dataset_events_summary_and_retry(authed_client, db, test_org):
    from app.db.enums import JobStatus, JobType
    from app.services import job_service, meta_crm_dataset_monitor_service

    job = job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.META_CRM_DATASET_EVENT,
        payload={"dataset_id": "1428122951556949", "body": {"data": []}},
        idempotency_key="meta_crm_dataset:test",
    )
    event = meta_crm_dataset_monitor_service.record_queued_event(
        db=db,
        org_id=test_org.id,
        job_id=job.id,
        source="automatic",
        event_id="meta-crm-event-1",
        event_name="Qualified",
        lead_id="1559954882011881",
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_label="Pre Qualified",
        surrogate_id=None,
    )
    meta_crm_dataset_monitor_service.mark_job_failed(
        db=db,
        job_id=job.id,
        job_status=JobStatus.FAILED.value,
        attempts=job.attempts,
        error_message="Graph API error",
    )

    summary_res = await authed_client.get("/integrations/meta/crm-dataset/events/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["failed_count"] == 1
    assert summary["total_count"] == 1

    events_res = await authed_client.get("/integrations/meta/crm-dataset/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert events["total"] == 1
    assert events["items"][0]["status"] == "failed"
    assert events["items"][0]["can_retry"] is True

    retry_res = await authed_client.post(
        f"/integrations/meta/crm-dataset/events/{event.id}/retry",
        json={"reason": "manual retry"},
    )
    assert retry_res.status_code == 200
    retried = retry_res.json()
    assert retried["status"] == "queued"
