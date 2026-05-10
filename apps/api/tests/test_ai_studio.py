"""AI Studio draft generation tests."""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    AISettings,
    AIStudioDraft,
    AIStudioSettings,
    Membership,
    Organization,
    User,
)
from app.main import app
from app.services import ai_settings_service, ai_studio_service, session_service


@asynccontextmanager
async def _client_for_user(db, org_id: uuid.UUID, user: User, role: Role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client

    app.dependency_overrides.clear()


def _create_second_org_user(db) -> tuple[Organization, User]:
    org = Organization(
        id=uuid.uuid4(),
        name="Second Organization",
        slug=f"second-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    user = User(
        id=uuid.uuid4(),
        email=f"second-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Second User",
        token_version=1,
        is_active=True,
    )
    db.add_all([org, user])
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org.id,
            role=Role.DEVELOPER,
        )
    )
    db.flush()
    return org, user


@pytest.mark.asyncio
async def test_ai_studio_settings_store_openai_key_masked_and_org_scoped(
    authed_client: AsyncClient,
    db,
    test_org,
):
    response = await authed_client.get("/ai/studio/settings")
    assert response.status_code == 200
    assert response.json()["has_api_key"] is False
    assert response.json()["reasoning_model"] == "gpt-5.5"
    assert response.json()["image_model"] == "gpt-image-2"

    response = await authed_client.patch(
        "/ai/studio/settings",
        json={
            "api_key": "sk-studio-test-key-1234",
            "agents_md": "Studio agent rules",
            "skills_md": "Studio skill rules",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_api_key"] is True
    assert payload["api_key_masked"] == "sk-s...1234"
    assert payload["agents_md"] == "Studio agent rules"
    assert payload["skills_md"] == "Studio skill rules"

    stored = db.query(AIStudioSettings).filter_by(organization_id=test_org.id).one()
    assert stored.openai_api_key_encrypted != "sk-studio-test-key-1234"

    second_org, second_user = _create_second_org_user(db)
    async with _client_for_user(db, second_org.id, second_user, Role.DEVELOPER) as second_client:
        second_response = await second_client.get("/ai/studio/settings")
        assert second_response.status_code == 200
        assert second_response.json()["has_api_key"] is False


@pytest.mark.asyncio
async def test_ai_studio_generate_requires_configured_openai_key(authed_client: AsyncClient):
    response = await authed_client.post(
        "/ai/studio/generate",
        json={
            "brief": "Create a hopeful Instagram post about matching intended parents.",
            "platform": "instagram",
            "format": "feed",
            "tone": "warm",
            "audience": "intended parents",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "OpenAI API key is not configured for AI Studio"


@pytest.mark.asyncio
async def test_ai_studio_generation_uses_isolated_agents_and_skills(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    db.add(
        AISettings(
            organization_id=test_org.id,
            is_enabled=True,
            provider="gemini",
            model="gemini-3-flash-preview",
            api_key_encrypted=ai_settings_service.encrypt_api_key("sk-assistant"),
            consent_accepted_at=datetime.now(timezone.utc),
            consent_accepted_by=test_user.id,
        )
    )
    studio_settings = AIStudioSettings(
        organization_id=test_org.id,
        openai_api_key_encrypted=ai_settings_service.encrypt_api_key("sk-studio"),
        agents_md="Studio-only AGENTS.md",
        skills_md="Studio-only SKILLS.md",
    )
    db.add(studio_settings)
    db.flush()

    captured: dict[str, object] = {}

    async def fake_generate_with_openai(*, api_key, studio_settings, request):  # noqa: ANN001
        captured["api_key"] = api_key
        captured["agents_md"] = studio_settings.agents_md
        captured["skills_md"] = studio_settings.skills_md
        captured["brief"] = request.brief
        captured["audience"] = request.audience
        captured["reference_images"] = [
            {"filename": image.filename, "mime_type": image.mime_type}
            for image in request.reference_images
        ]
        return ai_studio_service.AIStudioGeneratedAsset(
            audience="clinic partners",
            caption="Caption",
            hashtags=["#SurrogacyForce"],
            image_prompt="Image prompt",
            image_bytes=b"fake-image",
            image_mime_type="image/png",
            revised_prompt="Revised image prompt",
            metadata={"stub": True},
        )

    monkeypatch.setattr(ai_studio_service, "_generate_with_openai", fake_generate_with_openai)

    draft = await ai_studio_service.generate_preview(
        db=db,
        organization_id=test_org.id,
        user_id=test_user.id,
        request=ai_studio_service.AIStudioGenerateRequest(
            brief="Draft a post",
            platform="linkedin",
            format="feed",
            tone="professional",
            audience="",
            reference_images=[
                ai_studio_service.AIStudioReferenceImage(
                    filename="clinic-sample.png",
                    mime_type="image/png",
                    data_base64=base64.b64encode(b"reference-image").decode("ascii"),
                )
            ],
        ),
    )

    assert captured == {
        "api_key": "sk-studio",
        "agents_md": "Studio-only AGENTS.md",
        "skills_md": "Studio-only SKILLS.md",
        "brief": "Draft a post",
        "audience": "",
        "reference_images": [
            {"filename": "clinic-sample.png", "mime_type": "image/png"},
        ],
    }
    assert draft.audience == "clinic partners"
    assert draft.reasoning_model == "gpt-5.5"
    assert draft.image_model == "gpt-image-2"
    assert draft.image_size == "auto"
    assert draft.image_quality == "auto"
    assert draft.generation_metadata["reference_image_count"] == 1
    assert draft.generation_metadata["reference_images"] == [
        {"filename": "clinic-sample.png", "mime_type": "image/png", "size_bytes": 15}
    ]
    assert "data_base64" not in str(draft.generation_metadata)
    assert draft.status == "preview"


@pytest.mark.asyncio
async def test_ai_studio_drafts_are_saved_and_org_scoped(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    draft = AIStudioDraft(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        status="preview",
        platform="instagram",
        format="feed",
        tone="warm",
        audience="surrogates",
        brief="Post brief",
        caption="Generated caption",
        hashtags=["#SurrogacyForce"],
        image_prompt="Image prompt",
        image_storage_key="ai-studio/test/image.png",
        image_mime_type="image/png",
        image_size_bytes=10,
        image_size="1536x1024",
        image_quality="high",
        reasoning_model="gpt-5.5",
        image_model="gpt-image-2",
        generation_metadata={
            "reference_images": [
                {
                    "filename": "brand-reference.webp",
                    "mime_type": "image/webp",
                    "size_bytes": 42,
                }
            ],
            "reference_image_count": 1,
        },
    )
    db.add(draft)
    db.flush()

    response = await authed_client.post(f"/ai/studio/drafts/{draft.id}/save")
    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert response.json()["image_size"] == "1536x1024"
    assert response.json()["image_quality"] == "high"
    assert response.json()["reference_images"] == [
        {"filename": "brand-reference.webp", "mime_type": "image/webp", "size_bytes": 42}
    ]

    response = await authed_client.get("/ai/studio/drafts")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(draft.id)]

    second_org, second_user = _create_second_org_user(db)
    async with _client_for_user(db, second_org.id, second_user, Role.DEVELOPER) as second_client:
        second_response = await second_client.post(f"/ai/studio/drafts/{draft.id}/save")
        assert second_response.status_code == 404
        list_response = await second_client.get("/ai/studio/drafts")
        assert list_response.status_code == 200
        assert list_response.json()["items"] == []
