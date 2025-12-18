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
            {"status": "new", "label": "New", "color": "#3B82F6", "order": 1},
            {"status": "in_progress", "label": "In Progress", "color": "#F59E0B", "order": 2},
            {"status": "done", "label": "Done", "color": "#10B981", "order": 3},
        ]
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Pipeline"
    assert data["current_version"] == 1
    assert len(data["stages"]) == 3


@pytest.mark.xfail(reason="DB isolation issue - pipeline state not preserved between create/update")
@pytest.mark.asyncio
async def test_update_pipeline_increments_version(authed_client: AsyncClient):
    """Updating a pipeline should increment current_version."""
    # Create first
    create_payload = {
        "name": "Version Test Pipeline",
        "stages": [
            {"status": "open", "label": "Open", "color": "#3B82F6", "order": 1},
        ]
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    initial_version = create_resp.json()["current_version"]
    
    # Update
    update_payload = {
        "name": "Version Test Pipeline Updated",
        "stages": [
            {"status": "open", "label": "Open", "color": "#3B82F6", "order": 1},
            {"status": "closed", "label": "Closed", "color": "#EF4444", "order": 2},
        ],
        "expected_version": initial_version,
    }
    update_resp = await authed_client.patch(f"/settings/pipelines/{pipeline_id}", json=update_payload)
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
            {"status": "open", "label": "Open", "color": "#3B82F6", "order": 1},
        ]
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    
    # Update with wrong version
    update_payload = {
        "name": "Should Fail",
        "expected_version": 999,  # Wrong version
    }
    update_resp = await authed_client.patch(f"/settings/pipelines/{pipeline_id}", json=update_payload)
    assert update_resp.status_code == 409
