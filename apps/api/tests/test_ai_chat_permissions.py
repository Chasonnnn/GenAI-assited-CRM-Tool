from datetime import datetime, timezone
import uuid

import pytest

from app.db.enums import Role
from app.db.models import AISettings, Membership, User
from app.services import ai_settings_service, ai_chat_service
from app.services.ai_provider import ChatResponse


@pytest.mark.asyncio
async def test_global_chat_performance_requires_view_reports(db, test_org, test_user, monkeypatch):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=intake_user.id,
        organization_id=test_org.id,
        role=Role.INTAKE_SPECIALIST,
    )
    db.add(membership)
    db.flush()

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

    called = {"performance": False}

    def fake_get_cached_performance_by_user(**_kwargs):
        called["performance"] = True
        return {"data": []}

    monkeypatch.setattr(
        "app.services.analytics_service.get_cached_performance_by_user",
        fake_get_cached_performance_by_user,
    )

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
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
        user_id=intake_user.id,
        entity_type="global",
        entity_id=intake_user.id,
        message="How is team performance this quarter?",
        user_integrations=[],
    )

    assert result["content"] == "Ok"
    assert called["performance"] is False
    combined = "\n".join(msg.content for msg in captured)
    assert "Team Performance" not in combined
