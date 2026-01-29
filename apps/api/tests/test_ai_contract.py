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
from app.db.models import AIActionApproval, AISettings, Surrogate, AIEntitySummary
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_ai_settings_test_contract(authed_client: AsyncClient, monkeypatch):
    async def fake_test_api_key(provider: str, api_key: str, **_kwargs) -> bool:  # noqa: ARG001
        return True

    monkeypatch.setattr(ai_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.post(
        "/ai/settings/test",
        json={"provider": "openai", "api_key": "sk-test"},
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True}


@pytest.mark.asyncio
async def test_ai_settings_test_accepts_vertex_api_key(authed_client: AsyncClient, monkeypatch):
    async def fake_test_api_key(provider: str, api_key: str, **_kwargs) -> bool:  # noqa: ARG001
        return provider == "vertex_api_key" and api_key == "vertex-key"

    monkeypatch.setattr(ai_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.post(
        "/ai/settings/test",
        json={
            "provider": "vertex_api_key",
            "api_key": "vertex-key",
            "vertex_api_key": {"project_id": None, "location": None},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True}


@pytest.mark.asyncio
async def test_ai_settings_supports_vertex_wif_config(authed_client: AsyncClient):
    settings_response = await authed_client.get("/ai/settings")
    assert settings_response.status_code == 200
    current_version = settings_response.json()["current_version"]

    payload = {
        "provider": "vertex_wif",
        "model": "gemini-3-flash-preview",
        "is_enabled": False,
        "expected_version": current_version,
        "vertex_wif": {
            "project_id": "demo-project",
            "location": "us-central1",
            "service_account_email": "vertex-sa@demo-project.iam.gserviceaccount.com",
            "audience": "//iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/pool/providers/provider",
        },
    }

    response = await authed_client.patch("/ai/settings", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["provider"] == "vertex_wif"
    assert data["vertex_wif"]["project_id"] == payload["vertex_wif"]["project_id"]
    assert data["vertex_wif"]["location"] == payload["vertex_wif"]["location"]
    assert (
        data["vertex_wif"]["service_account_email"]
        == payload["vertex_wif"]["service_account_email"]
    )
    assert data["vertex_wif"]["audience"] == payload["vertex_wif"]["audience"]


@pytest.mark.asyncio
async def test_ai_settings_supports_vertex_api_key_config(authed_client: AsyncClient):
    settings_response = await authed_client.get("/ai/settings")
    assert settings_response.status_code == 200
    current_version = settings_response.json()["current_version"]

    payload = {
        "provider": "vertex_api_key",
        "model": "gemini-3-flash-preview",
        "is_enabled": False,
        "expected_version": current_version,
        "api_key": "vertex-key",
        "vertex_api_key": {"project_id": "demo-project", "location": "us-central1"},
    }

    response = await authed_client.patch("/ai/settings", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["provider"] == "vertex_api_key"
    assert data["vertex_api_key"]["project_id"] == payload["vertex_api_key"]["project_id"]
    assert data["vertex_api_key"]["location"] == payload["vertex_api_key"]["location"]


@pytest.mark.asyncio
async def test_ai_settings_rejects_non_flash_gemini_models(authed_client: AsyncClient):
    settings_response = await authed_client.get("/ai/settings")
    assert settings_response.status_code == 200
    current_version = settings_response.json()["current_version"]

    response = await authed_client.patch(
        "/ai/settings",
        json={
            "provider": "gemini",
            "model": "gemini-3-pro-preview",
            "is_enabled": False,
            "expected_version": current_version,
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"] == "Only gemini-3-flash-preview is supported for this provider."
    )


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


@pytest.mark.asyncio
async def test_ai_chat_anonymizes_case_messages(
    db, authed_client: AsyncClient, test_auth, default_stage, monkeypatch
):
    email = f"case-{uuid.uuid4().hex[:8]}@test.com"
    surrogate = Surrogate(
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
    db.add(surrogate)
    db.flush()

    ai_settings = AISettings(
        organization_id=test_auth.org.id,
        is_enabled=False,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        anonymize_pii=True,
    )
    db.add(ai_settings)
    db.flush()

    captured_messages = []

    class StubProvider:
        async def chat(self, messages):  # noqa: ARG002
            captured_messages.extend(messages)
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
        lambda _db, _org_id: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/chat",
        json={
            "entity_type": "case",
            "entity_id": str(surrogate.id),
            "message": f"Email {surrogate.full_name} at {email}",
        },
    )
    assert response.status_code == 200

    combined = "\n".join(msg.content for msg in captured_messages)
    assert surrogate.full_name not in combined
    assert email not in combined


@pytest.mark.asyncio
async def test_ai_chat_creates_entity_summary(
    db, authed_client: AsyncClient, test_auth, default_stage, monkeypatch
):
    email = f"case-{uuid.uuid4().hex[:8]}@test.com"
    surrogate = Surrogate(
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
    db.add(surrogate)
    db.flush()

    ai_settings = AISettings(
        organization_id=test_auth.org.id,
        is_enabled=False,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
    )
    db.add(ai_settings)
    db.flush()

    class StubProvider:
        async def chat(self, messages):  # noqa: ARG002
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
        lambda _db, _org_id: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/chat",
        json={
            "entity_type": "case",
            "entity_id": str(surrogate.id),
            "message": "Hello",
        },
    )
    assert response.status_code == 200

    summary = (
        db.query(AIEntitySummary)
        .filter(
            AIEntitySummary.organization_id == test_auth.org.id,
            AIEntitySummary.entity_type == "surrogate",
            AIEntitySummary.entity_id == surrogate.id,
        )
        .first()
    )
    assert summary is not None
    assert summary.summary_text
