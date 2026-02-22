from __future__ import annotations

import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.db.enums import FormStatus
from app.db.models import Form
from app.services import form_submission_service


def _make_form(*, allowed_mime_types: list[str] | None) -> Form:
    return Form(
        organization_id=uuid.uuid4(),
        name="Test Form",
        description=None,
        status=FormStatus.PUBLISHED.value,
        max_file_size_bytes=10 * 1024 * 1024,
        max_file_count=10,
        allowed_mime_types=allowed_mime_types,
    )


def _make_upload(*, filename: str, content_type: str, data: bytes) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(data),
        headers=Headers({"content-type": content_type}),
    )


def test_validate_file_rejects_exe_even_if_content_type_spoofed():
    form = _make_form(allowed_mime_types=["application/pdf"])
    upload = _make_upload(
        filename="malware.exe",
        content_type="application/pdf",  # spoofed multipart header
        data=b"MZ" + b"\x00" * 128,
    )

    with pytest.raises(ValueError):
        form_submission_service._validate_file(form, upload)


def test_validate_file_rejects_mz_signature_even_with_pdf_extension():
    form = _make_form(allowed_mime_types=["application/pdf"])
    upload = _make_upload(
        filename="malware.pdf",
        content_type="application/pdf",
        data=b"MZ" + b"\x00" * 128,
    )

    with pytest.raises(ValueError):
        form_submission_service._validate_file(form, upload)


def test_validate_file_accepts_valid_pdf():
    form = _make_form(allowed_mime_types=["application/pdf"])
    upload = _make_upload(
        filename="resume.pdf",
        content_type="application/octet-stream",  # header is untrusted
        data=b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n",
    )

    form_submission_service._validate_file(form, upload)


def test_validate_file_rejects_exe_when_form_allowed_mime_types_is_none():
    form = _make_form(allowed_mime_types=None)
    upload = _make_upload(
        filename="malware.exe",
        content_type="application/pdf",
        data=b"MZ" + b"\x00" * 128,
    )

    with pytest.raises(ValueError):
        form_submission_service._validate_file(form, upload)


def test_validate_file_accepts_plain_text_when_form_allows_text_plain():
    form = _make_form(allowed_mime_types=["text/plain"])
    upload = _make_upload(
        filename="notes.txt",
        content_type="text/plain",
        data=b"intake notes for candidate",
    )

    content_type = form_submission_service._validate_file(form, upload)
    assert content_type == "text/plain"


def test_validate_file_accepts_custom_binary_type_when_allowed():
    form = _make_form(allowed_mime_types=["image/gif"])
    upload = _make_upload(
        filename="profile.gif",
        content_type="image/gif",
        data=b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!",
    )

    content_type = form_submission_service._validate_file(form, upload)
    assert content_type == "image/gif"
