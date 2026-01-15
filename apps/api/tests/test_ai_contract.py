"""Contract tests for AI endpoints.

These tests ensure the frontend/backend API contract stays stable for:
- POST /ai/settings/test
- POST /ai/consent/accept
- POST /ai/chat (proposed_actions must include approval_id)
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.encryption import hash_email
from app.db.models import AIActionApproval, AISettings, Surrogate
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_ai_settings_test_contract(authed_client: AsyncClient, monkeypatch):
    async def fake_test_api_key(provider: str, api_key: str) -> bool:  # noqa: ARG001
        return True

    monkeypatch.setattr(ai_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.post(
        "/ai/settings/test",
        json={"provider": "openai", "api_key": "sk-test"},
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True}


@pytest.mark.asyncio
async def test_ai_consent_accept_contract(db, authed_client: AsyncClient, test_auth):
    response = await authed_client.post("/ai/consent/accept")
    assert response.status_code == 200

    data = response.json()
    assert data["accepted"] is True
    assert data["accepted_by"] == str(test_auth.user.id)
    assert data["accepted_at"]

    settings = db.query(AISettings).filter(AISettings.organization_id == test_auth.org.id).first()
    assert settings is not None
    assert settings.consent_accepted_by == test_auth.user.id
    assert settings.consent_accepted_at is not None


@pytest.mark.asyncio
async def test_ai_chat_returns_approval_id_per_action(
    db, authed_client: AsyncClient, test_auth, default_stage, monkeypatch
):
    # Minimal case required by /ai/chat contract
    email = f"case-{uuid.uuid4().hex[:8]}@test.com"
    case = Surrogate(
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        organization_id=test_auth.org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_auth.user.id,
        full_name="Test Case",
        email=normalize_email(email),
        email_hash=hash_email(email),
    )
    db.add(case)
    db.flush()

    # Minimal AI settings (chat service expects the row to exist for limits/privacy)
    ai_settings = AISettings(
        organization_id=test_auth.org.id,
        is_enabled=False,  # Avoid consent gating in router
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
    )
    db.add(ai_settings)
    db.flush()

    class StubProvider:
        async def chat(self, messages):  # noqa: ARG002
            return ChatResponse(
                content=('Sure.\n<action>{"type":"add_note","content":"Test note"}</action>'),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        ai_settings_service,
        "get_ai_provider_for_org",
        lambda _db, _org_id: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/chat",
        json={
            "entity_type": "case",
            "entity_id": str(case.id),
            "message": "Add a note please",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload.get("proposed_actions"), list)
    assert len(payload["proposed_actions"]) == 1

    action = payload["proposed_actions"][0]
    assert action["action_type"] == "add_note"
    assert action["status"] == "pending"
    assert isinstance(action["action_data"], dict)
    assert action["action_data"]["type"] == "add_note"
    assert action["action_data"]["content"] == "Test note"

    approval_id = uuid.UUID(action["approval_id"])
    approval = db.query(AIActionApproval).filter(AIActionApproval.id == approval_id).first()
    assert approval is not None
    assert approval.action_type == "add_note"
    assert approval.status == "pending"
