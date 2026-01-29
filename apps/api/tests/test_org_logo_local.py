import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_local_org_logo_route_serves_file(client, db, test_org, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    storage_key = f"logos/{test_org.id}/logo.png"
    file_path = tmp_path / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = b"fake-png-data"
    file_path.write_bytes(content)

    test_org.signature_logo_url = f"/settings/organization/signature/logo/local/{storage_key}"
    db.add(test_org)
    db.flush()

    response = await client.get(test_org.signature_logo_url)

    assert response.status_code == 200
    assert response.content == content
    assert response.headers.get("content-type", "").startswith("image/png")


@pytest.mark.asyncio
async def test_local_org_logo_route_404_for_unknown_logo(
    client, db, test_org, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    storage_key = f"logos/{test_org.id}/missing.png"

    response = await client.get(f"/settings/organization/signature/logo/local/{storage_key}")

    assert response.status_code == 404
