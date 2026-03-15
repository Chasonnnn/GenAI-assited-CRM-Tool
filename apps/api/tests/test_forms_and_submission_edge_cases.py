from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.routers import forms as forms_router


def _session(org_id, user_id):
    return SimpleNamespace(org_id=org_id, user_id=user_id, role="developer")


def _submission(*, surrogate_id=None):
    return SimpleNamespace(id=uuid4(), surrogate_id=surrogate_id, form_id=uuid4())


def _surrogate():
    return SimpleNamespace(id=uuid4(), full_name="Case Person", surrogate_number="S12345")


def _file_record(*, scan_status="clean", filename="doc.pdf"):
    return SimpleNamespace(
        id=uuid4(),
        filename=filename,
        content_type="application/pdf",
        file_size=128,
        quarantined=False,
        scan_status=scan_status,
        field_key="document",
    )


def test_download_submission_file_branch_paths(monkeypatch, db, test_org, test_user):
    session = _session(test_org.id, test_user.id)
    request = SimpleNamespace(base_url="https://api.example.com/", headers={})
    submission_id = uuid4()
    file_id = uuid4()

    monkeypatch.setattr(forms_router, "check_surrogate_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(forms_router.audit_service, "log_phi_access", lambda **_kwargs: None)

    # Submission missing.
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Submission not found"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    # Submission not linked.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission",
        lambda *_args, **_kwargs: _submission(surrogate_id=None),
    )
    with pytest.raises(HTTPException, match="not linked to a surrogate"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    # Surrogate missing.
    linked = _submission(surrogate_id=uuid4())
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: linked
    )
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Surrogate not found"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    # File missing.
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: _surrogate()
    )
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission_file", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="File not found"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    # Infected / scan error / pending scan.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file",
        lambda *_args, **_kwargs: _file_record(scan_status="infected"),
    )
    with pytest.raises(HTTPException, match="File is infected"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file",
        lambda *_args, **_kwargs: _file_record(scan_status="error"),
    )
    with pytest.raises(HTTPException, match="failed virus scan"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    monkeypatch.setattr(forms_router.settings, "ATTACHMENT_SCAN_ENABLED", True)
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file",
        lambda *_args, **_kwargs: _file_record(scan_status="pending"),
    )
    with pytest.raises(HTTPException, match="still being scanned"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    # URL generation failure then success with relative URL expansion.
    monkeypatch.setattr(forms_router.settings, "ATTACHMENT_SCAN_ENABLED", False)
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file",
        lambda *_args, **_kwargs: _file_record(scan_status="clean"),
    )
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file_download_url",
        lambda **_kwargs: None,
    )
    with pytest.raises(HTTPException, match="Failed to generate download URL"):
        forms_router.download_submission_file(
            submission_id, file_id, request, session=session, db=db
        )

    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file_download_url",
        lambda **_kwargs: "/files/download/signed",
    )
    response = forms_router.download_submission_file(
        submission_id, file_id, request, session=session, db=db
    )
    assert response.download_url == "https://api.example.com/files/download/signed"
    assert response.filename == "doc.pdf"


def test_upload_and_delete_submission_file_branch_paths(monkeypatch, db, test_org, test_user):
    session = _session(test_org.id, test_user.id)
    submission_id = uuid4()
    file_id = uuid4()
    upload = UploadFile(filename="note.txt", file=BytesIO(b"hello"))

    monkeypatch.setattr(forms_router, "check_surrogate_access", lambda *_args, **_kwargs: None)

    # Upload: submission missing.
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Submission not found"):
        forms_router.upload_submission_file(submission_id, upload, None, session=session, db=db)

    # Upload: not linked / surrogate missing.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission",
        lambda *_args, **_kwargs: _submission(surrogate_id=None),
    )
    with pytest.raises(HTTPException, match="not linked to a surrogate"):
        forms_router.upload_submission_file(submission_id, upload, None, session=session, db=db)

    linked = _submission(surrogate_id=uuid4())
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: linked
    )
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Surrogate not found"):
        forms_router.upload_submission_file(submission_id, upload, None, session=session, db=db)

    # Upload: service validation error.
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: _surrogate()
    )
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "add_submission_file",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad file")),
    )
    with pytest.raises(HTTPException, match="bad file"):
        forms_router.upload_submission_file(submission_id, upload, None, session=session, db=db)

    # Upload: success.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "add_submission_file",
        lambda **_kwargs: _file_record(scan_status="clean", filename="note.txt"),
    )
    uploaded = forms_router.upload_submission_file(
        submission_id, upload, "document", session=session, db=db
    )
    assert uploaded.filename == "note.txt"
    assert uploaded.scan_status == "clean"

    # Delete: missing submission.
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Submission not found"):
        forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)

    # Delete: not linked, surrogate missing, file missing.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission",
        lambda *_args, **_kwargs: _submission(surrogate_id=None),
    )
    with pytest.raises(HTTPException, match="not linked to a surrogate"):
        forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)

    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: linked
    )
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Surrogate not found"):
        forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)

    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: _surrogate()
    )
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission_file", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="File not found"):
        forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)

    # Delete: already deleted.
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission_file",
        lambda *_args, **_kwargs: _file_record(),
    )
    monkeypatch.setattr(
        forms_router.form_submission_service,
        "soft_delete_submission_file",
        lambda **_kwargs: False,
    )
    with pytest.raises(HTTPException, match="already deleted"):
        forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)

    monkeypatch.setattr(
        forms_router.form_submission_service,
        "soft_delete_submission_file",
        lambda **_kwargs: True,
    )
    deleted = forms_router.delete_submission_file(submission_id, file_id, session=session, db=db)
    assert deleted == {"deleted": True}


def test_export_submission_pdf_branch_paths(monkeypatch, db, test_org, test_user):
    session = _session(test_org.id, test_user.id)
    submission_id = uuid4()

    monkeypatch.setattr(forms_router, "check_surrogate_access", lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Submission not found"):
        forms_router.export_submission_pdf(submission_id, session=session, db=db)

    monkeypatch.setattr(
        forms_router.form_submission_service,
        "get_submission",
        lambda *_args, **_kwargs: _submission(surrogate_id=None),
    )
    with pytest.raises(HTTPException, match="not linked to a surrogate"):
        forms_router.export_submission_pdf(submission_id, session=session, db=db)

    linked = _submission(surrogate_id=uuid4())
    monkeypatch.setattr(
        forms_router.form_submission_service, "get_submission", lambda *_args, **_kwargs: linked
    )
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: None
    )
    with pytest.raises(HTTPException, match="Surrogate not found"):
        forms_router.export_submission_pdf(submission_id, session=session, db=db)

    surrogate = _surrogate()
    monkeypatch.setattr(
        forms_router.surrogate_service, "get_surrogate", lambda *_args, **_kwargs: surrogate
    )
    monkeypatch.setattr(
        forms_router.org_service,
        "get_org_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(name="Test Org"),
    )

    monkeypatch.setattr(
        "app.services.pdf_export_service.export_submission_pdf",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("invalid template")),
    )
    with pytest.raises(HTTPException, match="invalid template"):
        forms_router.export_submission_pdf(submission_id, session=session, db=db)

    monkeypatch.setattr(
        "app.services.pdf_export_service.export_submission_pdf",
        lambda **_kwargs: b"%PDF-1.4 fake",
    )
    response = forms_router.export_submission_pdf(submission_id, session=session, db=db)
    assert response.media_type == "application/pdf"
    assert "attachment; filename=" in response.headers["Content-Disposition"]
