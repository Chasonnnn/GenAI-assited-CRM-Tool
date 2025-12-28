"""Tests for Pipelines API with versioning."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_pipelines_authed(authed_client: AsyncClient):
    """Authenticated request to /settings/pipelines should return 200."""
    response = await authed_client.get("/settings/pipelines")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_pipeline(authed_client: AsyncClient):
    """Create a pipeline should return 201 with version=1."""
    payload = {
        "name": "Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
            {
                "slug": "contacted",
                "label": "Contacted",
                "color": "#F59E0B",
                "stage_type": "intake",
                "order": 2,
            },
            {
                "slug": "delivered",
                "label": "Delivered",
                "color": "#10B981",
                "stage_type": "terminal",
                "order": 3,
            },
        ],
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    if response.status_code != 201:
        print(f"Create response: {response.status_code} - {response.text}")
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Pipeline"
    assert data["current_version"] == 1
    assert len(data["stages"]) == 3


@pytest.mark.asyncio
async def test_update_pipeline_increments_version(authed_client: AsyncClient):
    """Updating a pipeline should increment current_version."""
    # Create first
    create_payload = {
        "name": "Version Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    initial_version = create_resp.json()["current_version"]

    # Update name only (stages unchanged)
    update_payload = {
        "name": "Version Test Pipeline Updated",
        "expected_version": initial_version,
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    if update_resp.status_code != 200:
        print(f"Update response: {update_resp.status_code} - {update_resp.text}")
    assert update_resp.status_code == 200
    assert update_resp.json()["current_version"] == initial_version + 1


@pytest.mark.asyncio
async def test_update_pipeline_version_conflict(authed_client: AsyncClient):
    """Updating with wrong expected_version should return 409."""
    # Create first
    create_payload = {
        "name": "Conflict Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]

    # Update with wrong version
    update_payload = {
        "name": "Should Fail",
        "expected_version": 999,  # Wrong version
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    assert update_resp.status_code == 409
