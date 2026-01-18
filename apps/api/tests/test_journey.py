from datetime import date, datetime, timezone
from uuid import UUID
import uuid

import pytest

from app.db.models import Surrogate
from app.services import pipeline_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


async def _create_surrogate(authed_client):
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Journey Test",
            "email": f"journey-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _set_stage(authed_client, surrogate_id: str, stage_id: UUID, effective_at: str | None = None):
    payload: dict[str, str] = {"stage_id": str(stage_id)}
    if effective_at:
        payload["effective_at"] = effective_at
    response = await authed_client.patch(f"/surrogates/{surrogate_id}/status", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"


def _iter_milestones(payload: dict):
    for phase in payload.get("phases", []):
        for milestone in phase.get("milestones", []):
            yield milestone


def _find_milestone(payload: dict, slug: str):
    for milestone in _iter_milestones(payload):
        if milestone.get("slug") == slug:
            return milestone
    raise AssertionError(f"Missing milestone {slug}")


@pytest.mark.asyncio
async def test_journey_completion_date_uses_next_milestone_entry(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ready_to_match = _get_stage(db, test_auth.org.id, "ready_to_match")
    matched = _get_stage(db, test_auth.org.id, "matched")

    await _set_stage(authed_client, surrogate["id"], ready_to_match.id)
    today = date.today().isoformat()
    await _set_stage(authed_client, surrogate["id"], matched.id, effective_at=today)

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    approved_matching = _find_milestone(payload, "approved_matching")
    assert approved_matching["status"] == "completed"
    assert approved_matching["completed_at"] is not None
    expected_date = datetime.now(timezone.utc).date().isoformat()
    assert approved_matching["completed_at"].startswith(expected_date)

    match_confirmed = _find_milestone(payload, "match_confirmed")
    assert match_confirmed["status"] == "current"


@pytest.mark.asyncio
async def test_journey_terminal_state_has_banner_and_no_current(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    lost_stage = _get_stage(db, test_auth.org.id, "lost")
    today = date.today().isoformat()

    await _set_stage(authed_client, surrogate["id"], lost_stage.id, effective_at=today)

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["is_terminal"] is True
    assert payload["terminal_date"] is not None
    expected_date = datetime.now(timezone.utc).date().isoformat()
    assert payload["terminal_date"].startswith(expected_date)
    assert all(milestone["status"] != "current" for milestone in _iter_milestones(payload))


@pytest.mark.asyncio
async def test_journey_unknown_stage_falls_back_to_first_milestone(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_auth.org.id)

    unknown_stage = pipeline_service.create_stage(
        db=db,
        pipeline_id=pipeline.id,
        slug=f"unknown_{uuid.uuid4().hex[:6]}",
        label="Unknown Stage",
        color="#6B7280",
        stage_type="intake",
        order=0,
        user_id=test_auth.user.id,
    )

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    surrogate_row.stage_id = unknown_stage.id
    surrogate_row.status_label = unknown_stage.label
    db.commit()

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    application_intake = _find_milestone(payload, "application_intake")
    assert application_intake["status"] == "current"


@pytest.mark.asyncio
async def test_journey_completed_milestones_do_not_roll_back(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ready_to_match = _get_stage(db, test_auth.org.id, "ready_to_match")
    matched = _get_stage(db, test_auth.org.id, "matched")

    await _set_stage(authed_client, surrogate["id"], ready_to_match.id)
    await _set_stage(authed_client, surrogate["id"], matched.id)

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    surrogate_row.stage_id = ready_to_match.id
    surrogate_row.status_label = ready_to_match.label
    db.commit()

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    approved_matching = _find_milestone(payload, "approved_matching")
    assert approved_matching["status"] == "completed"
