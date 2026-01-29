"""AI Provider abstraction layer.

Supports OpenAI, Google Gemini, and Vertex AI with a unified interface.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import uuid

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
        # Pricing per 1M tokens (approximate)
        pricing = {
            # OpenAI
            "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
            "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
            # Gemini
            "gemini-3-flash-preview": {
                "input": Decimal("0.10"),
                "output": Decimal("0.40"),
            },  # Gemini 3.0 Flash
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


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, default_model: str = "gpt-4o-mini") -> None:
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
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
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

    def __init__(self, api_key: str, default_model: str = "gemini-3-flash-preview") -> None:
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

        request_body: dict[str, object] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

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


@dataclass
class VertexWIFConfig:
    project_id: str
    location: str
    audience: str
    service_account_email: str
    organization_id: uuid.UUID
    user_id: uuid.UUID | None = None


class VertexWIFProvider(AIProvider):
    """Vertex AI provider using Workload Identity Federation (OIDC)."""

    STS_TOKEN_URL = "https://sts.googleapis.com/v1/token"
    IAM_CREDENTIALS_URL = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{service_account}:generateAccessToken"

    def __init__(
        self, config: VertexWIFConfig, default_model: str = "gemini-3-flash-preview"
    ) -> None:
        self.config = config
        self.default_model = default_model
        self.base_url = f"https://{config.location}-aiplatform.googleapis.com/v1"
        self._cached_token: str | None = None
        self._cached_token_expiry: datetime | None = None

    def _normalize_audience(self, audience: str) -> str:
        if audience.startswith("//"):
            return audience
        return f"//iam.googleapis.com/{audience}"

    async def _get_access_token(self) -> str:
        if self._cached_token and self._cached_token_expiry:
            if self._cached_token_expiry > datetime.now(timezone.utc) + timedelta(minutes=2):
                return self._cached_token

        from app.services import wif_oidc_service

        audience = self._normalize_audience(self.config.audience)
        subject = f"org:{self.config.organization_id}"
        claims = {
            "org_id": str(self.config.organization_id),
        }
        if self.config.user_id:
            claims["user_id"] = str(self.config.user_id)

        subject_token = wif_oidc_service.create_subject_token(
            audience=audience,
            subject=subject,
            claims=claims,
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            sts_response = await client.post(
                self.STS_TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "audience": audience,
                    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "scope": "https://www.googleapis.com/auth/cloud-platform",
                    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                    "subject_token": subject_token,
                },
            )
            sts_response.raise_for_status()
            sts_payload = sts_response.json()

        sts_token = sts_payload["access_token"]

        async with httpx.AsyncClient(timeout=20.0) as client:
            iam_response = await client.post(
                self.IAM_CREDENTIALS_URL.format(service_account=self.config.service_account_email),
                headers={"Authorization": f"Bearer {sts_token}"},
                json={
                    "scope": ["https://www.googleapis.com/auth/cloud-platform"],
                    "lifetime": "3600s",
                },
            )
            iam_response.raise_for_status()
            iam_payload = iam_response.json()

        access_token = iam_payload["accessToken"]
        expires_at = iam_payload.get("expireTime")
        if expires_at:
            self._cached_token_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            self._cached_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        self._cached_token = access_token
        return access_token

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        model = model or self.default_model

        system_instruction = None
        contents = []
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "model" if msg.role == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        body: dict[str, object] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        access_token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/projects/{self.config.project_id}/locations/{self.config.location}/publishers/google/models/{model}:generateContent",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": self.config.project_id,
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]
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
        """Validate WIF configuration by attempting a token exchange."""
        try:
            await self._get_access_token()
            return True
        except Exception as e:
            logger.warning(f"Vertex WIF validation failed: {e}")
            return False


@dataclass
class VertexAPIKeyConfig:
    api_key: str
    project_id: str | None = None
    location: str | None = None


class VertexAPIKeyProvider(AIProvider):
    """Vertex AI provider using API keys (supports express mode)."""

    def __init__(
        self,
        config: VertexAPIKeyConfig,
        default_model: str = "gemini-3-flash-preview",
    ) -> None:
        self.config = config
        self.default_model = default_model
        self._is_express = not (config.project_id and config.location)

    def _base_url(self) -> str:
        if self._is_express:
            return "https://aiplatform.googleapis.com/v1"
        return f"https://{self.config.location}-aiplatform.googleapis.com/v1/projects/{self.config.project_id}/locations/{self.config.location}"

    def _endpoint(self, model: str) -> str:
        return f"{self._base_url()}/publishers/google/models/{model}:generateContent"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.project_id:
            headers["x-goog-user-project"] = self.config.project_id
        return headers

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> ChatResponse:
        model = model or self.default_model

        system_instruction = None
        contents = []
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "model" if msg.role == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        body: dict[str, object] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._endpoint(model),
                params={"key": self.config.api_key},
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]
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
        """Validate API key with a lightweight request."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    self._endpoint(self.default_model),
                    params={"key": self.config.api_key},
                    headers=self._headers(),
                    json={
                        "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
                        "generationConfig": {"maxOutputTokens": 1, "temperature": 0},
                    },
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Vertex API key validation failed: {e}")
            return False


def get_provider(
    provider_name: str, api_key: str, model: str | None = None, **kwargs
) -> AIProvider:
    """Factory function to get the appropriate AI provider."""
    if provider_name == "openai":
        return OpenAIProvider(api_key, default_model=model or "gpt-4o-mini")
    elif provider_name == "gemini":
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
