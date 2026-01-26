"""API contract tests for import templates."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_template_crud(authed_client: AsyncClient):
    payload = {
        "name": "Meta Export",
        "description": "Default template for Meta TSV exports",
        "is_default": True,
        "encoding": "auto",
        "delimiter": "auto",
        "has_header": True,
        "column_mappings": [
            {"csv_column": "email", "surrogate_field": "email"},
            {
                "csv_column": "are_you_currently_between_the_ages_of_21_and_36?",
                "surrogate_field": "is_age_eligible",
                "transformation": "boolean_flexible",
            },
        ],
        "transformations": {
            "is_non_smoker": "boolean_inverted",
        },
        "unknown_column_behavior": "metadata",
    }

    create_resp = await authed_client.post("/import-templates", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    template_id = created["id"]
    assert created["name"] == "Meta Export"
    assert created["is_default"] is True

    list_resp = await authed_client.get("/import-templates")
    assert list_resp.status_code == 200, list_resp.text
    templates = list_resp.json()
    assert any(t["id"] == template_id for t in templates)

    get_resp = await authed_client.get(f"/import-templates/{template_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == template_id

    patch_resp = await authed_client.patch(
        f"/import-templates/{template_id}",
        json={"name": "Meta Export (Updated)"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["name"] == "Meta Export (Updated)"

    clone_resp = await authed_client.post(
        f"/import-templates/{template_id}/clone",
        json={"name": "Meta Export Copy"},
    )
    assert clone_resp.status_code == 201, clone_resp.text

    delete_resp = await authed_client.delete(f"/import-templates/{template_id}")
    assert delete_resp.status_code == 204, delete_resp.text
