import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import attachment_service
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_attachment_upload_rejects_oversized_file_without_read(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
    monkeypatch,
):
    normalized_email = normalize_email("oversized-upload@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Oversized Upload",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    async def _read_should_not_be_called(*_args, **_kwargs):
        raise AssertionError("UploadFile.read should not be called for oversized attachments")

    monkeypatch.setattr("starlette.datastructures.UploadFile.read", _read_should_not_be_called)

    too_large = b"x" * (attachment_service.MAX_FILE_SIZE_BYTES + 1)
    response = await authed_client.post(
        f"/attachments/surrogates/{surrogate.id}/attachments",
        files={"file": ("too-large.pdf", too_large, "application/pdf")},
    )

    assert response.status_code == 400
    assert "File size exceeds" in response.json()["detail"]


@pytest.mark.asyncio
async def test_avatar_upload_rejects_oversized_file_without_read(authed_client, monkeypatch):
    async def _read_should_not_be_called(*_args, **_kwargs):
        raise AssertionError("UploadFile.read should not be called for oversized avatars")

    monkeypatch.setattr("starlette.datastructures.UploadFile.read", _read_should_not_be_called)

    too_large = b"x" * ((2 * 1024 * 1024) + 1)
    response = await authed_client.post(
        "/auth/me/avatar",
        files={"file": ("too-large.png", too_large, "image/png")},
    )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]
