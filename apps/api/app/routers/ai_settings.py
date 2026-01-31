"""AI settings routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession

router = APIRouter()


class VertexWIFConfig(BaseModel):
    project_id: str | None = None
    location: str | None = None
    audience: str | None = None
    service_account_email: str | None = None


class VertexAPIKeyConfig(BaseModel):
    project_id: str | None = None
    location: str | None = None


class AISettingsResponse(BaseModel):
    """AI settings for display (with masked key)."""

    is_enabled: bool
    provider: str
    model: str | None
    api_key_masked: str | None
    vertex_wif: VertexWIFConfig | None = None
    vertex_api_key: VertexAPIKeyConfig | None = None
    context_notes_limit: int
    conversation_history_limit: int
    # Privacy fields
    anonymize_pii: bool
    consent_accepted_at: str | None
    consent_required: bool
    # Version control
    current_version: int | None = None


class AISettingsUpdate(BaseModel):
    """Update AI settings."""

    is_enabled: bool | None = None
    provider: str | None = Field(None, pattern="^(gemini|vertex_wif|vertex_api_key)$")
    api_key: str | None = None
    model: str | None = None
    vertex_wif: VertexWIFConfig | None = None
    vertex_api_key: VertexAPIKeyConfig | None = None
    context_notes_limit: int | None = Field(None, ge=1, le=20)
    conversation_history_limit: int | None = Field(None, ge=5, le=50)
    anonymize_pii: bool | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")


class TestKeyRequest(BaseModel):
    """Test an API key."""

    provider: str = Field(..., pattern="^(gemini|vertex_api_key)$")
    api_key: str
    vertex_api_key: VertexAPIKeyConfig | None = None


class TestKeyResponse(BaseModel):
    """API key test result."""

    valid: bool


@router.get("/settings", response_model=AISettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> AISettingsResponse:
    """Get AI settings for the organization."""
    from app.services import ai_settings_service

    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id, session.user_id)

    effective_model = ai_settings_service.get_effective_model(settings)

    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=effective_model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        vertex_wif=VertexWIFConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
            audience=settings.vertex_audience,
            service_account_email=settings.vertex_service_account_email,
        )
        if settings.provider == "vertex_wif"
        else None,
        vertex_api_key=VertexAPIKeyConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
        )
        if settings.provider == "vertex_api_key"
        else None,
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_required=ai_settings_service.is_consent_required(settings),
        current_version=settings.current_version,
    )


@router.patch(
    "/settings",
    response_model=AISettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_settings(
    update: AISettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> AISettingsResponse:
    """Update AI settings for the organization. Creates version snapshot."""
    from app.services import ai_settings_service, version_service

    try:
        settings = ai_settings_service.update_ai_settings(
            db,
            session.org_id,
            session.user_id,
            is_enabled=update.is_enabled,
            provider=update.provider,
            api_key=update.api_key,
            model=update.model,
            vertex_project_id=update.vertex_wif.project_id
            if update.vertex_wif
            else update.vertex_api_key.project_id
            if update.vertex_api_key
            else None,
            vertex_location=update.vertex_wif.location
            if update.vertex_wif
            else update.vertex_api_key.location
            if update.vertex_api_key
            else None,
            vertex_audience=update.vertex_wif.audience if update.vertex_wif else None,
            vertex_service_account_email=update.vertex_wif.service_account_email
            if update.vertex_wif
            else None,
            context_notes_limit=update.context_notes_limit,
            conversation_history_limit=update.conversation_history_limit,
            anonymize_pii=update.anonymize_pii,
            expected_version=update.expected_version,
        )
    except version_service.VersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {e.expected}, got {e.actual}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    changed_fields = [
        field
        for field, value in {
            "is_enabled": update.is_enabled,
            "provider": update.provider,
            "api_key": update.api_key,
            "model": update.model,
            "vertex_wif": update.vertex_wif,
            "vertex_api_key": update.vertex_api_key,
            "context_notes_limit": update.context_notes_limit,
            "conversation_history_limit": update.conversation_history_limit,
            "anonymize_pii": update.anonymize_pii,
        }.items()
        if value is not None
    ]
    if changed_fields:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="ai",
            changes={"fields": changed_fields},
            request=request,
        )
        if update.api_key is not None:
            audit_service.log_api_key_rotated(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                provider=update.provider or settings.provider,
                request=request,
            )
        db.commit()

    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=settings.model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        vertex_wif=VertexWIFConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
            audience=settings.vertex_audience,
            service_account_email=settings.vertex_service_account_email,
        )
        if settings.provider == "vertex_wif"
        else None,
        vertex_api_key=VertexAPIKeyConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
        )
        if settings.provider == "vertex_api_key"
        else None,
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_required=ai_settings_service.is_consent_required(settings),
        current_version=settings.current_version,
    )


@router.post(
    "/settings/test",
    response_model=TestKeyResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def test_api_key(
    request: TestKeyRequest,
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> TestKeyResponse:
    """Test if an API key is valid."""
    from app.services import ai_settings_service

    valid = await ai_settings_service.test_api_key(
        request.provider,
        request.api_key,
        project_id=request.vertex_api_key.project_id if request.vertex_api_key else None,
        location=request.vertex_api_key.location if request.vertex_api_key else None,
    )
    return TestKeyResponse(valid=valid)
