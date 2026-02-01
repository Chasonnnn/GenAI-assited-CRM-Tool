import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import attachment_service
from app.utils.normalization import normalize_email


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
