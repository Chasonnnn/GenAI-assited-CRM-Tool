"""AI Provider abstraction layer.

Supports OpenAI and Google Gemini with a unified interface.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: str  # 'system', 'user', 'assistant'
    content: str


@dataclass
class ChatResponse:
    """Response from an AI provider."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str

    @property
    def estimated_cost_usd(self) -> Decimal:
        """Estimate cost based on model pricing (approximate)."""
        # Pricing per 1M tokens (as of Dec 2024)
        pricing = {
            # OpenAI
            "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
            "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
            # Gemini
            "gemini-3-flash-preview": {
                "input": Decimal("0.10"),
                "output": Decimal("0.40"),
            },  # Gemini 3.0 Flash
            "gemini-2.0-flash-exp": {
                "input": Decimal("0.075"),
                "output": Decimal("0.30"),
            },
            "gemini-1.5-flash": {"input": Decimal("0.075"), "output": Decimal("0.30")},
            "gemini-1.5-pro": {"input": Decimal("1.25"), "output": Decimal("5.00")},
        }

        model_pricing = pricing.get(
            self.model, {"input": Decimal("0"), "output": Decimal("0")}
        )
        input_cost = (Decimal(self.prompt_tokens) / Decimal("1000000")) * model_pricing[
            "input"
        ]
        output_cost = (
            Decimal(self.completion_tokens) / Decimal("1000000")
        ) * model_pricing["output"]
        return input_cost + output_cost


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def validate_key(self) -> bool:
        """Validate that the API key is working."""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, default_model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://api.openai.com/v1"

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        model = model or self.default_model

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": m.role, "content": m.content} for m in messages
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

        usage = data.get("usage", {})
        return ChatResponse(
            content=data["choices"][0]["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model=model,
        )

    async def validate_key(self) -> bool:
        """Test the API key with a minimal request."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI key validation failed: {e}")
            return False


class GeminiProvider(AIProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, default_model: str = "gemini-3-flash-preview"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        model = model or self.default_model

        # Convert messages to Gemini format
        # Gemini uses 'user' and 'model' roles, system goes in systemInstruction
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "model" if msg.role == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        request_body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/models/{model}:generateContent",
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        # Extract response content
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        # Gemini returns usage metadata
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        return ChatResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
        )

    async def validate_key(self) -> bool:
        """Test the API key with a minimal request."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    params={"key": self.api_key},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini key validation failed: {e}")
            return False


def get_provider(
    provider_name: str, api_key: str, model: str | None = None
) -> AIProvider:
    """Factory function to get the appropriate AI provider."""
    if provider_name == "openai":
        return OpenAIProvider(api_key, default_model=model or "gpt-4o-mini")
    elif provider_name == "gemini":
        return GeminiProvider(api_key, default_model=model or "gemini-3-flash-preview")
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
