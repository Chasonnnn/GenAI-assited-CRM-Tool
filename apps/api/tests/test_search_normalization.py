import uuid

import pytest


@pytest.mark.asyncio
async def test_surrogates_list_search_accent_insensitive(authed_client):
    payload = {
        "full_name": "José Alvarez",
        "email": f"jose-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates?q=jose")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]

    assert any(item["id"] == surrogate_id for item in items)


@pytest.mark.asyncio
async def test_intended_parents_list_search_accent_insensitive(authed_client):
    payload = {
        "full_name": "Renée O'Neil",
        "email": f"renee-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/intended-parents", json=payload)
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    list_res = await authed_client.get("/intended-parents?q=renee")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]

    assert any(item["id"] == ip_id for item in items)
