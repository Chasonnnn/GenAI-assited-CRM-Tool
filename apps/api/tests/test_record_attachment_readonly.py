"""Attachment read access does not require permission to edit its subject."""

import pytest

from app.core.config import settings
from app.db.models import Attachment
from tests.test_record_capability_access import _record, _revoke, _session


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_view_only_can_download_signed_and_local_attachment(
    authed_client, db, test_user, test_org, tmp_path, monkeypatch, kind
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    record = _record(db, test_org.id, test_user.id, kind)
    storage_key = "synthetic/test.txt"
    path = tmp_path / storage_key
    path.parent.mkdir(parents=True)
    path.write_text("test")
    attachment = Attachment(
        organization_id=test_org.id,
        **{f"{kind}_id": record.id},
        uploaded_by_user_id=test_user.id,
        filename="test.txt",
        storage_key=storage_key,
        content_type="text/plain",
        file_size=4,
        checksum_sha256="a" * 64,
        scan_status="clean",
    )
    db.add(attachment)
    db.flush()
    _revoke(db, _session(test_user, test_org), f"edit_{kind}s")

    signed = await authed_client.get(f"/attachments/{attachment.id}/download")
    assert signed.status_code == 200, signed.text
    local = await authed_client.get(f"/attachments/local/{storage_key}")
    assert local.status_code == 200, local.text
    assert local.text == "test"
