import uuid

import pytest


@pytest.mark.asyncio
async def test_list_intended_parents_sorts_by_partner_name(authed_client):
    first_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Primary One",
            "email": f"ip-{uuid.uuid4().hex[:8]}@example.com",
            "partner_name": "Zed Partner",
        },
    )
    assert first_res.status_code == 201, first_res.text

    second_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Primary Two",
            "email": f"ip-{uuid.uuid4().hex[:8]}@example.com",
            "partner_name": "Amy Partner",
        },
    )
    assert second_res.status_code == 201, second_res.text

    list_res = await authed_client.get(
        "/intended-parents",
        params={"sort_by": "partner_name", "sort_order": "asc", "per_page": 20},
    )
    assert list_res.status_code == 200, list_res.text

    partner_names = [item["partner_name"] for item in list_res.json()["items"][:2]]
    assert partner_names == ["Amy Partner", "Zed Partner"]

