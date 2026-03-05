import pytest


@pytest.mark.asyncio
async def test_public_signature_logo_allows_cross_origin_embedding(
    client, db, test_org, monkeypatch
):
    from app.services import media_service

    test_org.signature_logo_url = "logos/test-signature.png"
    db.add(test_org)
    db.commit()

    monkeypatch.setattr(
        media_service,
        "get_signed_media_url",
        lambda _storage_key: "https://cdn.example.com/signature.png",
    )

    response = await client.get(
        f"/forms/public/{test_org.id}/signature-logo", follow_redirects=False
    )

    assert response.status_code == 307
    assert response.headers.get("cross-origin-resource-policy") == "cross-origin"


@pytest.mark.asyncio
async def test_non_public_routes_keep_same_origin_resource_policy(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers.get("cross-origin-resource-policy") == "same-origin"
