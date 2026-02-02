import io

import pytest
from PIL import Image

from app.core.config import settings
from app.services import platform_branding_service


def _strip_api_base(url: str) -> str:
    base = (settings.API_BASE_URL or "").rstrip("/")
    if base and url.startswith(base):
        return url[len(base) :]
    return url


@pytest.mark.asyncio
async def test_platform_logo_upload_updates_branding(
    authed_client, db, test_auth, monkeypatch, tmp_path
):
    test_auth.user.is_platform_admin = True
    db.commit()

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    response = await authed_client.post(
        "/platform/email/branding/logo",
        files={"file": ("logo.png", buf.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "logo_url" in data
    assert "/platform/email/branding/logo/local/" in data["logo_url"]

    branding = platform_branding_service.get_branding(db)
    assert branding.logo_url == data["logo_url"]


@pytest.mark.asyncio
async def test_platform_logo_local_route_serves_file(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    storage_key = "logos/platform/logo.png"
    file_path = tmp_path / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = b"fake-png-data"
    file_path.write_bytes(content)

    branding = platform_branding_service.get_branding(db)
    branding.logo_url = _strip_api_base(
        f"{(settings.API_BASE_URL or '').rstrip('/')}/platform/email/branding/logo/local/{storage_key}"
    )
    db.add(branding)
    db.flush()

    response = await client.get(f"/platform/email/branding/logo/local/{storage_key}")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers.get("content-type", "").startswith("image/png")


@pytest.mark.asyncio
async def test_platform_logo_local_route_404_for_unknown_logo(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    storage_key = "logos/platform/missing.png"

    response = await client.get(f"/platform/email/branding/logo/local/{storage_key}")

    assert response.status_code == 404
