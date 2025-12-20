"""
Admin endpoints for Meta Lead Ads page management.

Replaces CLI commands with web UI for managing Meta page tokens.
"""
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.encryption import encrypt_token, is_encryption_configured

from app.db.models import MetaPageMapping
from app.schemas.auth import UserSession


router = APIRouter(prefix="/admin/meta-pages", tags=["admin"])


# =============================================================================
# Schemas
# =============================================================================

class MetaPageCreate(BaseModel):
    page_id: str = Field(..., description="Meta page ID")
    page_name: str | None = Field(None, description="Optional page name for display")
    access_token: str = Field(..., description="Page access token (will be encrypted)")
    expires_days: int = Field(60, ge=1, le=365, description="Token expiry in days")


class MetaPageUpdate(BaseModel):
    page_name: str | None = None
    access_token: str | None = Field(None, description="New access token (will be encrypted)")
    expires_days: int | None = Field(None, ge=1, le=365)
    is_active: bool | None = None


class MetaPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    page_id: str
    page_name: str | None
    token_expires_at: datetime | None
    is_active: bool
    last_success_at: datetime | None = None  # From model's last_success_at
    last_error: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MetaPageTestResponse(BaseModel):
    success: bool
    message: str
    page_info: dict | None = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=list[MetaPageRead])
def list_meta_pages(
    session: UserSession = Depends(require_permission("manage_meta_leads")),
    db: Session = Depends(get_db),
):
    """List all Meta page mappings for the organization."""
    pages = db.query(MetaPageMapping).filter(
        MetaPageMapping.organization_id == session.org_id
    ).order_by(MetaPageMapping.created_at.desc()).all()
    
    return pages


@router.post("", response_model=MetaPageRead, status_code=status.HTTP_201_CREATED)
def create_meta_page(
    data: MetaPageCreate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(require_permission("manage_meta_leads")),
    db: Session = Depends(get_db),
):
    """
    Create or update Meta page mapping with encrypted token.
    
    Replaces: python -m app.cli update-meta-page-token
    """
    # Check encryption configured
    if not is_encryption_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="META_ENCRYPTION_KEY not configured. Contact administrator."
        )
    
    # Check for existing mapping
    existing = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == data.page_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Page {data.page_id} already exists. Use PUT to update."
        )
    
    # Encrypt token
    encrypted = encrypt_token(data.access_token)
    expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
    
    # Create mapping
    mapping = MetaPageMapping(
        organization_id=session.org_id,
        page_id=data.page_id,
        page_name=data.page_name,
        access_token_encrypted=encrypted,
        token_expires_at=expires_at,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    
    return mapping


@router.put("/{page_id}", response_model=MetaPageRead)
def update_meta_page(
    page_id: str,
    data: MetaPageUpdate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(require_permission("manage_meta_leads")),
    db: Session = Depends(get_db),
):
    """Update existing Meta page mapping."""
    mapping = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == page_id,
        MetaPageMapping.organization_id == session.org_id,
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    
    # Update fields
    if data.page_name is not None:
        mapping.page_name = data.page_name
    
    if data.access_token is not None:
        if not is_encryption_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="META_ENCRYPTION_KEY not configured"
            )
        encrypted = encrypt_token(data.access_token)
        mapping.access_token_encrypted = encrypted
        
    if data.expires_days is not None:
        mapping.token_expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
        
    if data.is_active is not None:
        mapping.is_active = data.is_active
        if data.is_active:
            # Clear error when reactivating
            mapping.last_error = None
    
    db.commit()
    db.refresh(mapping)
    
    return mapping


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meta_page(
    page_id: str,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(require_permission("manage_meta_leads")),
    db: Session = Depends(get_db),
):
    """
    Delete Meta page mapping.
    
    Replaces: python -m app.cli deactivate-meta-page
    """
    mapping = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == page_id,
        MetaPageMapping.organization_id == session.org_id,
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    
    db.delete(mapping)
    db.commit()

