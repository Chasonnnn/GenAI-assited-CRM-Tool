"""AI job payload tests."""

from datetime import datetime, timezone
import json
import uuid

import pytest
from httpx import AsyncClient

from app.db.models import AISettings, Job
from app.services import ai_settings_service, ai_chat_service
from app.services.ai_provider import ChatResponse


@pytest.mark.asyncio
async def test_ai_chat_async_payload_encrypted_and_scrubbed(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content="Ok",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        ai_settings_service,
        "get_ai_provider_for_org",
        lambda _db, _org_id, **_kwargs: StubProvider(),
    )

    message = "Email Jane Doe at jane.doe@example.com"
    response = await authed_client.post("/ai/chat/async", json={"message": message})
    assert response.status_code == 202

    job_id = uuid.UUID(response.json()["job_id"])
    job = db.query(Job).filter(Job.id == job_id).first()
    assert job is not None

    payload = job.payload or {}
    assert payload.get("message") is None
    assert payload.get("message_encrypted") is not None
    assert message not in json.dumps(payload)

    from app.worker import process_ai_chat

    await process_ai_chat(db, job)
    db.commit()
    db.refresh(job)

    payload = job.payload or {}
    assert "message" not in payload
    assert "message_encrypted" not in payload


@pytest.mark.asyncio
async def test_ai_chat_async_blocks_when_consent_missing(
    db, test_org, test_user, monkeypatch
):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        consent_accepted_at=None,
        consent_accepted_by=None,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()

    called = {"chat": False}

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            called["chat"] = True
            return ChatResponse(
                content="Ok",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    result = await ai_chat_service.chat_async(
        db=db,
        organization_id=test_org.id,
        user_id=test_user.id,
        entity_type="global",
        entity_id=test_user.id,
        message="Hello there",
        user_integrations=[],
    )

    assert "consent" in result["content"].lower()
    assert called["chat"] is False
