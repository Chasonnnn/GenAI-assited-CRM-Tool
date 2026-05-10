"""AI Studio service for social draft generation."""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AIStudioDraft, AIStudioSettings, Organization
from app.services import ai_settings_service, attachment_service, storage_client, storage_url_service


AI_STUDIO_REASONING_MODEL = "gpt-5.5"
AI_STUDIO_IMAGE_MODEL = "gpt-image-2"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_IMAGE_MIME_TYPE = "image/png"

Platform = Literal["instagram", "facebook", "linkedin", "x", "tiktok"]
PostFormat = Literal["feed", "story", "reel", "carousel", "ad"]
Tone = Literal["warm", "professional", "bold", "calm", "educational"]
ImageSize = Literal["auto", "1024x1024", "1024x1536", "1536x1024", "2560x1440", "3840x2160"]
ImageQuality = Literal["auto", "high", "medium", "low"]

DEFAULT_AGENTS_MD = """# AI Studio Agent
Generate human-reviewed social media drafts for Surrogacy Force. Keep claims careful, avoid medical guarantees, and write for a professional fertility and surrogacy audience.
"""

DEFAULT_SKILLS_MD = """# AI Studio Skills
- Turn a short campaign brief into polished social copy.
- Create concise hashtags that match the selected platform.
- Write a production-ready visual prompt for one generated image.
"""


class AIStudioConfigurationError(RuntimeError):
    """Raised when AI Studio is not configured for generation."""


class AIStudioDraftNotFoundError(RuntimeError):
    """Raised when a draft does not exist within the organization."""


class AIStudioGenerationError(RuntimeError):
    """Raised when OpenAI generation does not return usable content."""


class AIStudioGenerateRequest(BaseModel):
    brief: str = Field(min_length=8, max_length=2000)
    platform: Platform
    format: PostFormat
    tone: Tone
    audience: str = Field(default="", max_length=200)
    image_size: ImageSize = "auto"
    image_quality: ImageQuality = "auto"


class AIStudioStructuredDraft(BaseModel):
    caption: str = Field(min_length=1, max_length=2200)
    hashtags: list[str] = Field(default_factory=list, max_length=12)
    image_prompt: str = Field(min_length=10, max_length=1400)


class AIStudioGeneratedAsset(BaseModel):
    caption: str
    hashtags: list[str]
    image_prompt: str
    image_bytes: bytes
    image_mime_type: str = DEFAULT_IMAGE_MIME_TYPE
    revised_prompt: str | None = None
    metadata: dict = Field(default_factory=dict)


def get_or_create_settings(db: Session, organization_id: uuid.UUID) -> AIStudioSettings:
    studio_settings = (
        db.query(AIStudioSettings)
        .filter(AIStudioSettings.organization_id == organization_id)
        .first()
    )
    if studio_settings:
        return studio_settings

    studio_settings = AIStudioSettings(
        organization_id=organization_id,
        agents_md=DEFAULT_AGENTS_MD,
        skills_md=DEFAULT_SKILLS_MD,
    )
    db.add(studio_settings)
    db.commit()
    db.refresh(studio_settings)
    return studio_settings


def update_settings(
    db: Session,
    organization_id: uuid.UUID,
    *,
    api_key: str | None = None,
    agents_md: str | None = None,
    skills_md: str | None = None,
) -> AIStudioSettings:
    studio_settings = get_or_create_settings(db, organization_id)
    if api_key is not None:
        stripped = api_key.strip()
        studio_settings.openai_api_key_encrypted = (
            ai_settings_service.encrypt_api_key(stripped) if stripped else None
        )
    if agents_md is not None:
        studio_settings.agents_md = agents_md
    if skills_md is not None:
        studio_settings.skills_md = skills_md
    studio_settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(studio_settings)
    return studio_settings


def has_api_key(studio_settings: AIStudioSettings) -> bool:
    return bool(studio_settings.openai_api_key_encrypted)


def mask_api_key(studio_settings: AIStudioSettings) -> str | None:
    return ai_settings_service.mask_api_key(studio_settings.openai_api_key_encrypted)


def _get_decrypted_api_key(studio_settings: AIStudioSettings) -> str:
    if not studio_settings.openai_api_key_encrypted:
        raise AIStudioConfigurationError("OpenAI API key is not configured for AI Studio")
    try:
        return ai_settings_service.decrypt_api_key(studio_settings.openai_api_key_encrypted)
    except Exception as exc:  # noqa: BLE001
        raise AIStudioConfigurationError("OpenAI API key could not be decrypted") from exc


