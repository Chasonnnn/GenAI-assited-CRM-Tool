"""AI job payload tests."""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.db.models import AISettings
from app.services import ai_settings_service, ai_chat_service
from app.services.ai_provider import ChatResponse


@pytest.mark.asyncio
async def test_ai_chat_sync_returns_response(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
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
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        ai_settings_service,
        "get_ai_provider_for_org",
        lambda _db, _org_id, **_kwargs: StubProvider(),
    )

    message = "Email Jane Doe at jane.doe@example.com"
    response = await authed_client.post("/ai/chat", json={"message": message})
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "Ok"


@pytest.mark.asyncio
async def test_ai_chat_async_blocks_when_consent_missing(db, test_org, test_user, monkeypatch):
    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
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
                model="gemini-3-flash-preview",
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
