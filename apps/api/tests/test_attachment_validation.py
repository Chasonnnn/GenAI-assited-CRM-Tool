from io import BytesIO
from unittest.mock import Mock
import uuid

import pytest

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import attachment_service
from app.utils.normalization import normalize_email


def test_validate_file_allows_csv_mp4_mov():
    samples = [
        ("report.csv", "text/csv"),
        ("video.mp4", "video/mp4"),
        ("clip.mov", "video/quicktime"),
    ]

    for filename, content_type in samples:
        is_valid, error = attachment_service.validate_file(
            filename,
            content_type,
            file_size=1024,
        )
        assert is_valid, error


def test_validate_file_rejects_extension_mime_mismatch():
    is_valid, error = attachment_service.validate_file(
        "profile.png",
        "text/csv",
        file_size=1024,
    )

    assert not is_valid
    assert error is not None


def test_store_file_sets_content_type_for_s3_upload(monkeypatch):
    s3 = Mock()

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3", raising=False)
    monkeypatch.setattr(settings, "S3_BUCKET", "test-bucket", raising=False)
    monkeypatch.setattr(attachment_service, "_get_s3_client", lambda: s3)

    attachment_service.store_file("org/key/file.png", BytesIO(b"png-bytes"), "image/png")

    s3.upload_fileobj.assert_called_once()
    _fileobj, bucket, key = s3.upload_fileobj.call_args.args
    extra = s3.upload_fileobj.call_args.kwargs

    assert bucket == "test-bucket"
    assert key == "org/key/file.png"
    assert extra == {"ExtraArgs": {"ContentType": "image/png"}}


@pytest.mark.asyncio
async def test_upload_attachment_returns_clean_error_on_storage_failure(
    authed_client, db, test_org, test_user, default_stage, monkeypatch
):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(attachment_service, "store_file", _boom)

    normalized_email = normalize_email("upload-error@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Upload Error",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    response = await authed_client.post(
        f"/attachments/surrogates/{surrogate.id}/attachments",
        files={"file": ("fail.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to store attachment. Please try again."