def _assert_org_ai_enabled(db: Session, organization_id: uuid.UUID) -> None:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org or not org.ai_enabled:
        raise AIStudioConfigurationError("AI is not enabled for this organization")


def _build_system_prompt(studio_settings: AIStudioSettings) -> str:
    return "\n\n".join(
        [
            "You generate social media draft content for a CRM AI Studio.",
            "Return only content that can be reviewed by a human before posting.",
            "Never claim guaranteed medical, legal, or financial outcomes.",
            "Use the provided AGENTS.md and SKILLS.md only for this AI Studio task.",
            "<AGENTS.md>",
            studio_settings.agents_md or DEFAULT_AGENTS_MD,
            "</AGENTS.md>",
            "<SKILLS.md>",
            studio_settings.skills_md or DEFAULT_SKILLS_MD,
            "</SKILLS.md>",
        ]
    )


def _build_user_prompt(request: AIStudioGenerateRequest) -> str:
    audience = request.audience.strip() or "general CRM audience"
    return (
        "Create one social media draft as JSON for these inputs:\n"
        f"- Platform: {request.platform}\n"
        f"- Format: {request.format}\n"
        f"- Tone: {request.tone}\n"
        f"- Audience: {audience}\n"
        f"- Brief: {request.brief.strip()}\n\n"
        "The JSON must include caption, hashtags, and image_prompt. "
        "The image_prompt must describe a polished social media visual with no text overlay."
    )


def _strip_json_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def _extract_output_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    chunks: list[str] = []
    for output in getattr(response, "output", []) or []:
        for item in getattr(output, "content", []) or []:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _extract_parsed_draft(response: object) -> AIStudioStructuredDraft:
    output_parsed = getattr(response, "output_parsed", None)
    if output_parsed:
        return AIStudioStructuredDraft.model_validate(output_parsed)

    for output in getattr(response, "output", []) or []:
        for item in getattr(output, "content", []) or []:
            parsed = getattr(item, "parsed", None)
            if parsed:
                return AIStudioStructuredDraft.model_validate(parsed)
            if getattr(item, "type", None) == "refusal":
                raise AIStudioGenerationError("OpenAI refused to generate this draft")

    output_text = _strip_json_fence(_extract_output_text(response)).strip()
    if output_text:
        return AIStudioStructuredDraft.model_validate(json.loads(output_text))
    raise AIStudioGenerationError("OpenAI did not return draft content")


def _image_size_for_request(request: AIStudioGenerateRequest) -> str:
    return request.image_size


