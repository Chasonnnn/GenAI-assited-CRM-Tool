"""AI Provider abstraction layer.

Supports Google Gemini and Vertex AI with a unified interface.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import uuid

import requests
from google import genai
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.genai import types

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
        # Pricing per 1M tokens (approximate, as of Jan 2026)
        pricing = {
            "gemini-3-flash-preview": {"input": Decimal("0.075"), "output": Decimal("0.30")},
            "gemini-3-pro-preview": {"input": Decimal("1.25"), "output": Decimal("5.00")},
        }

        model_pricing = pricing.get(self.model, {"input": Decimal("0"), "output": Decimal("0")})
        input_cost = (Decimal(self.prompt_tokens) / Decimal("1000000")) * model_pricing["input"]
        output_cost = (Decimal(self.completion_tokens) / Decimal("1000000")) * model_pricing[
            "output"
        ]
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


def _build_google_contents(
    messages: list[ChatMessage],
) -> tuple[list[types.Content], str | None]:
    system_instruction = None
    contents: list[types.Content] = []
    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
        else:
            role = "model" if msg.role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(msg.content)],
                )
            )
    return contents, system_instruction


def _build_google_config(
    temperature: float,
    max_tokens: int,
    system_instruction: str | None,
) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        system_instruction=system_instruction,
    )


def _extract_genai_text(response: object) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    try:
        parts = response.candidates[0].content.parts  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Provider response missing text") from exc
    text_parts = []
    for part in parts:
        part_text = getattr(part, "text", None)
        if part_text:
            text_parts.append(part_text)
    combined = "".join(text_parts).strip()
    if not combined:
        raise ValueError("Provider response missing text")
    return combined


def _extract_usage_counts(response: object) -> tuple[int, int, int]:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return 0, 0, 0
    prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    completion_tokens = int(
        getattr(usage, "candidates_token_count", 0)
        or getattr(usage, "response_token_count", 0)
        or 0
    )
    total_tokens = int(
        getattr(usage, "total_token_count", prompt_tokens + completion_tokens)
        or (prompt_tokens + completion_tokens)
    )
    return prompt_tokens, completion_tokens, total_tokens


class GoogleGenAIProvider(AIProvider):
    """Base provider for Google Gen AI SDK backends."""

    def __init__(self, client: genai.Client, default_model: str) -> None:
        self._client = client
        self.default_model = default_model

    async def _generate_content(
        self,
        *,
        model: str,
        contents: list[types.Content],
        temperature: float,
        max_tokens: int,
        system_instruction: str | None,
    ) -> object:
        config = _build_google_config(temperature, max_tokens, system_instruction)
        return await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        model = model or self.default_model
        contents, system_instruction = _build_google_contents(messages)
        response = await self._generate_content(
            model=model,
            contents=contents,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instruction=system_instruction,
        )
        content = _extract_genai_text(response)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage_counts(response)
        return ChatResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model,
        )

    async def generate_text_with_parts(
        self,
        *,
        parts: list[types.Part],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system_instruction: str | None = None,
    ) -> str:
        model = model or self.default_model
        contents = [types.Content(role="user", parts=parts)]
        response = await self._generate_content(
            model=model,
            contents=contents,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instruction=system_instruction,
        )
        return _extract_genai_text(response)


class GeminiProvider(GoogleGenAIProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, default_model: str = "gemini-3-flash-preview") -> None:
        self.api_key = api_key
        client = genai.Client(api_key=api_key)
        super().__init__(client, default_model)

    async def validate_key(self) -> bool:
        """Test the API key with a minimal request."""
        try:
            await self._client.aio.models.generate_content(
                model=self.default_model,
                contents=[types.Content(role="user", parts=[types.Part.from_text("ping")])],
                config=types.GenerateContentConfig(temperature=0, max_output_tokens=1),
            )
            return True
        except Exception as e:
            logger.warning(f"Gemini key validation failed: {e}")
            return False


@dataclass
class VertexWIFConfig:
    project_id: str
    location: str
    audience: str
    service_account_email: str
    organization_id: uuid.UUID
    user_id: uuid.UUID | None = None


class VertexWIFCredentials(Credentials):
    """Google Auth credentials using Workload Identity Federation tokens."""

    STS_TOKEN_URL = "https://sts.googleapis.com/v1/token"
    IAM_CREDENTIALS_URL = (
        "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
        "{service_account}:generateAccessToken"
    )

    def __init__(self, config: VertexWIFConfig) -> None:
        super().__init__()
        self._config = config
        self.token = None
        self.expiry: datetime | None = None

    @staticmethod
    def _normalize_audience(audience: str) -> str:
        if audience.startswith("//"):
            return audience
        return f"//iam.googleapis.com/{audience}"

    def refresh(self, request: Request) -> None:  # noqa: ARG002
        now = datetime.now(timezone.utc)
        if self.token and self.expiry and self.expiry > now + timedelta(minutes=2):
            return

        from app.services import wif_oidc_service

        audience = self._normalize_audience(self._config.audience)
        subject = f"org:{self._config.organization_id}"
        claims = {
            "org_id": str(self._config.organization_id),
        }
        if self._config.user_id:
            claims["user_id"] = str(self._config.user_id)

        subject_token = wif_oidc_service.create_subject_token(
            audience=audience,
            subject=subject,
            claims=claims,
        )

        sts_response = requests.post(
            self.STS_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "audience": audience,
                "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "scope": "https://www.googleapis.com/auth/cloud-platform",
                "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "subject_token": subject_token,
            },
            timeout=20,
        )
        sts_response.raise_for_status()
        sts_payload = sts_response.json()
        sts_token = sts_payload["access_token"]

        iam_response = requests.post(
            self.IAM_CREDENTIALS_URL.format(service_account=self._config.service_account_email),
            headers={"Authorization": f"Bearer {sts_token}"},
            json={
                "scope": ["https://www.googleapis.com/auth/cloud-platform"],
                "lifetime": "3600s",
            },
            timeout=20,
        )
        iam_response.raise_for_status()
        iam_payload = iam_response.json()

        access_token = iam_payload["accessToken"]
        expires_at = iam_payload.get("expireTime")
        if expires_at:
            self.expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            self.expiry = now + timedelta(hours=1)
        self.token = access_token


class VertexWIFProvider(GoogleGenAIProvider):
    """Vertex AI provider using Workload Identity Federation (OIDC)."""

    def __init__(
        self, config: VertexWIFConfig, default_model: str = "gemini-3-flash-preview"
    ) -> None:
        self.config = config
        self._credentials = VertexWIFCredentials(config)
        client = genai.Client(
            vertexai=True,
            project=config.project_id,
            location=config.location,
            credentials=self._credentials,
            http_options=types.HttpOptions(api_version="v1"),
        )
        super().__init__(client, default_model)

    async def _generate_content(
        self,
        *,
        model: str,
        contents: list[types.Content],
        temperature: float,
        max_tokens: int,
        system_instruction: str | None,
    ) -> object:
        if not self._credentials.token or not self._credentials.expiry or self._credentials.expired:
            await asyncio.to_thread(self._credentials.refresh, Request())
        return await super()._generate_content(
            model=model,
            contents=contents,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instruction=system_instruction,
        )

    async def validate_key(self) -> bool:
        """Validate WIF configuration by attempting a token exchange."""
        try:
            self._credentials.refresh(Request())
            return True
        except Exception as e:
            logger.warning(f"Vertex WIF validation failed: {e}")
            return False


@dataclass
class VertexAPIKeyConfig:
    api_key: str
    project_id: str | None = None
    location: str | None = None


class VertexAPIKeyProvider(GoogleGenAIProvider):
    """Vertex AI provider using API keys (supports express mode)."""

    def __init__(
        self,
        config: VertexAPIKeyConfig,
        default_model: str = "gemini-3-flash-preview",
    ) -> None:
        self.config = config
        self._is_express = not (config.project_id and config.location)
        client_kwargs: dict[str, object] = {
            "vertexai": True,
            "api_key": config.api_key,
            "http_options": types.HttpOptions(api_version="v1"),
        }
        if config.project_id:
            client_kwargs["project"] = config.project_id
        if config.location:
            client_kwargs["location"] = config.location
        client = genai.Client(**client_kwargs)
        super().__init__(client, default_model)

    async def validate_key(self) -> bool:
        """Validate API key with a lightweight request."""
        try:
            await self._client.aio.models.generate_content(
                model=self.default_model,
                contents=[types.Content(role="user", parts=[types.Part.from_text("ping")])],
                config=types.GenerateContentConfig(temperature=0, max_output_tokens=1),
            )
            return True
        except Exception as e:
            logger.warning(f"Vertex API key validation failed: {e}")
            return False


def get_provider(
    provider_name: str, api_key: str, model: str | None = None, **kwargs
) -> AIProvider:
    """Factory function to get the appropriate AI provider."""
    if provider_name == "gemini":
        return GeminiProvider(api_key, default_model=model or "gemini-3-flash-preview")
    elif provider_name == "vertex_api_key":
        config = VertexAPIKeyConfig(
            api_key=api_key,
            project_id=kwargs.get("project_id"),
            location=kwargs.get("location"),
        )
        return VertexAPIKeyProvider(config, default_model=model or "gemini-3-flash-preview")
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
