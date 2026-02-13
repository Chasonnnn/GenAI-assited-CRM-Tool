import pytest

from app.services import surrogate_service


@pytest.mark.asyncio
async def test_bulk_assign_does_not_call_get_surrogate_per_id(
    authed_client,
    test_auth,
    monkeypatch,
):
    create_1 = await authed_client.post(
        "/surrogates",
        json={"full_name": "Bulk Assign One", "email": "bulk-assign-one@example.com"},
    )
    assert create_1.status_code == 201, create_1.text
    surrogate_1_id = create_1.json()["id"]

    create_2 = await authed_client.post(
        "/surrogates",
        json={"full_name": "Bulk Assign Two", "email": "bulk-assign-two@example.com"},
    )
    assert create_2.status_code == 201, create_2.text
    surrogate_2_id = create_2.json()["id"]

    def _should_not_be_called(*_args, **_kwargs):
        raise AssertionError("bulk assign should not fetch each surrogate individually")

    monkeypatch.setattr(surrogate_service, "get_surrogate", _should_not_be_called)

    response = await authed_client.post(
        "/surrogates/bulk-assign",
        json={
            "surrogate_ids": [surrogate_1_id, surrogate_2_id],
            "owner_type": "user",
            "owner_id": str(test_auth.user.id),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["assigned"] == 2
    assert payload["failed"] == []
