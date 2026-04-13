from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _create_surrogate(authed_client: AsyncClient) -> dict:
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Stats Surrogate",
            "email": f"surrogate-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_intended_parent(authed_client: AsyncClient) -> dict:
    response = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Stats Intended Parent",
            "email": f"ip-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_match_stats_returns_zero_filled_statuses_and_grouped_total(
    authed_client: AsyncClient,
):
    surrogate_one = await _create_surrogate(authed_client)
    intended_parent_one = await _create_intended_parent(authed_client)
    proposed_response = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate_one["id"],
            "intended_parent_id": intended_parent_one["id"],
        },
    )
    assert proposed_response.status_code == 201, proposed_response.text

    surrogate_two = await _create_surrogate(authed_client)
    intended_parent_two = await _create_intended_parent(authed_client)
    accepted_response = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate_two["id"],
            "intended_parent_id": intended_parent_two["id"],
        },
    )
    assert accepted_response.status_code == 201, accepted_response.text

    accept = await authed_client.put(
        f"/matches/{accepted_response.json()['id']}/accept",
        json={},
    )
    assert accept.status_code == 200, accept.text

    stats_response = await authed_client.get("/matches/stats")
    assert stats_response.status_code == 200, stats_response.text

    payload = stats_response.json()
    assert payload["total"] == 2
    assert payload["by_status"]["proposed"] == 1
    assert payload["by_status"]["accepted"] == 1
    assert payload["by_status"]["reviewing"] == 0
    assert payload["by_status"]["cancel_pending"] == 0
    assert payload["by_status"]["rejected"] == 0
    assert payload["by_status"]["cancelled"] == 0
    assert sum(payload["by_status"].values()) == payload["total"]
