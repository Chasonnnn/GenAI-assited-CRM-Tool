from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.enums import Role
from app.db.models import Form, FormSubmission, FormSubmissionFile, Organization
from tests.test_record_capability_access import _record, _revoke, _session
from tests.test_surrogate_permission_access import (
    _client_for_user,
    _create_surrogate,
    _create_user,
)


def _submission_file(
    db,
    *,
    org_id: uuid.UUID,
    scan_status: str = "clean",
    quarantined: bool = False,
    storage_key: str | None = None,
    donor_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    deleted_at: datetime | None = None,
) -> FormSubmissionFile:
    lead_kind = "surrogate" if surrogate_id else "egg_donor"
    form = Form(
        organization_id=org_id,
        name="Donor application",
        status="published",
        purpose="other",
        lead_kind=lead_kind,
        schema_json={"pages": []},
        published_schema_json={"pages": []},
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=org_id,
        form_id=form.id,
        lead_kind=lead_kind,
        donor_id=donor_id,
        surrogate_id=surrogate_id,
        source_mode="shared",
        match_status="linked" if donor_id or surrogate_id else "unmatched",
        status="pending_review",
        answers_json={"full_name": "Local Download Donor"},
        schema_snapshot={"pages": []},
        mapping_snapshot=[],
    )
    db.add(submission)
    db.flush()
    file_record = FormSubmissionFile(
        organization_id=org_id,
        submission_id=submission.id,
        filename="profile.png",
        field_key="profile_photo",
        storage_key=storage_key or f"{org_id}/form-submissions/{submission.id}/profile.png",
        content_type="image/png",
        file_size=8,
        checksum_sha256="a" * 64,
        scan_status=scan_status,
        quarantined=quarantined,
        deleted_at=deleted_at,
    )
    db.add(file_record)
    db.flush()
    return file_record


def _write_file(tmp_path: Path, storage_key: str, content: bytes = b"png-data") -> None:
    path = tmp_path / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.mark.asyncio
async def test_local_download_serves_authorized_form_submission_file(
    authed_client, db, test_org, test_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    donor = _record(db, test_org.id, test_user.id, "donor")
    file_record = _submission_file(db, org_id=test_org.id, donor_id=donor.id)
    _write_file(tmp_path, file_record.storage_key)

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"png-data"


@pytest.mark.asyncio
async def test_local_download_hides_foreign_form_submission_file(
    authed_client, db, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    foreign_org = Organization(
        id=uuid.uuid4(),
        name="Foreign form org",
        slug=f"foreign-form-{uuid.uuid4().hex[:8]}",
    )
    db.add(foreign_org)
    db.flush()
    file_record = _submission_file(db, org_id=foreign_org.id)
    _write_file(tmp_path, file_record.storage_key)

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found"


@pytest.mark.asyncio
async def test_local_download_requires_donor_view_for_form_submission_file(
    authed_client, db, test_org, test_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    file_record = _submission_file(db, org_id=test_org.id)
    _write_file(tmp_path, file_record.storage_key)
    _revoke(db, _session(test_user, test_org), "view_donors")

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_donors"


@pytest.mark.asyncio
async def test_local_download_preserves_surrogate_record_scope(db, test_org, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    owner = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Submission Owner")
    viewer = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Other Intake User")
    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="under_review",
        name="Private Submission Subject",
    )
    file_record = _submission_file(
        db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
    )
    _write_file(tmp_path, file_record.storage_key)

    async with _client_for_user(db, test_org.id, viewer, Role.INTAKE_SPECIALIST) as client:
        response = await client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have access to this surrogate"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scan_status", "quarantined", "scan_enabled", "expected_status", "detail"),
    [
        ("infected", True, False, 403, "File is infected"),
        ("error", True, False, 403, "File failed virus scan"),
        ("clean", True, False, 403, "File is quarantined"),
        ("pending", True, True, 409, "File is still being scanned"),
        ("pending", False, True, 409, "File is still being scanned"),
    ],
)
async def test_local_download_blocks_unsafe_form_submission_file(
    authed_client,
    db,
    test_org,
    tmp_path,
    monkeypatch,
    scan_status,
    quarantined,
    scan_enabled,
    expected_status,
    detail,
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", scan_enabled)
    file_record = _submission_file(
        db,
        org_id=test_org.id,
        scan_status=scan_status,
        quarantined=quarantined,
    )
    _write_file(tmp_path, file_record.storage_key)

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == expected_status
    assert response.json()["detail"] == detail


@pytest.mark.asyncio
async def test_local_download_returns_404_when_form_submission_file_is_missing(
    authed_client, db, test_org, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    file_record = _submission_file(db, org_id=test_org.id)

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found"


@pytest.mark.asyncio
async def test_local_download_hides_deleted_form_submission_file(
    authed_client, db, test_org, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    file_record = _submission_file(
        db,
        org_id=test_org.id,
        deleted_at=datetime.now(UTC),
    )
    _write_file(tmp_path, file_record.storage_key)

    response = await authed_client.get(f"/attachments/local/{file_record.storage_key}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found"


@pytest.mark.asyncio
async def test_local_download_rejects_form_submission_path_traversal(
    authed_client, db, test_org, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    _submission_file(db, org_id=test_org.id, storage_key="../outside.png")

    response = await authed_client.get("/attachments/local/%2E%2E/outside.png")

    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found"
