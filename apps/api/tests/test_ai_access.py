"""Access control tests for AI endpoints."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import AISettings, Membership, Surrogate, User, UserPermissionOverride
from app.main import app
from app.services import ai_settings_service, session_service
from app.utils.normalization import normalize_email


@asynccontextmanager
async def _authed_client_for_user(db, org_id, user, role):
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


def _create_ai_settings(db, org_id, user_id, *, consent_accepted=True) -> AISettings:
    settings = AISettings(
        organization_id=org_id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        consent_accepted_at=datetime.now(timezone.utc) if consent_accepted else None,
        consent_accepted_by=user_id if consent_accepted else None,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()
    return settings


@pytest.mark.asyncio
async def test_ai_summarize_and_draft_require_surrogate_access(
    db, test_org, test_user, default_stage
):
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

    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=intake_user.id,
            permission="use_ai_assistant",
            override_type="grant",
        )
    )

    normalized_email = normalize_email("access@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Access Test",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    _create_ai_settings(db, test_org.id, test_user.id, consent_accepted=True)

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(
            "/ai/summarize-surrogate",
            json={"surrogate_id": str(surrogate.id)},
        )
        assert response.status_code == 403

        response = await client.post(
            "/ai/draft-email",
            json={"surrogate_id": str(surrogate.id), "email_type": "follow_up"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_analyze_dashboard_requires_consent(
    authed_client: AsyncClient, db, test_org, test_user
):
    _create_ai_settings(db, test_org.id, test_user.id, consent_accepted=False)

    response = await authed_client.post("/ai/analyze-dashboard")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_org_ai_enabled_blocks_usage(authed_client: AsyncClient, db, test_org, test_user):
    test_org.ai_enabled = False
    db.add(test_org)
    db.flush()

    _create_ai_settings(db, test_org.id, test_user.id, consent_accepted=True)

    response = await authed_client.post("/ai/chat", json={"message": "Hello"})
    assert response.status_code == 403

    response = await authed_client.post("/ai/analyze-dashboard")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_map_requires_ai_permission(db, test_org, monkeypatch):
    """AI import mapping should require use_ai_assistant permission."""
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

    # Avoid external AI calls; the permission check should block first.
    from app.services import import_ai_mapper_service

    async def fake_ai_suggest_mappings(db, org_id, unmatched_columns):  # noqa: ANN001
        return unmatched_columns

    monkeypatch.setattr(import_ai_mapper_service, "is_ai_available", lambda *_: True)
    monkeypatch.setattr(import_ai_mapper_service, "ai_suggest_mappings", fake_ai_suggest_mappings)

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(
            "/surrogates/import/ai-map",
            json={
                "unmatched_columns": ["Custom Column"],
                "sample_values": {"Custom Column": ["value"]},
            },
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_focus_supports_vertex_wif_without_api_key(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
    default_stage,
    monkeypatch,
):
    """Vertex WIF should work for AI focus endpoints without api_key_encrypted."""
    from app.db.models import AISettings
    from app.services import ai_settings_service
    from app.services.ai_provider import ChatResponse

    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="vertex_wif",
        model="gemini-3-flash-preview",
        vertex_project_id="demo-project",
        vertex_location="us-central1",
        vertex_audience="projects/123/locations/global/workloadIdentityPools/pool/providers/provider",
        vertex_service_account_email="vertex-sa@demo-project.iam.gserviceaccount.com",
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=test_user.id,
    )
    db.add(settings)
    db.flush()

    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="WIF Test",
        email=normalize_email("wif@test.com"),
        email_hash=hash_email(normalize_email("wif@test.com")),
    )
    db.add(surrogate)
    db.flush()

    class FakeProvider:
        async def chat(self, *_, **__):
            return ChatResponse(
                content="ok",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        ai_settings_service,
        "get_ai_provider_for_settings",
        lambda *_args, **_kwargs: FakeProvider(),
    )

    response = await authed_client.post(
        "/ai/summarize-surrogate",
        json={"surrogate_id": str(surrogate.id)},
    )
    assert response.status_code == 200

    response = await authed_client.post(
        "/ai/draft-email",
        json={"surrogate_id": str(surrogate.id), "email_type": "follow_up"},
    )
    assert response.status_code == 200

    response = await authed_client.post("/ai/analyze-dashboard")
    assert response.status_code == 200
