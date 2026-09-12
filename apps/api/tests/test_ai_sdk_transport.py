"""Exercise the installed Google SDK through an in-memory HTTP transport."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from google import genai
from google.genai import types

from app.services import ai_provider


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
