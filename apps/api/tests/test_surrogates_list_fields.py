import uuid

import pytest


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
