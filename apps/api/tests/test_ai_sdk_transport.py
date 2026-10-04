"""Exercise the installed Google SDK through an in-memory HTTP transport."""

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from google import genai
from google.genai import types
from openai import AsyncOpenAI

from app.db.models import AIStudioSettings
from app.services import ai_provider, ai_studio_service


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["gemini", "vertex_express", "vertex_scoped", "vertex_wif"])
async def test_sdk_chat_stream_and_audio_parts_preserve_provider_contract(monkeypatch, mode):
    requests = []
    response = {
        "candidates": [{"content": {"role": "model", "parts": [{"text": "Hello"}]}}],
        "usageMetadata": {
            "promptTokenCount": 7,
            "candidatesTokenCount": 3,
            "totalTokenCount": 10,
        },
    }

    def handler(request):
        requests.append(request)
        if "streamGenerateContent" in request.url.path:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=f"data: {json.dumps(response)}\n\n".encode(),
            )
        return httpx.Response(200, json=response)

    real_client = genai.Client
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:

        def make_client(**kwargs):
            options = kwargs.pop("http_options", types.HttpOptions())
            options.httpx_async_client = http_client
            return real_client(**kwargs, http_options=options)

        monkeypatch.setattr(ai_provider.genai, "Client", make_client)
        if mode == "gemini":
            provider = ai_provider.GeminiProvider("synthetic-key")
        elif mode == "vertex_wif":
            provider = ai_provider.VertexWIFProvider(
                ai_provider.VertexWIFConfig(
                    "synthetic-project", "us", "audience", "account", uuid4()
                )
            )
            provider._credentials.token = "synthetic-access-token"
            provider._credentials.expiry = (datetime.now(UTC) + timedelta(hours=1)).replace(
                tzinfo=None
            )
        else:
            provider = ai_provider.VertexAPIKeyProvider(
                ai_provider.VertexAPIKeyConfig(
                    "synthetic-key",
                    "synthetic-project" if mode == "vertex_scoped" else None,
                    "us" if mode == "vertex_scoped" else None,
                )
            )
        try:
            messages = [
                ai_provider.ChatMessage("system", "Be concise"),
                ai_provider.ChatMessage("user", "Hi"),
            ]
            chat = await provider.chat(messages)
            assert (chat.content, chat.prompt_tokens, chat.completion_tokens) == ("Hello", 7, 3)
            chunks = [chunk async for chunk in provider.stream_chat(messages)]
            assert chunks[0].text == "Hello"
            assert chunks[-1].is_final and chunks[-1].total_tokens == 10
            text = await provider.generate_text_with_parts(
                parts=[types.Part.from_bytes(data=b"synthetic-audio", mime_type="audio/wav")]
            )
            assert text == "Hello"
            assert len(requests) == 3
            assert all("gemini-3.8-flash" in request.url.path for request in requests)
            body = json.loads(requests[0].content)
            assert body["systemInstruction"]["parts"][0]["text"] == "Be concise"
            part = types.Part.model_validate(
                json.loads(requests[2].content)["contents"][0]["parts"][0]
            )
            assert part.inline_data.mime_type == "audio/wav"
            assert part.inline_data.data == b"synthetic-audio"
            if mode == "vertex_wif":
                assert requests[0].headers["authorization"] == "Bearer synthetic-access-token"
            else:
                assert requests[0].headers["x-goog-api-key"] == "synthetic-key"
            assert ("aiplatform" in requests[0].url.host) == (mode != "gemini")
        finally:
            await provider._client.aio.aclose()
            provider._client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    ["generate", "edit", "responses_error", "images_error", "responses_cancel", "images_cancel"],
)
async def test_studio_sdk_releases_transport_after_generation(monkeypatch, outcome):
    """The real SDK releases connections on completion, failure, and task cancellation."""
    blocked = asyncio.Event()
    draft = {
        "audience": "Synthetic audience",
        "caption": "Synthetic caption",
        "hashtags": ["synthetic"],
        "image_prompt": "Synthetic image prompt",
    }

    async def handler(request):
        phase = "responses" if request.url.path.endswith("/responses") else "images"
        if outcome == f"{phase}_cancel":
            blocked.set()
            await asyncio.Event().wait()
        if outcome == f"{phase}_error":
            return httpx.Response(400, json={"error": {"message": "synthetic-private-provider"}})
        if phase == "responses":
            return httpx.Response(
                200,
                json={
                    "id": "resp_synthetic",
                    "object": "response",
                    "created_at": 0,
                    "status": "completed",
                    "model": "gpt-5.5",
                    "output": [
                        {
                            "id": "msg_synthetic",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(draft),
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "created": 0,
                "data": [{"b64_json": base64.b64encode(b"synthetic-image").decode()}],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk_clients = []

    def make_client(**kwargs):
        client = AsyncOpenAI(**kwargs, http_client=http_client)
        sdk_clients.append(client)
        return client

    monkeypatch.setattr(ai_studio_service, "AsyncOpenAI", make_client)
    request = ai_studio_service.AIStudioGenerateRequest(
        brief="Synthetic post brief",
        platform="linkedin",
        format="feed",
        tone="professional",
        reference_images=(
            [
                ai_studio_service.AIStudioReferenceImage(
                    filename="synthetic.png",
                    mime_type="image/png",
                    data_base64=base64.b64encode(b"synthetic-reference").decode(),
                )
            ]
            if outcome == "edit"
            else []
        ),
    )
    generation = ai_studio_service._generate_with_openai(
        api_key="synthetic-key",
        studio_settings=AIStudioSettings(
            agents_md="Synthetic instructions", skills_md="Synthetic skills"
        ),
        request=request,
    )
    try:
        if outcome.endswith("_cancel"):
            task = asyncio.create_task(generation)
            try:
                await asyncio.wait_for(blocked.wait(), timeout=5)
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        elif outcome.endswith("_error"):
            with pytest.raises(ai_studio_service.AIStudioGenerationError) as exc:
                await generation
            assert str(exc.value) == "OpenAI generation failed"
        else:
            asset = await generation
            assert (asset.audience, asset.caption, asset.hashtags, asset.image_bytes) == (
                "Synthetic audience",
                "Synthetic caption",
                ["#synthetic"],
                b"synthetic-image",
            )
        assert http_client.is_closed
        assert sdk_clients[0].is_closed()
    finally:
        await http_client.aclose()
