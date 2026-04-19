from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Query


@pytest.mark.asyncio
async def test_zapier_outbound_events_summary_excludes_test_events(authed_client, db, test_org):
    from app.db.models import ZapierOutboundEvent

    now = datetime.now(timezone.utc)
    db.add_all(
        [
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="automatic",
                status="delivered",
                event_id="evt-delivered",
                event_name="Qualified",
                lead_id="lead-1",
                stage_key="pre_qualified",
                stage_label="Pre Qualified",
                attempts=1,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
                delivered_at=now - timedelta(hours=2),
                last_attempt_at=now - timedelta(hours=2),
            ),
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="workflow",
                status="failed",
                event_id="evt-failed",
                event_name="Converted",
                lead_id="lead-2",
                stage_key="matched",
                stage_label="Matched",
                attempts=3,
                last_error="Webhook timeout",
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(hours=1),
                last_attempt_at=now - timedelta(hours=1),
            ),
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="automatic",
                status="skipped",
                reason="stale_meta_lead",
                event_name="Converted",
                lead_id="lead-3",
                stage_key="delivered",
                stage_label="Delivered",
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
            ),
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="test",
                status="failed",
                event_id="evt-test",
                event_name="Lead",
                lead_id="lead-test",
                stage_key="new_unread",
                stage_label="New Unread",
                attempts=1,
                last_error="Ignore test event",
                created_at=now - timedelta(minutes=10),
                updated_at=now - timedelta(minutes=10),
                last_attempt_at=now - timedelta(minutes=10),
            ),
        ]
    )
    db.commit()

    list_res = await authed_client.get("/integrations/zapier/events?limit=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 4
    assert list_data["items"][0]["source"] == "test"
    assert list_data["items"][0]["status"] == "failed"

    summary_res = await authed_client.get("/integrations/zapier/events/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_count"] == 3
    assert summary["queued_count"] == 0
    assert summary["delivered_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["actionable_skipped_count"] == 1
    assert summary["failure_rate"] == 0.5
    assert summary["skipped_rate"] == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_retry_failed_zapier_outbound_event_replays_job(authed_client, db, test_org):
    from app.db.enums import JobStatus, JobType
    from app.db.models import Job, ZapierOutboundEvent

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.ZAPIER_STAGE_EVENT.value,
        payload={
            "url": "https://hooks.zapier.com/hooks/catch/123/abc",
            "headers": {},
            "data": {"event_id": "evt-failed"},
        },
        status=JobStatus.FAILED.value,
        attempts=3,
        max_attempts=3,
        last_error="Webhook timeout",
    )
    db.add(job)
    db.flush()

    event = ZapierOutboundEvent(
        organization_id=test_org.id,
        source="automatic",
        status="failed",
        job_id=job.id,
        event_id="evt-failed",
        event_name="Qualified",
        lead_id="lead-1",
        stage_key="pre_qualified",
        stage_label="Pre Qualified",
        attempts=3,
        last_error="Webhook timeout",
        last_attempt_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    res = await authed_client.post(f"/integrations/zapier/events/{event.id}/retry", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert data["attempts"] == 0
    assert data["can_retry"] is False

    db.refresh(job)
    db.refresh(event)
    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 0
    assert event.status == "queued"
    assert event.last_error is None


def test_mark_zapier_event_job_lifecycle_updates(db, test_org):
    from app.db.enums import JobStatus, JobType
    from app.db.models import Job, ZapierOutboundEvent
    from app.services import zapier_monitor_service

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.ZAPIER_STAGE_EVENT.value,
        payload={
            "url": "https://hooks.zapier.com/hooks/catch/123/abc",
            "headers": {},
            "data": {"event_id": "evt-queued"},
        },
        status=JobStatus.PENDING.value,
        attempts=1,
    )
    db.add(job)
    db.flush()
    event = ZapierOutboundEvent(
        organization_id=test_org.id,
        source="automatic",
        status="queued",
        job_id=job.id,
        event_id="evt-queued",
        event_name="Qualified",
        lead_id="lead-queued",
        stage_key="pre_qualified",
        stage_label="Pre Qualified",
    )
    db.add(event)
    db.commit()

    job.status = JobStatus.COMPLETED.value
    job.attempts = 1
    db.commit()
    zapier_monitor_service.mark_job_delivered(db=db, job_id=job.id, attempts=job.attempts)

    db.refresh(event)
    assert event.status == "delivered"
    assert event.delivered_at is not None
    assert event.attempts == 1

    failed_job = Job(
        organization_id=test_org.id,
        job_type=JobType.ZAPIER_STAGE_EVENT.value,
        payload={
            "url": "https://hooks.zapier.com/hooks/catch/123/abc",
            "headers": {},
            "data": {"event_id": "evt-failed-final"},
        },
        status=JobStatus.FAILED.value,
        attempts=3,
        max_attempts=3,
        last_error="Webhook timeout",
    )
    db.add(failed_job)
    db.flush()
    failed_event = ZapierOutboundEvent(
        organization_id=test_org.id,
        source="automatic",
        status="queued",
        job_id=failed_job.id,
        event_id="evt-failed-final",
        event_name="Converted",
        lead_id="lead-failed",
        stage_key="matched",
        stage_label="Matched",
    )
    db.add(failed_event)
    db.commit()

    zapier_monitor_service.mark_job_failed(
        db=db,
        job_id=failed_job.id,
        job_status=failed_job.status,
        attempts=failed_job.attempts,
        error_message=failed_job.last_error or "Webhook timeout",
    )

    db.refresh(failed_event)
    assert failed_event.status == "failed"
    assert failed_event.last_error == "Webhook timeout"
    assert failed_event.attempts == 3


def test_list_events_skips_count_for_short_first_page(db, test_org, monkeypatch):
    from app.db.models import ZapierOutboundEvent
    from app.services import zapier_monitor_service

    event = ZapierOutboundEvent(
        organization_id=test_org.id,
        source="automatic",
        status="queued",
        event_id="evt-short-page",
        event_name="Lead",
        lead_id="lead-short-page",
        stage_key="new_unread",
        stage_label="New Unread",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    original_count = Query.count

    def _count_should_not_be_called(self, *args, **kwargs):
        if self.column_descriptions and self.column_descriptions[0].get("name") == "ZapierOutboundEvent":
            raise AssertionError("list_events should not call Query.count()")
        return original_count(self, *args, **kwargs)

    monkeypatch.setattr(Query, "count", _count_should_not_be_called)

    items, total = zapier_monitor_service.list_events(db, org_id=test_org.id, limit=50, offset=0)

    assert total == 1
    assert [item.id for item in items] == [event.id]
