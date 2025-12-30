"""Admin versions router - unified version control API for developers.

Provides a single endpoint to view version history for any versioned entity:
- pipelines
- email_templates
- ai_settings

Developer-only access.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import version_service

router = APIRouter(prefix="/admin/versions", tags=["Admin - Versions"])


# =============================================================================
# Schemas
# =============================================================================

ALLOWED_ENTITY_TYPES = {"pipeline", "email_template", "ai_settings"}


class VersionRead(BaseModel):
    """Version history entry."""

    id: UUID
    entity_type: str
    entity_id: UUID
    version: int
    schema_version: int
    checksum: str
    created_by_user_id: UUID | None
    comment: str | None
    created_at: str


class VersionDetailRead(VersionRead):
    """Version with decrypted payload (for viewing)."""

    payload: dict[str, Any]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{entity_type}/{entity_id}", response_model=list[VersionRead])
def get_entity_versions(
    entity_type: str,
    entity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.ADMIN_VERSIONS_MANAGE)),
):
    """
    Get version history for any versioned entity.

    Supported entity_types: pipeline, email_template, ai_settings
    Developer-only access.
    """
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type. Allowed: {', '.join(ALLOWED_ENTITY_TYPES)}",
        )

    versions = version_service.get_version_history(
        db=db,
        org_id=session.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )

    if not versions:
        raise HTTPException(status_code=404, detail="No versions found")

    return [
        VersionRead(
            id=v.id,
            entity_type=v.entity_type,
            entity_id=v.entity_id,
            version=v.version,
            schema_version=v.schema_version,
            checksum=v.checksum,
            created_by_user_id=v.created_by_user_id,
            comment=v.comment,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.get("/{entity_type}/{entity_id}/{version}", response_model=VersionDetailRead)
def get_version_detail(
    entity_type: str,
    entity_id: UUID,
    version: int,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.ADMIN_VERSIONS_MANAGE)),
):
    """
    Get a specific version with decrypted payload.

    Developer-only access.
    """
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type. Allowed: {', '.join(ALLOWED_ENTITY_TYPES)}",
        )

    version_record = version_service.get_version(
        db=db,
        org_id=session.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        version=version,
    )

    if not version_record:
        raise HTTPException(status_code=404, detail="Version not found")

    # Decrypt and verify payload
    try:
        payload = version_service.decrypt_payload(version_record.payload_encrypted)
        if not version_service.verify_checksum(
            version_record.payload_encrypted, version_record.checksum
        ):
            raise HTTPException(status_code=500, detail="Checksum verification failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt payload: {e}")

    return VersionDetailRead(
        id=version_record.id,
        entity_type=version_record.entity_type,
        entity_id=version_record.entity_id,
        version=version_record.version,
        schema_version=version_record.schema_version,
        checksum=version_record.checksum,
        created_by_user_id=version_record.created_by_user_id,
        comment=version_record.comment,
        created_at=version_record.created_at.isoformat(),
        payload=payload,
    )
