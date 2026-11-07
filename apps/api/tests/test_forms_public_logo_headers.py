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
    assert response.headers.get("cache-control") == "public, max-age=3600"


@pytest.mark.asyncio
async def test_non_public_routes_keep_same_origin_resource_policy(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers.get("cross-origin-resource-policy") == "same-origin"


@pytest.mark.asyncio
async def test_public_form_logo_rejects_storage_key_outside_local_root(
    client, db, test_org, monkeypatch, tmp_path
):
    import uuid

    from app.core.config import settings
    from app.db.models import FormLogo

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    (tmp_path / "outside.png").write_bytes(b"outside-root")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(storage_root), raising=False)

    logo = FormLogo(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        storage_key="../outside.png",
        filename="outside.png",
        content_type="image/png",
        file_size=12,
    )
    db.add(logo)
    db.flush()

    response = await client.get(f"/forms/public/{test_org.id}/logos/{logo.id}")

    assert response.status_code == 404
    assert response.content != b"outside-root"
