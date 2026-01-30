from datetime import date, datetime
from uuid import UUID
import uuid
from zoneinfo import ZoneInfo

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
            "full_name": "Delivery Date Test",
            "email": f"delivery-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _org_today(org_timezone: str | None) -> str:
    tz_name = org_timezone or "America/Los_Angeles"
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()


@pytest.mark.asyncio
async def test_setting_actual_delivery_date_advances_stage(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    delivered_stage = _get_stage(db, test_auth.org.id, "delivered")
    today = _org_today(test_auth.org.timezone)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}",
        json={"actual_delivery_date": today},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("actual_delivery_date") == today

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == delivered_stage.id


@pytest.mark.asyncio
async def test_delivered_stage_sets_actual_delivery_date_when_missing(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    delivered_stage = _get_stage(db, test_auth.org.id, "delivered")
    today = _org_today(test_auth.org.timezone)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(delivered_stage.id), "effective_at": today},
    )
    assert response.status_code == 200, response.text

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.actual_delivery_date == date.fromisoformat(today)


@pytest.mark.asyncio
async def test_delivered_stage_syncs_delivery_outcome_fields(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    delivered_stage = _get_stage(db, test_auth.org.id, "delivered")
    today = _org_today(test_auth.org.timezone)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={
            "stage_id": str(delivered_stage.id),
            "effective_at": today,
            "delivery_baby_gender": "Male",
            "delivery_baby_weight": "6 lb 8 oz",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["surrogate"]["delivery_baby_gender"] == "Male"
    assert payload["surrogate"]["delivery_baby_weight"] == "6 lb 8 oz"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.delivery_baby_gender == "Male"
    assert surrogate_row.delivery_baby_weight == "6 lb 8 oz"


@pytest.mark.asyncio
async def test_delivery_outcome_fields_saved(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    today = _org_today(test_auth.org.timezone)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}",
        json={
            "actual_delivery_date": today,
            "delivery_baby_gender": "Female",
            "delivery_baby_weight": "7 lb 2 oz",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("delivery_baby_gender") == "Female"
    assert payload.get("delivery_baby_weight") == "7 lb 2 oz"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.delivery_baby_gender == "Female"
    assert surrogate_row.delivery_baby_weight == "7 lb 2 oz"
