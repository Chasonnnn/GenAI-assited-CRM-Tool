from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient

from app.core.encryption import hash_email
from app.db.models import AISettings, AIUsageLog, Surrogate
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse
from app.utils.normalization import normalize_email


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


def _create_surrogate(db, org_id, user_id, stage) -> Surrogate:
    email = f"usage-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Usage Test",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@pytest.mark.asyncio
async def test_summarize_surrogate_logs_usage(
    authed_client: AsyncClient, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    _create_ai_settings(db, test_org.id, test_user.id)

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content='{"summary":"Ok","recent_activity":"None","suggested_next_steps":["Next"]}',
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/summarize-surrogate",
        json={"surrogate_id": str(surrogate.id)},
    )
    assert response.status_code == 200

    usage = (
        db.query(AIUsageLog)
        .filter(
            AIUsageLog.organization_id == test_org.id,
            AIUsageLog.user_id == test_user.id,
        )
        .all()
    )
    assert len(usage) == 1
    assert usage[0].model == "gemini-3-flash-preview"


@pytest.mark.asyncio
async def test_draft_email_logs_usage(
    authed_client: AsyncClient, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    _create_ai_settings(db, test_org.id, test_user.id)

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content='{"subject":"Hello","body":"Hi there"}',
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/draft-email",
        json={"surrogate_id": str(surrogate.id), "email_type": "follow_up"},
    )
    assert response.status_code == 200

    usage = (
        db.query(AIUsageLog)
        .filter(
            AIUsageLog.organization_id == test_org.id,
            AIUsageLog.user_id == test_user.id,
        )
        .all()
    )
    assert len(usage) == 1
    assert usage[0].model == "gemini-3-flash-preview"


@pytest.mark.asyncio
async def test_analyze_dashboard_logs_usage(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    _create_ai_settings(db, test_org.id, test_user.id)

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content='{"insights":["Ok"],"recommendations":["Next"]}',
                prompt_tokens=6,
                completion_tokens=3,
                total_tokens=9,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post("/ai/analyze-dashboard")
    assert response.status_code == 200

    usage = (
        db.query(AIUsageLog)
        .filter(
            AIUsageLog.organization_id == test_org.id,
            AIUsageLog.user_id == test_user.id,
        )
        .all()
    )
    assert len(usage) == 1
    assert usage[0].model == "gemini-3-flash-preview"
