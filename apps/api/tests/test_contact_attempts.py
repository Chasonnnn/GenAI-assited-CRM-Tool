from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.db.enums import ContactStatus
from app.db.models import Surrogate, PipelineStage, SurrogateActivityLog


@pytest.mark.asyncio
async def test_contact_attempt_blocked_for_queue_owned(authed_client):
    queue_res = await authed_client.post("/queues", json={"name": "Queue A", "description": ""})
    assert queue_res.status_code == 201, queue_res.text
    queue_id = queue_res.json()["id"]

    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Queue Attempt", "email": "queue-attempt@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    assign_res = await authed_client.post(
        f"/queues/surrogates/{surrogate_id}/assign", json={"queue_id": queue_id}
    )
    assert assign_res.status_code == 200, assign_res.text

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={"contact_methods": ["phone"], "outcome": "no_answer"},
    )
    assert attempt_res.status_code == 400, attempt_res.text


@pytest.mark.asyncio
async def test_contact_attempt_rejects_before_assignment(authed_client):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Backdated", "email": "backdated@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempted_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={
            "contact_methods": ["phone"],
            "outcome": "no_answer",
            "attempted_at": attempted_at,
        },
    )
    assert attempt_res.status_code == 400, attempt_res.text


@pytest.mark.asyncio
async def test_contact_attempt_reached_updates_stage_and_status(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Reached", "email": "reached@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={"contact_methods": ["phone"], "outcome": "reached"},
    )
    assert attempt_res.status_code == 201, attempt_res.text

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    assert case.contact_status == ContactStatus.REACHED.value
    assert case.contacted_at is not None

    stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert stage is not None
    assert stage.slug == "contacted"


@pytest.mark.asyncio
async def test_manual_stage_change_sets_contact_status(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Manual Contacted", "email": "manual@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    current_stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert current_stage is not None

    contacted_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == current_stage.pipeline_id,
            PipelineStage.slug == "contacted",
        )
        .first()
    )
    assert contacted_stage is not None

    change_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert change_res.status_code == 200, change_res.text

    db.refresh(case)
    assert case.contact_status == ContactStatus.REACHED.value
    assert case.contacted_at is not None


@pytest.mark.asyncio
async def test_contact_attempt_activity_includes_note_preview(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Contact Notes", "email": "contact-notes@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={
            "contact_methods": ["phone"],
            "outcome": "no_answer",
            "notes": "<p>Left voicemail and asked for callback.</p>",
        },
    )
    assert attempt_res.status_code == 201, attempt_res.text

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == UUID(surrogate_id),
            SurrogateActivityLog.activity_type == "contact_attempt",
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    assert details.get("note_preview") == "Left voicemail and asked for callback."
