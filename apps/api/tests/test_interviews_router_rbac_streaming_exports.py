from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models import AISettings, Surrogate
from app.routers import interviews as interviews_router
from app.schemas.interview import InterviewCreate
from app.services import ai_settings_service, interview_service, pdf_export_service


@pytest.fixture
def interview_surrogate(db, test_org, test_user, default_stage):
    surrogate = Surrogate(
        id=uuid4(),
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label="new_unread",
        source="manual",
        owner_type="user",
        owner_id=test_user.id,
        full_name="Interview Candidate",
        email=f"interview-{uuid4().hex[:8]}@example.com",
        email_hash=uuid4().hex * 2,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_interview(db, org_id, surrogate_id, user_id):
    data = InterviewCreate(
        interview_type="phone",
        conducted_at=datetime.now(timezone.utc),
        duration_minutes=20,
        transcript_json={
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Transcript"}]}],
        },
        status="completed",
    )
    interview = interview_service.create_interview(
        db=db,
        org_id=org_id,
        surrogate_id=surrogate_id,
        user_id=user_id,
        data=data,
    )
    db.commit()
    db.refresh(interview)
    return interview


def test_interview_permission_helpers(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        interviews_router._check_admin_only(SimpleNamespace(role="intake_specialist"))
    assert exc.value.status_code == 403

    interviews_router._check_admin_only(SimpleNamespace(role="developer"))

    surrogate = SimpleNamespace()
    session = SimpleNamespace(user_id=uuid4(), role="developer", org_id=uuid4())

    monkeypatch.setattr(interviews_router, "can_modify_surrogate", lambda *_args, **_kwargs: False)
    with pytest.raises(HTTPException) as forbidden:
        interviews_router._check_can_modify_interview(surrogate, session, db=None)
    assert forbidden.value.status_code == 403

    monkeypatch.setattr(interviews_router, "can_modify_surrogate", lambda *_args, **_kwargs: True)
    interviews_router._check_can_modify_interview(surrogate, session, db=None)


@pytest.mark.asyncio
async def test_interview_export_endpoint_returns_pdf(
    authed_client, db, test_org, test_user, interview_surrogate, monkeypatch
):
    interview = _create_interview(db, test_org.id, interview_surrogate.id, test_user.id)

    monkeypatch.setattr(pdf_export_service, "export_interview_pdf", lambda **_kwargs: b"%PDF-1.7 export")

    response = await authed_client.get(f"/interviews/{interview.id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_interview_summarize_stream_endpoint_returns_sse(
    authed_client, db, test_org, test_user, interview_surrogate, monkeypatch
):
    interview = _create_interview(db, test_org.id, interview_surrogate.id, test_user.id)

    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        anonymize_pii=False,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.commit()

    class _Chunk:
        def __init__(self, text: str, is_final: bool, prompt_tokens: int = 0, completion_tokens: int = 0):
            self.text = text
            self.is_final = is_final
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens
            self.model = "gemini-3-flash-preview"

    class _Provider:
        async def stream_chat(self, **_kwargs):
            yield _Chunk('{"summary":"Done"', False)
            yield _Chunk(',"key_points":[],"concerns":[],"sentiment":"neutral","follow_up_items":[]}', True, 12, 7)

    from app.services import ai_interview_service

    monkeypatch.setattr(ai_interview_service, "is_consent_required", lambda _settings: False)
    monkeypatch.setattr(ai_interview_service, "get_provider", lambda *_args, **_kwargs: _Provider())
    monkeypatch.setattr(
        ai_interview_service,
        "_parse_json_response",
        lambda _text: {
            "summary": "Done",
            "key_points": [],
            "concerns": [],
            "sentiment": "neutral",
            "follow_up_items": [],
        },
    )

    response = await authed_client.post(f"/interviews/{interview.id}/ai/summarize/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payload = response.text
    assert "event: done" in payload
    assert "Done" in payload
