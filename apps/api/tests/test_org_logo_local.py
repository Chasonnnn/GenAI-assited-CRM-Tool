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


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["post", "delete"])
async def test_signature_logo_change_commits_with_its_audit_row(
    authed_client, db, test_org, monkeypatch, tmp_path, method
):
    import io

    from PIL import Image

    from app.services import audit_service

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    test_org.signature_logo_url = (
        f"/settings/organization/signature/logo/local/logos/{test_org.id}/old.png"
    )
    db.flush()

    commits: list[None] = []
    original_commit = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(None), original_commit())[1])
    audited_after: list[int] = []
    original_audit = audit_service.log_settings_changed

    def audit_spy(**kwargs):
        audited_after.append(len(commits))
        return original_audit(**kwargs)

    monkeypatch.setattr(audit_service, "log_settings_changed", audit_spy)

    if method == "post":
        image = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(image, format="PNG")
        response = await authed_client.post(
            "/settings/organization/signature/logo",
            files={"file": ("logo.png", image.getvalue(), "image/png")},
        )
    else:
        response = await authed_client.delete("/settings/organization/signature/logo")

    assert response.status_code == 200, response.text
    assert audited_after == [0]
    assert len(commits) == 1
