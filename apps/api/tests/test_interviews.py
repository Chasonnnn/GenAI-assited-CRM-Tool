"""
Tests for interview endpoints and background transcription.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.db.models import Attachment, Surrogate, InterviewAttachment, Job, AISettings
from app.db.enums import JobType
from app.schemas.interview import InterviewCreate, InterviewNoteCreate
from app.services import interview_note_service, interview_service, ai_settings_service
from app.services.ai_provider import ChatResponse


@pytest.fixture
def test_surrogate(db, test_org, test_user, default_stage):
    surrogate = Surrogate(
        id=uuid4(),
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label="new_unread",
        source="manual",
        owner_type="user",
        owner_id=test_user.id,
        full_name="Test Candidate",
        email="candidate@test.com",
        email_hash=uuid4().hex,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _default_transcript_json():
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Transcript"}]},
        ],
    }


_DEFAULT_TRANSCRIPT = object()


def _create_interview(db, org_id, surrogate_id, user_id, transcript_json=_DEFAULT_TRANSCRIPT):
    if transcript_json is _DEFAULT_TRANSCRIPT:
        transcript_json = _default_transcript_json()

    data = InterviewCreate(
        interview_type="phone",
        conducted_at=datetime.now(timezone.utc),
        duration_minutes=30,
        transcript_json=transcript_json,
        status="completed",
    )
    interview = interview_service.create_interview(
        db=db,
        org_id=org_id,
        surrogate_id=surrogate_id,
        user_id=user_id,
        data=data,
    )
    db.flush()
    return interview


@pytest.mark.asyncio
async def test_list_interviews_includes_counts(
    authed_client: AsyncClient, db, test_org, test_user, test_surrogate
):
    interview = _create_interview(db, test_org.id, test_surrogate.id, test_user.id)

    note = interview_note_service.create_note(
        db=db,
        org_id=test_org.id,
        interview=interview,
        user_id=test_user.id,
        data=InterviewNoteCreate(content="<p>Note</p>"),
    )
    db.add(note)

    attachment = Attachment(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_id=test_surrogate.id,
        uploaded_by_user_id=test_user.id,
        filename="audio.mp3",
        storage_key=f"{test_org.id}/{test_surrogate.id}/audio.mp3",
        content_type="audio/mpeg",
        file_size=1234,
        checksum_sha256=uuid4().hex * 2,
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()

    link = InterviewAttachment(
        id=uuid4(),
        interview_id=interview.id,
        attachment_id=attachment.id,
        organization_id=test_org.id,
    )
    db.add(link)
    db.flush()

    response = await authed_client.get(f"/surrogates/{test_surrogate.id}/interviews")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["notes_count"] == 1
    assert item["attachments_count"] == 1
    assert item["has_transcript"] is True
    assert item["transcript_version"] == 1


@pytest.mark.asyncio
async def test_request_transcription_enqueues_job(
    authed_client: AsyncClient, db, test_org, test_user, test_surrogate
):
    interview = _create_interview(
        db, test_org.id, test_surrogate.id, test_user.id, transcript_json=None
    )

    attachment = Attachment(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_id=test_surrogate.id,
        uploaded_by_user_id=test_user.id,
        filename="call.mp3",
        storage_key=f"{test_org.id}/{test_surrogate.id}/call.mp3",
        content_type="audio/mpeg",
        file_size=2048,
        checksum_sha256=uuid4().hex * 2,
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()

    link = InterviewAttachment(
        id=uuid4(),
        interview_id=interview.id,
        attachment_id=attachment.id,
        organization_id=test_org.id,
    )
    db.add(link)
    db.flush()

    response = await authed_client.post(
        f"/interviews/{interview.id}/attachments/{attachment.id}/transcribe",
        json={"language": "en"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.INTERVIEW_TRANSCRIPTION.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload.get("interview_attachment_id") == str(link.id)


@pytest.mark.asyncio
async def test_interview_summary_requires_ai_enabled(
    authed_client: AsyncClient, db, test_org, test_user, test_surrogate
):
    interview = _create_interview(db, test_org.id, test_surrogate.id, test_user.id)

    response = await authed_client.post(f"/interviews/{interview.id}/ai/summarize")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_interview_summary_anonymizes_transcript(
    authed_client: AsyncClient, db, test_org, test_user, test_surrogate, monkeypatch
):
    transcript_json = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Interview with Jane Doe jane.doe@example.com",
                    }
                ],
            }
        ],
    }
    interview = _create_interview(
        db, test_org.id, test_surrogate.id, test_user.id, transcript_json=transcript_json
    )

    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        anonymize_pii=True,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content=(
                    '{"summary":"Ok","key_points":[],"concerns":[],"sentiment":"neutral","follow_up_items":[]}'
                ),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "app.services.ai_interview_service.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post(f"/interviews/{interview.id}/ai/summarize")
    assert response.status_code == 200

    combined = "\n".join(msg.content for msg in captured)
    assert "Jane Doe" not in combined
    assert "jane.doe@example.com" not in combined
