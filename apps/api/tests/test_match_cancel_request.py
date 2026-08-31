import uuid

import pytest

from app.db.enums import IntendedParentStatus, MatchStatus
from app.db.models import EntityActivityLog, IntendedParent, Match, StatusChangeRequest, Surrogate
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


def _ip_activity_types(db, match: Match) -> list[str]:
    return [
        row.activity_type
        for row in (
            db.query(EntityActivityLog)
            .filter(EntityActivityLog.intended_parent_id == match.intended_parent_id)
            .order_by(EntityActivityLog.occurred_at, EntityActivityLog.id)
            .all()
        )
    ]


@pytest.mark.asyncio
async def test_create_match_response_excludes_compatibility_score(authed_client, db):
    surrogate = await _create_surrogate(authed_client)
    intended_parent = await _create_intended_parent(authed_client)

    response = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate["id"],
            "intended_parent_id": intended_parent["id"],
            "compatibility_score": 88,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert "compatibility_score" not in payload

    list_response = await authed_client.get("/matches/")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()["items"]
    assert items
    assert "compatibility_score" not in items[0]
    match = db.get(Match, uuid.UUID(payload["id"]))
    assert match is not None
    assert "match_proposed" in _ip_activity_types(db, match)


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
    assert _ip_activity_types(db, match_row)[-1] == "match_cancel_requested"


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
    assert _ip_activity_types(db, match_row)[-1] == "match_cancelled"


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
    assert _ip_activity_types(db, match_row)[-1] == "match_cancel_requested"


@pytest.mark.asyncio
async def test_reject_and_cancel_match_are_mirrored_to_intended_parent_activity(authed_client, db):
    surrogate = await _create_surrogate(authed_client)
    rejected_ip = await _create_intended_parent(authed_client)
    rejected = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate["id"], "intended_parent_id": rejected_ip["id"]},
    )
    assert rejected.status_code == 201, rejected.text
    reject_response = await authed_client.put(
        f"/matches/{rejected.json()['id']}/reject",
        json={"rejection_reason": "Not compatible"},
    )
    assert reject_response.status_code == 200, reject_response.text
    rejected_match = db.get(Match, uuid.UUID(rejected.json()["id"]))
    assert rejected_match is not None
    assert _ip_activity_types(db, rejected_match)[-1] == "match_rejected"

    cancelled_ip = await _create_intended_parent(authed_client)
    cancelled = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate["id"], "intended_parent_id": cancelled_ip["id"]},
    )
    assert cancelled.status_code == 201, cancelled.text
    cancel_response = await authed_client.delete(f"/matches/{cancelled.json()['id']}")
    assert cancel_response.status_code == 204, cancel_response.text
    cancelled_match = db.get(Match, uuid.UUID(cancelled.json()["id"]))
    assert cancelled_match is not None
    assert _ip_activity_types(db, cancelled_match)[-1] == "match_cancelled"


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


@pytest.mark.asyncio
async def test_surrogate_cannot_be_manually_set_to_matched_without_accepted_match(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_auth.org.id)
    matched_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "matched")
    assert matched_stage is not None

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(matched_stage.id)},
    )

    assert response.status_code == 403
    assert "accepted match" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_renamed_matched_stage_still_requires_accepted_match(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_auth.org.id)
    matched_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "matched")
    assert matched_stage is not None
    matched_stage.slug = "match_confirmed"
    db.commit()

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(matched_stage.id)},
    )

    assert response.status_code == 403
    assert "accepted match" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_intended_parent_cannot_be_manually_set_to_matched_without_accepted_match(
    authed_client,
    db,
    test_auth,
):
    intended_parent = await _create_intended_parent(authed_client)
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_auth.org.id,
        entity_type="intended_parent",
    )
    matched_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "matched")
    assert matched_stage is not None

    response = await authed_client.patch(
        f"/intended-parents/{intended_parent['id']}/status",
        json={"stage_id": str(matched_stage.id)},
    )

    assert response.status_code == 403
    assert "accepted match" in response.json()["detail"].lower()
