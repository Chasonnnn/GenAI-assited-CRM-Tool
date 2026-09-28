"""Replay of skipped Zapier outbound events after a configuration or data fix."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.enums import JobStatus, JobType, Role
from app.db.models import Job, Organization, ZapierOutboundEvent
from app.services import donor_service, zapier_outbound_service
from tests.test_donor_zapier_outbound import (
    _add_mapping,
    _add_stage,
    _attach_meta_lead,
    _capture_webhook,
    _configure_reporting,
    _create_donor,
    _history_event,
    _seed_donor_pipeline,
)
from tests.test_zapier_donor_permissions import _client_for, _integration_user
from tests.test_zapier_outbound import _meta_surrogate_with_reporting


def _replay_url(event) -> str:
    return f"/integrations/zapier/events/{event.id}/replay"


def _surrogate_rows(db, surrogate):
    return (
        db.query(ZapierOutboundEvent)
        .filter(ZapierOutboundEvent.surrogate_id == surrogate.id)
        .order_by(ZapierOutboundEvent.created_at)
        .all()
    )


def _skipped_surrogate_event(db, test_org, test_user, *, effective_at):
    surrogate, meta_lead = _meta_surrogate_with_reporting(db, test_org, test_user)
    settings = zapier_outbound_service.zapier_settings_service.get_settings(db, test_org.id)
    settings.outbound_enabled = False
    db.commit()
    result = zapier_outbound_service.enqueue_stage_event(
        db,
        surrogate,
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_id=str(surrogate.stage_id),
        stage_label="Pre Qualified",
        effective_at=effective_at,
    )
    assert result["reason"] == "outbound_disabled"
    (event,) = _surrogate_rows(db, surrogate)
    return surrogate, meta_lead, settings, event


def _synthetic_event(db, org_id, *, reason, donor=False, effective_at=True):
    event = ZapierOutboundEvent(
        organization_id=org_id,
        source="automatic",
        status="skipped",
        reason=reason,
        stage_key="pre_qualified",
        surrogate_id=None if donor else uuid4(),
        donor_type="egg" if donor else None,
        effective_at=datetime.now(UTC) if effective_at else None,
        attempts=0,
    )
    db.add(event)
    db.commit()
    return event


@pytest.mark.asyncio
async def test_replay_queues_a_skipped_surrogate_event_in_place(
    authed_client, db, test_org, test_user
):
    effective_at = datetime.now(UTC) - timedelta(days=3)
    _surrogate, meta_lead, settings, event = _skipped_surrogate_event(
        db, test_org, test_user, effective_at=effective_at
    )
    listed = await authed_client.get("/integrations/zapier/events")
    assert listed.status_code == 200
    assert {item["id"]: item["can_replay"] for item in listed.json()["items"]} == {
        str(event.id): True
    }
    settings.outbound_enabled = True
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(event.id)
    assert body["status"] == "queued"
    assert body["reason"] is None
    assert body["can_replay"] is False
    db.refresh(event)
    assert event.status == "queued"
    assert event.job_id is not None
    assert event.lead_id == meta_lead.meta_lead_id
    job = db.get(Job, event.job_id)
    assert job.job_type == JobType.ZAPIER_STAGE_EVENT.value
    assert job.idempotency_key == event.event_id
    assert job.payload["data"]["event_time"] == effective_at.isoformat()
    assert job.payload["data"]["stage_id"] == str(_surrogate.stage_id)
    assert len(_surrogate_rows(db, _surrogate)) == 1

    again = await authed_client.post(_replay_url(event))
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_replay_that_skips_again_records_the_new_reason(
    authed_client, db, test_org, test_user
):
    surrogate, _meta_lead, settings, event = _skipped_surrogate_event(
        db, test_org, test_user, effective_at=datetime.now(UTC)
    )
    settings.outbound_enabled = True
    settings.outbound_event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": False,
        }
    ]
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "skipped"
    assert response.json()["reason"] == "unmapped_stage"
    assert response.json()["can_replay"] is True
    db.refresh(event)
    assert event.job_id is None
    assert len(_surrogate_rows(db, surrogate)) == 1
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_replay_keeps_one_send_per_surrogate_bucket(authed_client, db, test_org, test_user):
    surrogate, _meta_lead, settings, event = _skipped_surrogate_event(
        db, test_org, test_user, effective_at=datetime.now(UTC)
    )
    settings.outbound_enabled = True
    db.commit()
    later = zapier_outbound_service.enqueue_stage_event(
        db,
        surrogate,
        stage_key="pre_qualified",
        stage_slug="pre_qualified",
        stage_label="Pre Qualified",
    )
    assert later["queued"] is True

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "skipped"
    assert response.json()["reason"] == "duplicate"
    assert response.json()["can_replay"] is False
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_surrogate_event_without_effective_time_is_not_replayable(
    authed_client, db, test_org
):
    event = _synthetic_event(db, test_org.id, reason="outbound_disabled", effective_at=False)

    listed = await authed_client.get("/integrations/zapier/events")
    response = await authed_client.post(_replay_url(event))

    assert listed.json()["items"][0]["can_replay"] is False
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "donor"),
    [
        ("duplicate", False),
        ("stale_meta_lead", False),
        ("synthetic_meta_lead_id", False),
        ("not_meta_source", False),
        ("some_future_reason", False),
        ("donor_stage_undo", True),
        ("donor_stage_undone", True),
        ("donor_event_invalid", True),
        ("donor_subject_missing", True),
        ("donor_stage_inactive", True),
    ],
)
async def test_non_replayable_skip_reasons_are_refused(authed_client, db, test_org, reason, donor):
    event = _synthetic_event(db, test_org.id, reason=reason, donor=donor)

    listed = await authed_client.get("/integrations/zapier/events")
    response = await authed_client.post(_replay_url(event))

    assert listed.json()["items"][0]["can_replay"] is False
    assert response.status_code == 400
    db.refresh(event)
    assert (event.status, event.reason) == ("skipped", reason)


def _skipped_donor_stage_event(db, test_org, test_user):
    pipeline, new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage
    )
    settings.donor_outbound_enabled = False
    db.commit()
    result = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    event = _history_event(db, result["history"])
    assert event.reason == "donor_outbound_disabled"
    return pipeline, new_stage, ready_stage, donor, settings, result["history"], event


@pytest.mark.asyncio
async def test_replay_queues_a_skipped_donor_event_for_the_same_occurrence(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    *_stages, donor, settings, history, event = _skipped_donor_stage_event(db, test_org, test_user)
    settings.donor_outbound_enabled = True
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    db.refresh(event)
    job = db.get(Job, event.job_id)
    assert job.idempotency_key == f"zapier_donor_stage:{history.id}"
    assert job.payload["event_record_id"] == str(event.id)
    assert event.event_id == f"zapier_donor:{donor.id}:qualified"
    assert event.config_fingerprint == job.payload["config_fingerprint"]
    assert db.query(ZapierOutboundEvent).filter_by(donor_id=donor.id).count() == 1

    sent = _capture_webhook(monkeypatch, zapier_handler)
    await zapier_handler.process_zapier_stage_event(db, job)
    assert sent["json"]["event_id"] == event.event_id


@pytest.mark.asyncio
async def test_replay_of_a_dispatch_skip_uses_a_fresh_job_key(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.jobs.handlers import zapier as zapier_handler

    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    settings = _configure_reporting(
        db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage
    )
    result = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    event = _history_event(db, result["history"])
    first_job = db.get(Job, event.job_id)
    settings.donor_outbound_enabled = False
    db.commit()
    await zapier_handler.process_zapier_stage_event(db, first_job)
    first_job.status = JobStatus.COMPLETED.value
    db.commit()
    db.refresh(event)
    assert (event.status, event.reason) == ("skipped", "donor_dispatch_disabled")
    settings.donor_outbound_enabled = True
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    db.refresh(event)
    assert event.status == "queued"
    replay_job = db.get(Job, event.job_id)
    assert replay_job.id != first_job.id
    assert replay_job.idempotency_key.startswith(f"zapier_donor_stage:{result['history'].id}:")
    sent = _capture_webhook(monkeypatch, zapier_handler)
    await zapier_handler.process_zapier_stage_event(db, replay_job)
    assert sent["json"]["event_id"] == event.event_id


@pytest.mark.asyncio
async def test_donor_replay_is_refused_while_the_skipped_job_is_still_running(
    authed_client, db, test_org, test_user
):
    pipeline, _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = _create_donor(db, test_org.id, test_user.id)
    _attach_meta_lead(db, donor)
    _configure_reporting(db, test_org.id, donor_type="egg", pipeline=pipeline, stage=ready_stage)
    result = donor_service.change_status(
        db,
        donor,
        ready_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    event = _history_event(db, result["history"])
    job = db.get(Job, event.job_id)
    job.status = JobStatus.RUNNING.value
    event.status = "skipped"
    event.reason = "donor_config_changed"
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 400
    db.refresh(event)
    assert (event.status, event.job_id) == ("skipped", job.id)


@pytest.mark.asyncio
async def test_donor_replay_keeps_the_send_once_rule(authed_client, db, test_org, test_user):
    pipeline, _new_stage, ready_stage, donor, settings, _history, event = (
        _skipped_donor_stage_event(db, test_org, test_user)
    )
    later_stage = _add_stage(
        db, pipeline, stage_key="screening", stage_type="post_approval", order=3
    )
    settings.donor_outbound_enabled = True
    db.commit()
    _add_mapping(db, settings, pipeline, later_stage, "Qualified")
    later = donor_service.change_status(
        db,
        donor,
        later_stage.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )
    assert _history_event(db, later["history"]).status == "queued"

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "skipped"
    assert response.json()["reason"] == "duplicate"
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 1


@pytest.mark.asyncio
async def test_donor_replay_is_refused_after_a_later_undo(authed_client, db, test_org, test_user):
    _pipeline, new_stage, _ready_stage, donor, settings, _history, event = (
        _skipped_donor_stage_event(db, test_org, test_user)
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
    assert undo["history"].is_undo is True
    settings.donor_outbound_enabled = True
    db.commit()

    response = await authed_client.post(_replay_url(event))

    assert response.status_code == 400
    assert "undo" in response.json()["detail"].lower()
    db.refresh(event)
    assert (event.status, event.reason) == ("skipped", "donor_outbound_disabled")
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_donor_replay_requires_donor_view_and_edit_and_stays_org_scoped(
    db, test_org, test_user
):
    *_stages, _donor, settings, _history, event = _skipped_donor_stage_event(
        db, test_org, test_user
    )
    settings.donor_outbound_enabled = True
    db.commit()
    no_view = _integration_user(db, test_org.id, can_view_donors=False, can_edit_donors=False)
    view_only = _integration_user(db, test_org.id, can_view_donors=True, can_edit_donors=False)
    editor = _integration_user(db, test_org.id, can_view_donors=True, can_edit_donors=True)
    csrf_editor = _integration_user(db, test_org.id, can_view_donors=True, can_edit_donors=True)

    async with _client_for(db, test_org.id, no_view) as client:
        denied_view = await client.post(_replay_url(event))
    async with _client_for(db, test_org.id, view_only) as client:
        denied_edit = await client.post(_replay_url(event))
    async with _client_for(db, test_org.id, csrf_editor, include_csrf=False) as client:
        missing_csrf = await client.post(_replay_url(event))

    assert denied_view.status_code == 403
    assert denied_view.json()["detail"] == "Missing permission: view_donors"
    assert denied_edit.status_code == 403
    assert denied_edit.json()["detail"] == "Missing permission: edit_donors"
    assert missing_csrf.status_code == 403
    assert "Missing or invalid CSRF token" in missing_csrf.json()["detail"]
    db.refresh(event)
    assert event.status == "skipped"

    other_org = Organization(
        id=uuid4(),
        name="Other replay tenant",
        slug=f"other-replay-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.commit()
    other_event = _synthetic_event(db, other_org.id, reason="outbound_disabled")
    async with _client_for(db, test_org.id, editor) as client:
        cross_org = await client.post(_replay_url(other_event))
        allowed = await client.post(_replay_url(event))

    assert cross_org.status_code == 404
    db.refresh(other_event)
    assert other_event.status == "skipped"
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_surrogate_replay_needs_no_donor_permissions(db, test_org, test_user):
    _surrogate, _meta_lead, settings, event = _skipped_surrogate_event(
        db, test_org, test_user, effective_at=datetime.now(UTC)
    )
    settings.outbound_enabled = True
    db.commit()
    user = _integration_user(db, test_org.id, can_view_donors=False, can_edit_donors=False)

    async with _client_for(db, test_org.id, user) as client:
        response = await client.post(_replay_url(event))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
