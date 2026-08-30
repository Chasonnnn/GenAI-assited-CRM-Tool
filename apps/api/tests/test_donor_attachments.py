import io
import uuid

import pytest
from PIL import Image

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.models import Attachment, Donor, Organization
from app.services import attachment_service, workflow_triggers


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(30, 120, 180)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _create_donor(client) -> dict:
    response = await client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Photo Donor",
            "email": f"photo-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_profile_photo_reuses_donor_attachment_and_clears_on_delete(
    authed_client, db, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
    donor = await _create_donor(authed_client)
    payload = _png_bytes()

    uploaded = await authed_client.post(
        f"/attachments/donors/{donor['id']}/profile-photo",
        files={"file": ("profile.png", payload, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment = uploaded.json()
    assert attachment["content_type"] == "image/png"
    assert attachment["scan_status"] == "clean"

    detail = await authed_client.get(f"/donors/{donor['id']}")
    assert detail.status_code == 200
    assert detail.json()["profile_photo_attachment_id"] == attachment["id"]

    listed = await authed_client.get(f"/attachments/donors/{donor['id']}/attachments")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [attachment["id"]]

    download = await authed_client.get(f"/attachments/{attachment['id']}/download")
    assert download.status_code == 200, download.text
    assert download.json()["filename"] == "profile.png"

    deleted = await authed_client.delete(f"/attachments/{attachment['id']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True}
    refreshed = await authed_client.get(f"/donors/{donor['id']}")
    assert refreshed.json()["profile_photo_attachment_id"] is None


@pytest.mark.asyncio
async def test_profile_photo_rejects_non_image_and_foreign_donor(
    authed_client, db, test_org, default_stage, test_user
):
    donor = await _create_donor(authed_client)
    rejected = await authed_client.post(
        f"/attachments/donors/{donor['id']}/profile-photo",
        files={"file": ("profile.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert rejected.status_code == 400
    assert (await authed_client.get(f"/donors/{donor['id']}")).json()[
        "profile_photo_attachment_id"
    ] is None

    foreign_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Donor Attachments",
        slug=f"foreign-donor-attachments-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(foreign_org)
    db.flush()
    foreign_email = "foreign-photo@example.com"
    foreign = Donor(
        id=uuid.uuid4(),
        organization_id=foreign_org.id,
        donor_number="D10001",
        donor_type="sperm",
        full_name="Foreign Photo Donor",
        email=foreign_email,
        email_hash=hash_email(foreign_email),
        stage_id=default_stage.id,
    )
    db.add(foreign)
    db.flush()

    foreign_list = await authed_client.get(f"/attachments/donors/{foreign.id}/attachments")
    assert foreign_list.status_code == 404
    foreign_upload = await authed_client.post(
        f"/attachments/donors/{foreign.id}/profile-photo",
        files={"file": ("profile.png", _png_bytes(), "image/png")},
    )
    assert foreign_upload.status_code == 404


@pytest.mark.asyncio
async def test_donor_document_workflow_fires_once_for_immediately_clean_upload(
    authed_client, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
    triggered: list[uuid.UUID] = []
    monkeypatch.setattr(
        workflow_triggers,
        "trigger_document_uploaded",
        lambda _db, attachment: triggered.append(attachment.id),
    )
    donor = await _create_donor(authed_client)

    response = await authed_client.post(
        f"/attachments/donors/{donor['id']}/attachments",
        files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert triggered == [uuid.UUID(response.json()["id"])]


@pytest.mark.asyncio
async def test_donor_document_workflow_waits_for_clean_scan_and_fires_once(
    authed_client, db, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(
        attachment_service,
        "dispatch_attachment_scan_if_needed",
        lambda **_kwargs: False,
    )
    triggered: list[uuid.UUID] = []
    monkeypatch.setattr(
        workflow_triggers,
        "trigger_document_uploaded",
        lambda _db, attachment: triggered.append(attachment.id),
    )
    donor = await _create_donor(authed_client)

    response = await authed_client.post(
        f"/attachments/donors/{donor['id']}/attachments",
        files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    attachment_id = uuid.UUID(response.json()["id"])
    assert triggered == []

    attachment_service.mark_attachment_scanned(db, attachment_id, "clean")
    db.flush()

    assert triggered == [attachment_id]
    assert db.get(Attachment, attachment_id).scan_status == "clean"


@pytest.mark.asyncio
async def test_failed_profile_photo_scan_clears_donor_designation(
    authed_client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(
        attachment_service,
        "dispatch_attachment_scan_if_needed",
        lambda **_kwargs: False,
    )
    donor = await _create_donor(authed_client)
    uploaded = await authed_client.post(
        f"/attachments/donors/{donor['id']}/profile-photo",
        files={"file": ("profile.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment_id = uuid.UUID(uploaded.json()["id"])
    assert (await authed_client.get(f"/donors/{donor['id']}")).json()[
        "profile_photo_attachment_id"
    ] == str(attachment_id)

    attachment_service.mark_attachment_scanned(db, attachment_id, "infected")
    db.commit()

    attachment = db.get(Attachment, attachment_id)
    assert attachment is not None
    assert attachment.scan_status == "infected"
    assert attachment.quarantined is True
    assert (await authed_client.get(f"/donors/{donor['id']}")).json()[
        "profile_photo_attachment_id"
    ] is None
