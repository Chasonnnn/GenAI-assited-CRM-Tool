import uuid

import pytest

from app.db.enums import IntendedParentStatus, MatchStatus
from app.db.models import IntendedParent, Match, StatusChangeRequest, Surrogate
from app.services import pipeline_service


async def _create_surrogate(authed_client) -> dict:
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Match Cancel Surrogate",
            "email": f"surrogate-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_intended_parent(authed_client) -> dict:
    response = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Match Cancel Intended Parent",
            "email": f"ip-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_accepted_match(authed_client) -> dict:
    surrogate = await _create_surrogate(authed_client)
    intended_parent = await _create_intended_parent(authed_client)

    response = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate["id"],
            "intended_parent_id": intended_parent["id"],
        },
    )
    assert response.status_code == 201, response.text
    match = response.json()
    accept = await authed_client.put(f"/matches/{match['id']}/accept", json={})
    assert accept.status_code == 200, accept.text
    return accept.json()


@pytest.mark.asyncio
async def test_match_cancel_request_creates_pending_request(authed_client, db, test_auth):
    match = await _create_accepted_match(authed_client)

    response = await authed_client.post(f"/matches/{match['id']}/cancel-request", json={})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == MatchStatus.CANCEL_PENDING.value

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == uuid.UUID(match["id"]),
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    assert request is not None
    assert request.target_status == MatchStatus.CANCELLED.value

    match_row = db.query(Match).filter(Match.id == uuid.UUID(match["id"])).first()
    assert match_row is not None
    assert match_row.status == MatchStatus.CANCEL_PENDING.value


@pytest.mark.asyncio
async def test_match_cancel_request_approval_updates_statuses(authed_client, db, test_auth):
    match = await _create_accepted_match(authed_client)

    response = await authed_client.post(f"/matches/{match['id']}/cancel-request", json={})
    assert response.status_code == 200, response.text

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == uuid.UUID(match["id"]),
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    assert request is not None

    approve = await authed_client.post(f"/status-change-requests/{request.id}/approve")
    assert approve.status_code == 200, approve.text

    match_row = db.query(Match).filter(Match.id == uuid.UUID(match["id"])).first()
    assert match_row is not None
    assert match_row.status == MatchStatus.CANCELLED.value

    surrogate = db.query(Surrogate).filter(Surrogate.id == match_row.surrogate_id).first()
    assert surrogate is not None
    ready_stage = pipeline_service.get_stage_by_slug(
        db,
        pipeline_service.get_or_create_default_pipeline(db, test_auth.org.id).id,
        "ready_to_match",
    )
    assert ready_stage is not None
    assert surrogate.stage_id == ready_stage.id

    intended_parent = (
        db.query(IntendedParent).filter(IntendedParent.id == match_row.intended_parent_id).first()
    )
    assert intended_parent is not None
    assert intended_parent.status == IntendedParentStatus.READY_TO_MATCH.value


@pytest.mark.asyncio
async def test_match_cancel_request_reject_restores_status(authed_client, db, test_auth):
    match = await _create_accepted_match(authed_client)

    response = await authed_client.post(f"/matches/{match['id']}/cancel-request", json={})
    assert response.status_code == 200, response.text

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == uuid.UUID(match["id"]),
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    assert request is not None

    reject = await authed_client.post(
        f"/status-change-requests/{request.id}/reject", json={"reason": "Not yet"}
    )
    assert reject.status_code == 200, reject.text

    match_row = db.query(Match).filter(Match.id == uuid.UUID(match["id"])).first()
    assert match_row is not None
    assert match_row.status == MatchStatus.ACCEPTED.value


@pytest.mark.asyncio
async def test_match_cancel_request_requires_accepted_match(authed_client, db):
    surrogate = await _create_surrogate(authed_client)
    intended_parent = await _create_intended_parent(authed_client)

    response = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate["id"],
            "intended_parent_id": intended_parent["id"],
        },
    )
    assert response.status_code == 201, response.text
    match = response.json()

    cancel = await authed_client.post(f"/matches/{match['id']}/cancel-request", json={})
    assert cancel.status_code == 400
