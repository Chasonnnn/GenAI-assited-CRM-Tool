import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import Surrogate, SurrogateActivityLog


@pytest.mark.asyncio
async def test_surrogates_list_includes_race(authed_client):
    payload = {
        "full_name": "Race Test",
        "email": f"race-{uuid.uuid4().hex[:8]}@example.com",
        "race": "Asian",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]

    match = next((item for item in items if item["id"] == created_id), None)
    assert match is not None
    assert match["race"] == payload["race"]
    assert match["last_activity_at"] is not None


@pytest.mark.asyncio
async def test_surrogates_list_normalizes_bmi_using_rounded_inches(authed_client):
    payload = {
        "full_name": "BMI Test",
        "email": f"bmi-{uuid.uuid4().hex[:8]}@example.com",
        "height_ft": 5.1,
        "weight_lb": 180,
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]
    match = next((item for item in items if item["id"] == created_id), None)

    assert match is not None
    assert match["bmi"] == pytest.approx(34.0, abs=0.01)


@pytest.mark.asyncio
async def test_surrogates_list_does_not_fallback_to_updated_at_for_last_activity(authed_client, db):
    payload = {
        "full_name": "No Activity Test",
        "email": f"no-activity-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]
    surrogate_id = uuid.UUID(created_id)

    db.query(SurrogateActivityLog).filter(SurrogateActivityLog.surrogate_id == surrogate_id).delete()
    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None
    surrogate.updated_at = datetime.now(timezone.utc)
    db.commit()

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]
    match = next((item for item in items if item["id"] == created_id), None)

    assert match is not None
    assert match["last_activity_at"] is None


@pytest.mark.asyncio
async def test_surrogates_list_created_to_date_includes_entire_day(authed_client, db):
    res_same_day = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Created To Same Day",
            "email": f"created-to-same-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert res_same_day.status_code == 201, res_same_day.text
    same_day_id = res_same_day.json()["id"]

    res_next_day = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Created To Next Day",
            "email": f"created-to-next-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert res_next_day.status_code == 201, res_next_day.text
    next_day_id = res_next_day.json()["id"]

    same_day_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(same_day_id)).first()
    next_day_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(next_day_id)).first()
    assert same_day_row is not None and next_day_row is not None

    same_day_row.created_at = datetime(2025, 1, 10, 15, 45, tzinfo=timezone.utc)
    next_day_row.created_at = datetime(2025, 1, 11, 0, 0, 1, tzinfo=timezone.utc)
    db.commit()

    list_res = await authed_client.get("/surrogates", params={"created_to": "2025-01-10"})
    assert list_res.status_code == 200, list_res.text
    ids = {item["id"] for item in list_res.json()["items"]}

    assert same_day_id in ids
    assert next_day_id not in ids
