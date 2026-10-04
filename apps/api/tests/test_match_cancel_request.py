import uuid

import pytest

from app.db.models import EntityActivityLog, IntendedParent, Match, Surrogate
from app.services import pipeline_service


async def _move_to_handoff(client, route, record_id, entity_type):
    pipeline = await client.get("/settings/pipelines/default", params={"entity_type": entity_type})
    assert pipeline.status_code == 200, pipeline.text
    key = "available" if entity_type == "sperm_donor" else "ready_to_match"
    stage = next(s for s in pipeline.json()["stages"] if s["stage_key"] == key)
    response = await client.patch(f"/{route}/{record_id}/status", json={"stage_id": stage["id"]})
    assert response.status_code == 200, response.text


async def _create_surrogate(authed_client, *, ready=True) -> dict:
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Match Cancel Surrogate",
            "email": f"surrogate-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    record = response.json()
    if ready:
        await _move_to_handoff(authed_client, "surrogates", record["id"], "surrogate")
    return record


async def _create_intended_parent(authed_client, *, ready=True) -> dict:
    response = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Match Cancel Intended Parent",
            "email": f"ip-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    record = response.json()
    if ready:
        await _move_to_handoff(authed_client, "intended-parents", record["id"], "intended_parent")
    return record


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
async def test_match_responses_include_participant_stage_colors(authed_client, db):
    match = await _create_accepted_match(authed_client)
    row = db.get(Match, uuid.UUID(match["id"]))
    surrogate = db.get(Surrogate, row.surrogate_id)
    ip = db.get(IntendedParent, row.intended_parent_id)

    detail = await authed_client.get(f"/matches/{match['id']}")
    listing = await authed_client.get("/matches/")

    assert detail.status_code == 200, detail.text
    assert detail.json()["surrogate_stage_color"] == surrogate.stage.color
    assert detail.json()["ip_stage_color"] == ip.stage.color
    item = next(i for i in listing.json()["items"] if i["id"] == match["id"])
    assert item["surrogate_stage_color"] == surrogate.stage.color
    assert item["donor_stage_color"] is None


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

    cancel = await authed_client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
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
