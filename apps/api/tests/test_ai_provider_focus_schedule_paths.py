from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routers.ai_schedule import ParseScheduleRequest
from app.services import ai_provider
from app.services.ai_provider import (
    ChatMessage,
    ChatResponse,
    VertexWIFConfig,
    VertexWIFCredentials,
)


def test_ai_provider_helpers_extract_and_usage():
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="hello"),
        ChatMessage(role="assistant", content="world"),
    ]
    contents, system = ai_provider._build_google_contents(messages)
    assert system == "sys"
    assert len(contents) == 2

    config = ai_provider._build_google_config(0.2, 256, "sys")
    assert config.temperature == 0.2
    assert config.max_output_tokens == 256

    assert ai_provider._extract_genai_text(SimpleNamespace(text="  hi  ")) == "  hi  "

    fallback_response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text="a"), SimpleNamespace(text="b")]
                )
            )
        ]
    )
    assert ai_provider._extract_genai_text(fallback_response) == "ab"
    assert ai_provider._extract_genai_text_optional(SimpleNamespace(text=None)) == ""

    usage_response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=3,
            total_token_count=13,
        )
    )
    assert ai_provider._extract_usage_counts(usage_response) == (10, 3, 13)

    quote = ChatResponse(
        content="ok",
        prompt_tokens=1_000_000,
        completion_tokens=500_000,
        total_tokens=1_500_000,
        model="gemini-3-flash-preview",
    )
    assert quote.estimated_cost_usd > 0


class _FakeAioModels:
    def __init__(self):
        self.calls: list[str] = []

    async def generate_content(self, **kwargs):
        self.calls.append("generate_content")
        return SimpleNamespace(
            text="response-text",
            usage_metadata=SimpleNamespace(
                prompt_token_count=7,
                candidates_token_count=5,
                total_token_count=12,
            ),
        )

    async def generate_content_stream(self, **kwargs):
        self.calls.append("generate_content_stream")

        async def _iterator():
            yield SimpleNamespace(text="H")
            yield SimpleNamespace(
                text="Hi",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=11,
                    candidates_token_count=4,
                    total_token_count=15,
                ),
            )

        return _iterator()


class _TestGoogleProvider(ai_provider.GoogleGenAIProvider):
    async def validate_key(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_google_genai_provider_chat_and_stream():
    fake_models = _FakeAioModels()
    fake_client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))
    provider = _TestGoogleProvider(fake_client, default_model="gemini-3-flash-preview")

    response = await provider.chat([ChatMessage(role="user", content="hello")], temperature=0.1)
    assert response.content == "response-text"
    assert response.total_tokens == 12

    chunks = [chunk async for chunk in provider.stream_chat([ChatMessage(role="user", content="hello")])]
    assert [chunk.text for chunk in chunks[:-1]] == ["H", "i"]
    assert chunks[-1].is_final is True
    assert chunks[-1].total_tokens == 15


def test_vertex_wif_credentials_refresh(monkeypatch):
    cfg = VertexWIFConfig(
        project_id="proj",
        location="us-central1",
        audience="projects/123/providers/provider",
        service_account_email="svc@example.iam.gserviceaccount.com",
        organization_id=uuid4(),
        user_id=uuid4(),
    )
    creds = VertexWIFCredentials(cfg)

    monkeypatch.setattr(
        "app.services.wif_oidc_service.create_subject_token",
        lambda **kwargs: "jwt-subject-token",
    )

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data=None, headers=None, json=None):
            if url == VertexWIFCredentials.STS_URL:
                return _Resp({"access_token": "sts-token"})
            return _Resp({"accessToken": "iam-token", "expireTime": "2026-01-01T01:00:00Z"})

    monkeypatch.setattr(ai_provider.httpx, "Client", lambda timeout=20.0: _Client())

    creds.refresh(SimpleNamespace())
    assert creds.token == "iam-token"
    assert creds.expiry is not None
    assert creds._normalize_audience("projects/1/providers/x").startswith("//iam.googleapis.com/")
    assert creds._normalize_audience("//iam.googleapis.com/projects/1/providers/x").startswith("//")


@pytest.mark.asyncio
async def test_vertex_provider_and_factory(monkeypatch):
    fake_models = _FakeAioModels()
    fake_client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))

    monkeypatch.setattr(ai_provider, "genai", SimpleNamespace(Client=lambda **kwargs: fake_client))
    monkeypatch.setattr(ai_provider.types, "HttpOptions", lambda api_version="v1": {"api_version": api_version})
    monkeypatch.setattr(ai_provider.asyncio, "to_thread", lambda fn, *args: fn(*args))

    cfg = VertexWIFConfig(
        project_id="proj",
        location="us-central1",
        audience="//iam.googleapis.com/projects/1/providers/x",
        service_account_email="svc@example.com",
        organization_id=uuid4(),
    )
    provider = ai_provider.VertexWIFProvider(cfg)
    provider._credentials.token = "tok"
    provider._credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    monkeypatch.setattr(
        VertexWIFCredentials,
        "expired",
        property(lambda self: False),
    )

    result = await provider._generate_content(
        model="gemini-3-flash-preview",
        contents=[],
        temperature=0,
        max_tokens=32,
        system_instruction=None,
    )
    assert getattr(result, "text", "") == "response-text"

    gemini = ai_provider.get_provider("gemini", "api-key")
    assert isinstance(gemini, ai_provider.GeminiProvider)
    vertex = ai_provider.get_provider("vertex_api_key", "api-key", project_id="proj", location="us-central1")
    assert isinstance(vertex, ai_provider.VertexAPIKeyProvider)
    with pytest.raises(ValueError, match="Unknown provider"):
        ai_provider.get_provider("unknown", "api-key")


def test_parse_schedule_request_validators():
    surrogate_id = uuid4()
    req = ParseScheduleRequest(
        text="Call tomorrow",
        case_id=str(surrogate_id),
    )
    assert req.surrogate_id == surrogate_id

    with pytest.raises(Exception):
        ParseScheduleRequest(text="Call tomorrow")


@pytest.mark.asyncio
async def test_vertex_validate_key_failure(monkeypatch):
    cfg = VertexWIFConfig(
        project_id="proj",
        location="us-central1",
        audience="//iam.googleapis.com/projects/1/providers/x",
        service_account_email="svc@example.com",
        organization_id=uuid4(),
    )
    provider = ai_provider.VertexWIFProvider(cfg)
    monkeypatch.setattr(provider._credentials, "refresh", lambda _req: (_ for _ in ()).throw(RuntimeError("bad")))
    ok = await provider.validate_key()
    assert ok is False