def _normalize_hashtags(hashtags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in hashtags:
        clean = tag.strip()
        if not clean:
            continue
        if not clean.startswith("#"):
            clean = f"#{clean}"
        if clean not in normalized:
            normalized.append(clean[:80])
    return normalized[:12]


async def _generate_with_openai(
    *,
    api_key: str,
    studio_settings: AIStudioSettings,
    request: AIStudioGenerateRequest,
) -> AIStudioGeneratedAsset:
    client = AsyncOpenAI(api_key=api_key, timeout=90.0)
    try:
        text_response = await client.responses.parse(
            model=AI_STUDIO_REASONING_MODEL,
            input=[
                {"role": "system", "content": _build_system_prompt(studio_settings)},
                {"role": "user", "content": _build_user_prompt(request)},
            ],
            text_format=AIStudioStructuredDraft,
            reasoning={"effort": DEFAULT_REASONING_EFFORT},
        )
        structured = _extract_parsed_draft(text_response)

        image_response = await client.images.generate(
            model=AI_STUDIO_IMAGE_MODEL,
            prompt=structured.image_prompt,
            size=_image_size_for_request(request),
            quality=request.image_quality,
            output_format="png",
        )
    except AIStudioGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIStudioGenerationError("OpenAI generation failed") from exc

    image_items = getattr(image_response, "data", None) or []
    if not image_items:
        raise AIStudioGenerationError("OpenAI did not return an image")
    first_image = image_items[0]
    image_base64 = getattr(first_image, "b64_json", None)
    if not image_base64:
        raise AIStudioGenerationError("OpenAI did not return image bytes")

    metadata = {
        "reasoning_response_id": getattr(text_response, "id", None),
        "reasoning_usage": _usage_to_dict(getattr(text_response, "usage", None)),
        "image_size": _image_size_for_request(request),
        "image_quality": request.image_quality,
    }
    return AIStudioGeneratedAsset(
        caption=structured.caption.strip(),
        hashtags=_normalize_hashtags(structured.hashtags),
        image_prompt=structured.image_prompt.strip(),
        image_bytes=base64.b64decode(image_base64),
        image_mime_type=DEFAULT_IMAGE_MIME_TYPE,
        revised_prompt=getattr(first_image, "revised_prompt", None),
        metadata=metadata,
    )


def _usage_to_dict(usage: object | None) -> dict:
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _store_image_asset(
    *,
    organization_id: uuid.UUID,
    image_bytes: bytes,
    content_type: str,
) -> str:
    storage_key = f"ai-studio/{organization_id}/{uuid.uuid4()}.png"
    if getattr(settings, "STORAGE_BACKEND", "local") == "s3":
        bucket = settings.S3_BUCKET or "crm-attachments"
        s3 = storage_client.get_s3_client()
        s3.put_object(Bucket=bucket, Key=storage_key, Body=image_bytes, ContentType=content_type)
    else:
        attachment_service.store_file(storage_key, BytesIO(image_bytes), content_type)
    return storage_key


def build_image_url(storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    if getattr(settings, "STORAGE_BACKEND", "local") == "s3":
        bucket = settings.S3_BUCKET or "crm-attachments"
        return storage_url_service.build_public_url(bucket, storage_key)
    base = (settings.API_BASE_URL or "").rstrip("/")
    path = f"/ai/studio/assets/{storage_key}"
    return f"{base}{path}" if base else path


async def generate_preview(
    *,
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    request: AIStudioGenerateRequest,
) -> AIStudioDraft:
    _assert_org_ai_enabled(db, organization_id)
    studio_settings = get_or_create_settings(db, organization_id)
    api_key = _get_decrypted_api_key(studio_settings)
    generated = await _generate_with_openai(
        api_key=api_key,
        studio_settings=studio_settings,
        request=request,
    )
    storage_key = _store_image_asset(
        organization_id=organization_id,
        image_bytes=generated.image_bytes,
        content_type=generated.image_mime_type,
    )
    draft = AIStudioDraft(
        organization_id=organization_id,
        created_by_user_id=user_id,
        status="preview",
        platform=request.platform,
        format=request.format,
        tone=request.tone,
        audience=request.audience.strip(),
        brief=request.brief.strip(),
        caption=generated.caption,
        hashtags=generated.hashtags,
        image_prompt=generated.image_prompt,
        image_storage_key=storage_key,
        image_mime_type=generated.image_mime_type,
        image_size_bytes=len(generated.image_bytes),
        image_revised_prompt=generated.revised_prompt,
        image_size=request.image_size,
        image_quality=request.image_quality,
        reasoning_model=AI_STUDIO_REASONING_MODEL,
        image_model=AI_STUDIO_IMAGE_MODEL,
        generation_metadata=generated.metadata,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def save_draft(db: Session, organization_id: uuid.UUID, draft_id: uuid.UUID) -> AIStudioDraft:
    draft = (
        db.query(AIStudioDraft)
        .filter(AIStudioDraft.organization_id == organization_id, AIStudioDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise AIStudioDraftNotFoundError("AI Studio draft not found")
    draft.status = "saved"
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)
    return draft


def list_saved_drafts(
    db: Session,
    organization_id: uuid.UUID,
    *,
    limit: int = 20,
) -> list[AIStudioDraft]:
    bounded_limit = max(1, min(limit, 50))
    return (
        db.query(AIStudioDraft)
        .filter(AIStudioDraft.organization_id == organization_id, AIStudioDraft.status == "saved")
        .order_by(desc(AIStudioDraft.created_at))
        .limit(bounded_limit)
        .all()
    )


def get_draft_by_storage_key(
    db: Session,
    organization_id: uuid.UUID,
    storage_key: str,
) -> AIStudioDraft | None:
    return (
        db.query(AIStudioDraft)
        .filter(
            AIStudioDraft.organization_id == organization_id,
            AIStudioDraft.image_storage_key == storage_key,
        )
        .first()
    )


def resolve_local_asset_path(storage_key: str) -> str:
    if "\\" in storage_key:
        raise ValueError("Invalid image path")
    normalized = os.path.normpath(storage_key)
    if normalized.startswith("..") or normalized.startswith("/") or not normalized.startswith(
        "ai-studio/"
    ):
        raise ValueError("Invalid image path")
    return attachment_service.resolve_local_storage_path(normalized)
