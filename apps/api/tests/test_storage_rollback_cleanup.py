import io
import os
import uuid

from PIL import Image
from starlette.datastructures import UploadFile, Headers

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.models import Form, FormSubmission, FormSubmissionFile, Surrogate
from app.services import attachment_service
from app.services import form_submission_service
from app.services.form_submission_service import _store_submission_file
from app.utils.normalization import normalize_email


def _create_surrogate(db, org_id, stage_id, status_label):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    surrogate = Surrogate(
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        organization_id=org_id,
        stage_id=stage_id,
        status_label=status_label,
        owner_type="user",
        owner_id=uuid.uuid4(),
        full_name="Test Surrogate",
        email=normalize_email(email),
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_valid_png() -> bytes:
    img = Image.new("RGB", (1, 1), color="red")
    f = io.BytesIO()
    img.save(f, format="PNG")
    return f.getvalue()


def test_attachment_file_cleanup_on_rollback(
    db, test_org, test_user, default_stage, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    surrogate = _create_surrogate(db, test_org.id, default_stage.id, default_stage.label)

    file_obj = io.BytesIO(_create_valid_png())
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="doc.png",
        content_type="image/png",
        file=file_obj,
        file_size=len(file_obj.getvalue()),
        surrogate_id=surrogate.id,
    )

    stored_path = os.path.join(str(tmp_path), attachment.storage_key)
    assert os.path.exists(stored_path)

    db.rollback()

    assert not os.path.exists(stored_path)


def test_form_submission_file_cleanup_on_rollback(
    db, test_org, default_stage, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)

    surrogate = _create_surrogate(db, test_org.id, default_stage.id, default_stage.label)

    form = Form(
        organization_id=test_org.id,
        name="Test Form",
        status="draft",
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        answers_json={},
    )
    db.add(submission)
    db.flush()

    upload = UploadFile(
        filename="upload.png",
        file=io.BytesIO(_create_valid_png()),
        headers=Headers({"content-type": "image/png"}),
    )

    register_called = {"value": False}
    original_register = form_submission_service.register_storage_cleanup_on_rollback

    def _wrapped_register(session, key: str) -> None:
        register_called["value"] = True
        original_register(session, key)

    monkeypatch.setattr(
        form_submission_service, "register_storage_cleanup_on_rollback", _wrapped_register
    )

    assert (
        _store_submission_file.__globals__["register_storage_cleanup_on_rollback"]
        is form_submission_service.register_storage_cleanup_on_rollback
    )

    _store_submission_file(db, submission, upload, form, field_key="supporting_docs")
    db.flush()

    assert register_called["value"] is True

    record = (
        db.query(FormSubmissionFile)
        .filter(FormSubmissionFile.submission_id == submission.id)
        .first()
    )
    assert record is not None

    stored_path = os.path.join(str(tmp_path), record.storage_key)
    assert os.path.exists(stored_path)

    called = {"value": False}
    original_delete = attachment_service.delete_file

    def _wrapped_delete(key: str) -> None:
        called["value"] = True
        original_delete(key)

    monkeypatch.setattr(attachment_service, "delete_file", _wrapped_delete)

    db.rollback()

    assert called["value"] is True
    assert not os.path.exists(stored_path)
