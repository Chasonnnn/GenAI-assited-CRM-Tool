"""AI Studio routes for social draft generation."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.schemas.auth import UserSession
from app.services import ai_studio_service

router = APIRouter(prefix="/studio", tags=["AI Studio"])
AI_STUDIO_GENERATION_LIMIT = f"{settings.RATE_LIMIT_AI_GENERATION}/minute"


class AIStudioSettingsResponse(BaseModel):
    """AI Studio settings safe for frontend display."""

    has_api_key: bool
    api_key_masked: str | None
    agents_md: str
    skills_md: str
    reasoning_model: str
    image_model: str


class AIStudioSettingsUpdate(BaseModel):
    """AI Studio settings update. API keys are write-only."""

    api_key: str | None = Field(default=None, max_length=4096)
    agents_md: str | None = Field(default=None, max_length=12000)
    skills_md: str | None = Field(default=None, max_length=12000)


class AIStudioDraftResponse(BaseModel):
    """Persisted AI Studio draft."""

    id: UUID
    status: str
    platform: str
    format: str
    tone: str
    audience: str
    brief: str
    caption: str
    hashtags: list[str]
    image_prompt: str
    image_url: str | None
    image_revised_prompt: str | None
    image_size: str
    image_quality: str
    reasoning_model: str
    image_model: str
    created_at: datetime
    updated_at: datetime


class AIStudioDraftListResponse(BaseModel):
    """Saved AI Studio drafts."""

    items: list[AIStudioDraftResponse]


def _settings_response(studio_settings) -> AIStudioSettingsResponse:  # noqa: ANN001
    return AIStudioSettingsResponse(
        has_api_key=ai_studio_service.has_api_key(studio_settings),
        api_key_masked=ai_studio_service.mask_api_key(studio_settings),
        agents_md=studio_settings.agents_md or ai_studio_service.DEFAULT_AGENTS_MD,
        skills_md=studio_settings.skills_md or ai_studio_service.DEFAULT_SKILLS_MD,
        reasoning_model=ai_studio_service.AI_STUDIO_REASONING_MODEL,
        image_model=ai_studio_service.AI_STUDIO_IMAGE_MODEL,
    )


def _draft_response(draft) -> AIStudioDraftResponse:  # noqa: ANN001
    return AIStudioDraftResponse(
        id=draft.id,
        status=draft.status,
        platform=draft.platform,
        format=draft.format,
        tone=draft.tone,
        audience=draft.audience,
        brief=draft.brief,
        caption=draft.caption,
        hashtags=draft.hashtags or [],
        image_prompt=draft.image_prompt,
        image_url=ai_studio_service.build_image_url(draft.image_storage_key),
        image_revised_prompt=draft.image_revised_prompt,
        image_size=draft.image_size,
        image_quality=draft.image_quality,
        reasoning_model=draft.reasoning_model,
        image_model=draft.image_model,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.get("/settings", response_model=AIStudioSettingsResponse)
def get_studio_settings(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
) -> AIStudioSettingsResponse:
    """Return org-scoped AI Studio settings without exposing secrets."""

    studio_settings = ai_studio_service.get_or_create_settings(db, session.org_id)
    return _settings_response(studio_settings)


@router.patch(
    "/settings",
    response_model=AIStudioSettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_studio_settings(
    update: AIStudioSettingsUpdate,
    request: Request,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.AI_SETTINGS_MANAGE)
    ),
) -> AIStudioSettingsResponse:
    """Update org-scoped AI Studio BYOK and isolated prompt guidance."""

    studio_settings = ai_studio_service.update_settings(
        db,
        session.org_id,
        api_key=update.api_key,
        agents_md=update.agents_md,
        skills_md=update.skills_md,
    )
    changed_fields = [
        key
        for key, value in {
            "api_key": update.api_key,
            "agents_md": update.agents_md,
            "skills_md": update.skills_md,
        }.items()
        if value is not None
    ]
    if changed_fields:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="ai_studio",
            changes={"fields": changed_fields},
            request=request,
        )
        if update.api_key is not None:
            audit_service.log_api_key_rotated(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                provider="openai",
                request=request,
            )
        db.commit()
    return _settings_response(studio_settings)


@router.post(
    "/generate",
    response_model=AIStudioDraftResponse,
    dependencies=[Depends(require_csrf_header)],
)
@limiter.limit(AI_STUDIO_GENERATION_LIMIT)
async def generate_studio_draft(
    request: Request,
    body: ai_studio_service.AIStudioGenerateRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
) -> AIStudioDraftResponse:
    """Generate a preview draft. Generated content is never posted automatically."""

    try:
        draft = await ai_studio_service.generate_preview(
            db=db,
            organization_id=session.org_id,
            user_id=session.user_id,
            request=body,
        )
    except ai_studio_service.AIStudioConfigurationError as exc:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if str(exc) == "AI is not enabled for this organization"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except ai_studio_service.AIStudioGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return _draft_response(draft)


@router.post(
    "/drafts/{draft_id}/save",
    response_model=AIStudioDraftResponse,
    dependencies=[Depends(require_csrf_header)],
)
def save_studio_draft(
    draft_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
) -> AIStudioDraftResponse:
    """Mark a generated preview as a saved draft."""

    try:
        draft = ai_studio_service.save_draft(db, session.org_id, draft_id)
    except ai_studio_service.AIStudioDraftNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _draft_response(draft)


@router.get("/drafts", response_model=AIStudioDraftListResponse)
def list_studio_drafts(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
    limit: int = 20,
) -> AIStudioDraftListResponse:
    """List saved org-scoped AI Studio drafts."""

    drafts = ai_studio_service.list_saved_drafts(db, session.org_id, limit=limit)
    return AIStudioDraftListResponse(items=[_draft_response(draft) for draft in drafts])


@router.get("/assets/{storage_key:path}")
def get_studio_asset(
    storage_key: str,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
) -> FileResponse:
    """Serve locally stored AI Studio image assets with org scoping."""

    draft = ai_studio_service.get_draft_by_storage_key(db, session.org_id, storage_key)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Studio asset not found")
    try:
        asset_path = ai_studio_service.resolve_local_asset_path(storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Studio asset not found") from exc
    if not os.path.exists(asset_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Studio asset not found")
    return FileResponse(asset_path, media_type=draft.image_mime_type or "image/png")
