from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.db.enums import FormStatus, FormSubmissionStatus
from app.db.models import Form, FormSubmission
from app.services import form_submission_service, interview_service, pdf_export_service


def _create_form(db, *, org_id, user_id) -> Form:
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {"key": "full_name", "label": "Full Name", "type": "text"},
                    {"key": "documents", "label": "Documents", "type": "file"},
                    {
                        "key": "history",
                        "label": "History",
                        "type": "repeatable_table",
                        "columns": [{"key": "year", "label": "Year"}],
                    },
                ],
            }
        ]
    }
    form = Form(
        id=uuid4(),
        organization_id=org_id,
        name="Export Form",
        status=FormStatus.PUBLISHED.value,
        schema_json=schema,
        published_schema_json=schema,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _create_submission(db, *, org_id, form_id) -> FormSubmission:
    submission = FormSubmission(
        id=uuid4(),
        organization_id=org_id,
        form_id=form_id,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        answers_json={
            "full_name": "Candidate A",
            "history": [{"year": 2024}, {"year": 2025}],
        },
        schema_snapshot={
            "pages": [
                {
                    "title": "Basics",
                    "fields": [
                        {"key": "full_name", "label": "Full Name", "type": "text"},
                        {"key": "documents", "label": "Documents", "type": "file"},
                        {
                            "key": "history",
                            "label": "History",
                            "type": "repeatable_table",
                            "columns": [{"key": "year", "label": "Year"}],
                        },
                    ],
                }
            ]
        },
    )
    db.add(submission)
    db.flush()
    return submission


def test_submission_render_helpers(monkeypatch):
    class _FakeFile:
        def __init__(self, filename: str, content_type: str, file_size: int, storage_key: str, quarantined: bool):
            self.filename = filename
            self.content_type = content_type
            self.file_size = file_size
            self.storage_key = storage_key
            self.quarantined = quarantined

    monkeypatch.setattr(
        pdf_export_service,
        "_load_file_bytes",
        lambda _key: (b"image-bytes", "image/png"),
    )

    files = pdf_export_service._collect_submission_files(
        [
            _FakeFile("photo.png", "image/png", 256, "photo", False),
            _FakeFile("skip.pdf", "application/pdf", 512, "skip", True),
        ]
    )
    assert len(files) == 1
    assert files[0]["data_url"] is not None

    html = pdf_export_service._generate_submission_html(
        title="Profile Card Export",
        surrogate_name="Candidate A",
        org_name="Test Org",
        schema={
            "pages": [
                {
                    "title": "Basics",
                    "fields": [
                        {"key": "full_name", "label": "Full Name", "type": "text"},
                        {"key": "documents", "label": "Documents", "type": "file"},
                        {
                            "key": "history",
                            "label": "History",
                            "type": "repeatable_table",
                            "columns": [{"key": "year", "label": "Year"}],
                        },
                    ],
                }
            ]
        },
        answers={"full_name": "Candidate A", "history": [{"year": "2024"}], "org_name": "Test Org"},
        files=files,
        hidden_fields={"documents"},
        header_note="Welcome {{org_name}}",
        custom_qas=[{"order": 1, "question": "Q1", "answer": "A1"}],
    )
    assert "Profile Card Export" in html
    assert "Custom Details" in html
    assert "********" in html
    assert "repeatable-table" in html


def test_interview_export_html_helpers(monkeypatch):
    monkeypatch.setattr(pdf_export_service.tiptap_service, "tiptap_to_text", lambda _json: "Transcript text")

    export_html = pdf_export_service._generate_interview_export_html(
        title="Interview Export",
        surrogate_name="Candidate A",
        org_name="Test Org",
        exports=[
            {
                "interview": {
                    "interview_type": "phone",
                    "status": "completed",
                    "conducted_at": datetime.now(timezone.utc),
                    "conducted_by_name": "Owner",
                    "duration_minutes": 30,
                    "transcript_json": {"type": "doc", "content": []},
                    "is_transcript_offloaded": False,
                },
                "notes": [
                    {
                        "author_name": "Owner",
                        "created_at": datetime.now(timezone.utc),
                        "anchor_text": "General",
                        "content": "<p>Note body</p>",
                        "replies": [],
                    }
                ],
                "attachments": [{"filename": "doc.pdf", "file_size": 1234}],
            }
        ],
    )

    assert "Interview Export" in export_html
    assert "Transcript text" in export_html
    assert "doc.pdf" in export_html


def test_export_submission_pdf_and_export_interviews_pdf(db, test_org, test_user, monkeypatch):
    form = _create_form(db, org_id=test_org.id, user_id=test_user.id)
    submission = _create_submission(db, org_id=test_org.id, form_id=form.id)

    monkeypatch.setattr(form_submission_service, "list_submission_files", lambda *_args, **_kwargs: [])

    async def _fake_render_html_to_pdf(_html: str) -> bytes:
        return b"%PDF-1.7 export"

    monkeypatch.setattr(pdf_export_service, "_render_html_to_pdf", _fake_render_html_to_pdf)

    submission_pdf = pdf_export_service.export_submission_pdf(
        db=db,
        submission_id=submission.id,
        org_id=test_org.id,
        surrogate_name="Candidate A",
        org_name="Test Org",
    )
    assert submission_pdf.startswith(b"%PDF")

    interview = SimpleNamespace(id=uuid4(), conducted_at=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc))
    monkeypatch.setattr(
        interview_service,
        "build_interview_exports",
        lambda **_kwargs: {
            interview.id: {
                "interview": {
                    "interview_type": "phone",
                    "status": "completed",
                    "conducted_at": datetime.now(timezone.utc),
                    "conducted_by_name": "Owner",
                    "duration_minutes": 15,
                    "transcript_json": None,
                    "is_transcript_offloaded": False,
                },
                "notes": [],
                "attachments": [],
            }
        },
    )

    interviews_pdf = pdf_export_service.export_interviews_pdf(
        db=db,
        org_id=test_org.id,
        interviews=[interview],
        surrogate_name="Candidate A",
        org_name="Test Org",
        current_user_id=test_user.id,
    )
    assert interviews_pdf.startswith(b"%PDF")
