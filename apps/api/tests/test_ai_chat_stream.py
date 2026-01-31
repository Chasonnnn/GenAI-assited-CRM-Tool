from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.db.models import AIMessage, AISettings
from app.services import ai_settings_service
from app.services.ai_provider import ChatStreamChunk


def _create_ai_settings(db, org_id, user_id) -> AISettings:
    settings = AISettings(
        organization_id=org_id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=user_id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()
    return settings


@pytest.mark.asyncio
async def test_chat_stream_returns_events(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    _create_ai_settings(db, test_org.id, test_user.id)

    class StubProvider:
        async def stream_chat(self, messages, **kwargs):  # noqa: ARG002
            yield ChatStreamChunk(text="Hello", model="gemini-3-flash-preview")
            yield ChatStreamChunk(text=" world", model="gemini-3-flash-preview")
            yield ChatStreamChunk(
                text="",
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                model="gemini-3-flash-preview",
                is_final=True,
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post("/ai/chat/stream", json={"message": "Hi"})
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")
    body = response.text
    assert "event: delta" in body
    assert "Hello" in body
    assert "event: done" in body

    messages = db.query(AIMessage).all()
    assert any(msg.role == "assistant" for msg in messages)
