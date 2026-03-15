from io import BytesIO
import uuid

import pytest
from starlette.datastructures import Headers, UploadFile

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.enums import OwnerType, SurrogateSource
from app.db.models import Form, FormSubmission, FormSubmissionFile, Surrogate
from app.services import attachment_service, form_submission_service
from app.utils.normalization import normalize_email


def test_sanitize_csv_escapes_formula_cells_and_preserves_structure():
    sanitized = attachment_service.sanitize_csv(
        BytesIO(b'name,formula\n"Alice, Jr.",=2+2\nBob,@cmd\n')
    )

    assert sanitized.read().decode("utf-8") == (
        "name,formula\r\n\"Alice, Jr.\",'=2+2\r\nBob,'@cmd\r\n"
    )


def test_sanitize_csv_rejects_malformed_input():
    with pytest.raises(ValueError, match="Invalid CSV file"):
        attachment_service.sanitize_csv(BytesIO(b'name,formula\n"Alice,=2+2\n'))


def test_upload_attachment_sanitizes_csv_before_storage(
    db, test_org, test_user, default_stage, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)

    normalized_email = normalize_email("csv-upload@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        source=SurrogateSource.MANUAL.value,
        full_name="CSV Upload",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="danger.csv",
        content_type="text/csv",
        file=BytesIO(b"name,formula\nAlice,=2+2\n"),
        file_size=len(b"name,formula\nAlice,=2+2\n"),
        surrogate_id=surrogate.id,
    )
    db.flush()

    stored = attachment_service.load_file_bytes(attachment.storage_key).decode("utf-8")
    assert stored == "name,formula\r\nAlice,'=2+2\r\n"


def test_store_submission_file_sanitizes_csv_before_storage(
    db, test_org, test_user, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)

    form = Form(
        organization_id=test_org.id,
        name="Submission Sanitizer",
        status="published",
        created_by_user_id=test_user.id,
        updated_by_user_id=test_user.id,
        schema_json={"pages": []},
        published_schema_json={"pages": []},
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        answers_json={},
    )
    db.add(submission)
    db.flush()

    upload = UploadFile(
        filename="danger.csv",
        file=BytesIO(b"name,formula\nAlice,=2+2\n"),
        headers=Headers({"content-type": "text/csv"}),
    )

    form_submission_service._store_submission_file(
        db=db,
        submission=submission,
        file=upload,
        form=form,
        field_key="supporting_docs",
        content_type="text/csv",
    )
    db.flush()

    record = (
        db.query(FormSubmissionFile).filter(FormSubmissionFile.submission_id == submission.id).one()
    )
    stored = attachment_service.load_file_bytes(record.storage_key).decode("utf-8")

    assert stored == "name,formula\r\nAlice,'=2+2\r\n"
