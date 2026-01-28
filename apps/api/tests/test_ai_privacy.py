"""Privacy tests for AI endpoints."""

from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient

from app.core.encryption import hash_email
from app.db.models import AISettings, Surrogate
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse
from app.utils.normalization import normalize_email


def _create_ai_settings(db, org_id, user_id, *, anonymize_pii=True) -> AISettings:
    settings = AISettings(
        organization_id=org_id,
        is_enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        anonymize_pii=anonymize_pii,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=user_id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()
    return settings


def _create_surrogate(db, org_id, user_id, stage, *, name, email) -> Surrogate:
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
        full_name=name,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@pytest.mark.asyncio
async def test_summarize_surrogate_anonymizes_prompt(
    authed_client: AsyncClient, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        name="Jane Doe",
        email="jane.doe@example.com",
    )
    _create_ai_settings(db, test_org.id, test_user.id, anonymize_pii=True)

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content='{"summary": "Ok", "recent_activity": "None", "suggested_next_steps": ["Next"]}',
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gpt-4o-mini",
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

    combined = "\n".join(msg.content for msg in captured)
    assert surrogate.full_name not in combined
    assert surrogate.email not in combined


@pytest.mark.asyncio
async def test_draft_email_anonymizes_prompt_and_rehydrates(
    authed_client: AsyncClient, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        name="Jane Doe",
        email="jane.doe@example.com",
    )
    _create_ai_settings(db, test_org.id, test_user.id, anonymize_pii=True)

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content=(
                    '{"subject": "Hello [PERSON_1]", '
                    '"body": "Hi [PERSON_1], we will email you at [EMAIL_1]."}'
                ),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/draft-email",
        json={
            "surrogate_id": str(surrogate.id),
            "email_type": "follow_up",
            "additional_context": "Please follow up with Jane Doe at jane.doe@example.com",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert surrogate.full_name in payload["body"]
    assert "[PERSON_1]" not in payload["body"]

    combined = "\n".join(msg.content for msg in captured)
    assert surrogate.full_name not in combined
    assert surrogate.email not in combined


@pytest.mark.asyncio
async def test_parse_schedule_anonymizes_prompt_and_rehydrates(
    authed_client: AsyncClient, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        name="Jane Doe",
        email="jane.doe@example.com",
    )
    _create_ai_settings(db, test_org.id, test_user.id, anonymize_pii=True)

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content=(
                    '[{"title":"Call [PERSON_1]","description":"Email [EMAIL_1]",'
                    '"due_date":"2025-01-01","due_time":null,"task_type":"contact","confidence":0.9}]'
                ),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gpt-4o-mini",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post(
        "/ai/parse-schedule",
        json={
            "text": "Call Jane Doe at jane.doe@example.com tomorrow",
            "surrogate_id": str(surrogate.id),
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["proposed_tasks"]
    assert surrogate.full_name in payload["proposed_tasks"][0]["title"]

    combined = "\n".join(msg.content for msg in captured)
    assert surrogate.full_name not in combined
    assert surrogate.email not in combined


@pytest.mark.asyncio
async def test_task_chat_anonymizes_context_and_message(
    db, test_org, test_user, default_stage, monkeypatch
):
    from app.db.models import Task
    from app.db.enums import TaskType, OwnerType
    from app.services import ai_chat_service

    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        name="Jane Doe",
        email="jane.doe@example.com",
    )
    _create_ai_settings(db, test_org.id, test_user.id, anonymize_pii=True)

    task = Task(
        organization_id=test_org.id,
        surrogate_id=surrogate.id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title="Follow up",
        description="Email Jane Doe at jane.doe@example.com about the next steps.",
        task_type=TaskType.OTHER.value,
        is_completed=False,
    )
    db.add(task)
    db.flush()

    captured = []

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            captured.extend(messages)
            return ChatResponse(
                content="Ok",
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
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
        entity_type="task",
        entity_id=task.id,
        message="Ping Jane Doe at jane.doe@example.com",
        user_integrations=[],
    )

    assert result["content"] == "Ok"
    combined = "\n".join(msg.content for msg in captured)
    assert surrogate.full_name not in combined
    assert surrogate.email not in combined
