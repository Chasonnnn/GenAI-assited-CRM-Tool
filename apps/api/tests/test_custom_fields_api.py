"""API contract tests for org-scoped custom fields."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_custom_field_crud(authed_client: AsyncClient):
    payload = {
        "key": "criminal_history",
        "label": "Criminal History",
        "field_type": "boolean",
        "options": None,
    }

    create_resp = await authed_client.post("/custom-fields", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    field_id = created["id"]
    assert created["key"] == "criminal_history"

    list_resp = await authed_client.get("/custom-fields")
    assert list_resp.status_code == 200, list_resp.text
    fields = list_resp.json()
    assert any(f["id"] == field_id for f in fields)

    patch_resp = await authed_client.patch(
        f"/custom-fields/{field_id}",
        json={"label": "Criminal History (Updated)"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["label"] == "Criminal History (Updated)"

    delete_resp = await authed_client.delete(f"/custom-fields/{field_id}")
    assert delete_resp.status_code == 204, delete_resp.text
