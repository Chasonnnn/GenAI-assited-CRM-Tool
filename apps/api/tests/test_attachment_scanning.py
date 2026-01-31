from datetime import datetime, timezone
from io import BytesIO
import uuid

from fastapi import UploadFile
from app.core.config import settings
from app.core.encryption import hash_email
from app.db.enums import JobType
from app.db.models import Attachment, Form, FormSubmission, Job, Surrogate
from app.jobs import scan_attachment
from app.services import attachment_service, form_submission_service
from app.utils.normalization import normalize_email
from sqlalchemy.orm import sessionmaker


def test_upload_attachment_enqueues_scan_job(db, test_org, test_user, default_stage, monkeypatch):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(attachment_service, "store_file", lambda *_args, **_kwargs: None)

    normalized_email = normalize_email("scan@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Scan Test",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    payload = b"%PDF-1.4"
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="scan.pdf",
        content_type="application/pdf",
        file=BytesIO(payload),
        file_size=len(payload),
        surrogate_id=surrogate.id,
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ATTACHMENT_SCAN.value,
        )
        .first()
    )
    assert job is not None
    assert job.payload.get("attachment_id") == str(attachment.id)


def test_scan_attachment_fail_closed_when_scanner_missing_non_dev(
    db, test_org, test_user, default_stage, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ENV", "production", raising=False)

    normalized_email = normalize_email("scan-closed@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Scan Fail Closed",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    attachment = Attachment(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_id=surrogate.id,
        uploaded_by_user_id=test_user.id,
        filename="scan.pdf",
        storage_key="test/scan.pdf",
        content_type="application/pdf",
        file_size=12,
        checksum_sha256="0" * 64,
        scan_status="pending",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()
    db.commit()

    temp_file = tmp_path / "scan.pdf"
    temp_file.write_bytes(b"%PDF-1.4")

    test_session_factory = sessionmaker(bind=db.connection())
    monkeypatch.setattr(scan_attachment, "SessionLocal", test_session_factory)
    monkeypatch.setattr(
        scan_attachment, "_download_to_temp", lambda *_args, **_kwargs: str(temp_file)
    )
    monkeypatch.setattr(
        scan_attachment,
        "_run_clamav_scan",
        lambda *_args, **_kwargs: ("scanner_not_available", "missing"),
    )

    result = scan_attachment.scan_attachment_job(attachment.id)

    db.refresh(attachment)
    assert result is True
    assert attachment.scan_status == "error"
    assert attachment.quarantined is True


def test_form_submission_file_enqueues_scan_job(db, test_org, test_user, default_stage, monkeypatch):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(form_submission_service, "store_file", lambda *_args, **_kwargs: None)

    normalized_email = normalize_email("scan-form@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Scan Form",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)

    schema = {
        "pages": [
            {
                "title": "Docs",
                "fields": [
                    {
                        "key": "supporting_docs",
                        "label": "Supporting Docs",
                        "type": "file",
                        "required": False,
                    }
                ],
            }
        ]
    }

    form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Submission Form",
        description="Test",
        status="published",
        published_schema_json=schema,
        max_file_size_bytes=10 * 1024 * 1024,
        max_file_count=10,
        created_by_user_id=test_user.id,
        updated_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        status="pending_review",
        answers_json={},
        schema_snapshot=schema,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    db.flush()

    upload = UploadFile(
        filename="doc.pdf",
        file=BytesIO(b"%PDF-1.4"),
        headers={"content-type": "application/pdf"},
    )
    file_record = form_submission_service.add_submission_file(
        db=db,
        org_id=test_org.id,
        submission=submission,
        file=upload,
        field_key="supporting_docs",
        user_id=test_user.id,
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.FORM_SUBMISSION_FILE_SCAN.value,
        )
        .first()
    )
    assert job is not None
    assert job.payload.get("submission_file_id") == str(file_record.id)
