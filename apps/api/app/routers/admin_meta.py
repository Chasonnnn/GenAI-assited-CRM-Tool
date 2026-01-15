"""
Admin endpoints for Meta Lead Ads management.

Includes:
- Page token management
- Ad account configuration (with encrypted tokens)
- Sync triggers (hierarchy, spend, forms)
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.core.encryption import encrypt_token, is_encryption_configured

from app.db.models import MetaAdAccount
from app.schemas.auth import UserSession
from app.services import meta_page_service, meta_sync_service


router = APIRouter(
    prefix="/admin/meta-pages",
    tags=["admin"],
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)

ad_account_router = APIRouter(
    prefix="/admin/meta-ad-accounts",
    tags=["admin"],
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)


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
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all Meta page mappings for the organization."""
    return meta_page_service.list_meta_pages(db, session.org_id)


@router.post("", response_model=MetaPageRead, status_code=status.HTTP_201_CREATED)
def create_meta_page(
    data: MetaPageCreate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
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
            detail="META_ENCRYPTION_KEY not configured. Contact administrator.",
        )

    # Check for existing mapping
    existing = meta_page_service.get_mapping_by_page_id_any_org(db, data.page_id)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Page {data.page_id} already exists. Use PUT to update.",
        )

    # Encrypt token
    encrypted = encrypt_token(data.access_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)

    # Create mapping
    return meta_page_service.create_mapping(
        db=db,
        org_id=session.org_id,
        page_id=data.page_id,
        page_name=data.page_name,
        access_token_encrypted=encrypted,
        token_expires_at=expires_at,
    )


@router.put("/{page_id}", response_model=MetaPageRead)
def update_meta_page(
    page_id: str,
    data: MetaPageUpdate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update existing Meta page mapping."""
    mapping = meta_page_service.get_mapping_by_page_id(db, session.org_id, page_id)

    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    # Update fields
    if data.access_token is not None:
        if not is_encryption_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="META_ENCRYPTION_KEY not configured",
            )
        encrypted = encrypt_token(data.access_token)
    else:
        encrypted = None

    if data.expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)
    else:
        expires_at = None

    return meta_page_service.update_mapping(
        db=db,
        mapping=mapping,
        page_name=data.page_name,
        access_token_encrypted=encrypted,
        token_expires_at=expires_at,
        is_active=data.is_active,
    )


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meta_page(
    page_id: str,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Delete Meta page mapping.

    Replaces: python -m app.cli deactivate-meta-page
    """
    mapping = meta_page_service.get_mapping_by_page_id(db, session.org_id, page_id)

    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    meta_page_service.delete_mapping(db, mapping)


# =============================================================================
# Ad Account Schemas
# =============================================================================


class MetaAdAccountCreate(BaseModel):
    ad_account_external_id: str = Field(..., description="Meta Ad Account ID (act_XXXXX)")
    ad_account_name: str | None = Field(None, description="Display name")
    system_token: str = Field(..., description="System user access token (will be encrypted)")
    expires_days: int = Field(60, ge=1, le=365, description="Token expiry in days")
    pixel_id: str | None = Field(None, description="Pixel ID for CAPI")
    capi_enabled: bool = Field(False, description="Enable CAPI for this account")
    capi_token: str | None = Field(None, description="CAPI token if different from system token")


class MetaAdAccountUpdate(BaseModel):
    ad_account_name: str | None = None
    system_token: str | None = Field(None, description="New system token")
    expires_days: int | None = Field(None, ge=1, le=365)
    pixel_id: str | None = None
    capi_enabled: bool | None = None
    capi_token: str | None = None
    is_active: bool | None = None


class MetaAdAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    ad_account_external_id: str
    ad_account_name: str | None
    token_expires_at: datetime | None
    pixel_id: str | None
    capi_enabled: bool
    hierarchy_synced_at: datetime | None
    spend_synced_at: datetime | None
    is_active: bool
    last_error: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SyncTriggerResponse(BaseModel):
    success: bool
    message: str
    details: dict | None = None


class SyncStatusResponse(BaseModel):
    ad_account_id: UUID
    ad_account_name: str | None
    hierarchy_synced_at: datetime | None
    spend_synced_at: datetime | None
    last_error: str | None


# =============================================================================
# Ad Account Endpoints
# =============================================================================


@ad_account_router.get("", response_model=list[MetaAdAccountRead])
def list_meta_ad_accounts(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all Meta ad accounts for the organization."""
    accounts = db.scalars(
        select(MetaAdAccount)
        .where(MetaAdAccount.organization_id == session.org_id)
        .order_by(MetaAdAccount.created_at.desc())
    ).all()
    return list(accounts)


@ad_account_router.post("", response_model=MetaAdAccountRead, status_code=status.HTTP_201_CREATED)
def create_meta_ad_account(
    data: MetaAdAccountCreate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new Meta ad account configuration."""
    if not is_encryption_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="META_ENCRYPTION_KEY not configured. Contact administrator.",
        )

    # Check for existing
    existing = db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.organization_id == session.org_id,
            MetaAdAccount.ad_account_external_id == data.ad_account_external_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ad account {data.ad_account_external_id} already exists.",
        )

    # Encrypt tokens
    system_token_encrypted = encrypt_token(data.system_token)
    capi_token_encrypted = encrypt_token(data.capi_token) if data.capi_token else None
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)

    account = MetaAdAccount(
        organization_id=session.org_id,
        ad_account_external_id=data.ad_account_external_id,
        ad_account_name=data.ad_account_name,
        system_token_encrypted=system_token_encrypted,
        token_expires_at=expires_at,
        pixel_id=data.pixel_id,
        capi_enabled=data.capi_enabled,
        capi_token_encrypted=capi_token_encrypted,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@ad_account_router.get("/{account_id}", response_model=MetaAdAccountRead)
def get_meta_ad_account(
    account_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get a specific Meta ad account."""
    account = db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.id == account_id,
            MetaAdAccount.organization_id == session.org_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")
    return account


@ad_account_router.put("/{account_id}", response_model=MetaAdAccountRead)
def update_meta_ad_account(
    account_id: UUID,
    data: MetaAdAccountUpdate,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update Meta ad account configuration."""
    account = db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.id == account_id,
            MetaAdAccount.organization_id == session.org_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")

    if data.ad_account_name is not None:
        account.ad_account_name = data.ad_account_name
    if data.system_token is not None:
        if not is_encryption_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="META_ENCRYPTION_KEY not configured",
            )
        account.system_token_encrypted = encrypt_token(data.system_token)
    if data.expires_days is not None:
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)
    if data.pixel_id is not None:
        account.pixel_id = data.pixel_id
    if data.capi_enabled is not None:
        account.capi_enabled = data.capi_enabled
    if data.capi_token is not None:
        account.capi_token_encrypted = encrypt_token(data.capi_token)
    if data.is_active is not None:
        account.is_active = data.is_active

    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)
    return account


@ad_account_router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meta_ad_account(
    account_id: UUID,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Soft-delete Meta ad account (sets is_active=false).

    Preserves historical data for spend/hierarchy tables.
    """
    account = db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.id == account_id,
            MetaAdAccount.organization_id == session.org_id,
        )
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")

    account.is_active = False
    account.updated_at = datetime.now(timezone.utc)
    db.commit()


# =============================================================================
# Sync Trigger Endpoints
# =============================================================================

sync_router = APIRouter(
    prefix="/admin/meta/sync",
    tags=["admin"],
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)


@sync_router.post("/hierarchy", response_model=SyncTriggerResponse)
async def trigger_hierarchy_sync(
    account_id: UUID | None = None,
    full_sync: bool = False,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Trigger hierarchy sync (campaigns, adsets, ads).

    Args:
        account_id: Specific ad account ID, or sync all if None
        full_sync: If True, fetch all entities. If False, delta sync.
    """
    accounts = _get_accounts(db, session.org_id, account_id)
    if not accounts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No ad accounts found")

    results = []
    for account in accounts:
        result = await meta_sync_service.sync_hierarchy(db, account, full_sync=full_sync)
        results.append(
            {
                "account_id": str(account.id),
                "account_name": account.ad_account_name,
                **result,
            }
        )

    return SyncTriggerResponse(
        success=all(r.get("error") is None for r in results),
        message=f"Hierarchy sync completed for {len(accounts)} account(s)",
        details={"accounts": results},
    )


@sync_router.post("/spend", response_model=SyncTriggerResponse)
async def trigger_spend_sync(
    account_id: UUID | None = None,
    days_back: int = 7,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Trigger spend sync for ad accounts.

    Args:
        account_id: Specific ad account ID, or sync all if None
        days_back: Number of days to sync (default 7)
    """
    from datetime import date, timedelta

    accounts = _get_accounts(db, session.org_id, account_id)
    if not accounts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No ad accounts found")

    today = date.today()
    date_start = today - timedelta(days=days_back)
    date_end = today - timedelta(days=1)  # Yesterday

    results = []
    for account in accounts:
        result = await meta_sync_service.sync_spend(db, account, date_start, date_end)
        results.append(
            {
                "account_id": str(account.id),
                "account_name": account.ad_account_name,
                **result,
            }
        )

    return SyncTriggerResponse(
        success=all(r.get("error") is None for r in results),
        message=f"Spend sync completed for {len(accounts)} account(s)",
        details={"accounts": results},
    )


@sync_router.post("/forms", response_model=SyncTriggerResponse)
async def trigger_forms_sync(
    page_id: str | None = None,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Trigger forms sync.

    NOTE: Forms sync uses page tokens, not ad account tokens.

    Args:
        page_id: Specific page ID, or sync all pages if None
    """
    result = await meta_sync_service.sync_forms(db, session.org_id, page_id)

    return SyncTriggerResponse(
        success=result.get("error") is None,
        message=f"Forms sync completed: {result.get('forms_synced', 0)} forms",
        details=result,
    )


@sync_router.get("/status", response_model=list[SyncStatusResponse])
def get_sync_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get sync status for all ad accounts."""
    accounts = db.scalars(
        select(MetaAdAccount)
        .where(
            MetaAdAccount.organization_id == session.org_id,
            MetaAdAccount.is_active.is_(True),
        )
        .order_by(MetaAdAccount.created_at.desc())
    ).all()

    return [
        SyncStatusResponse(
            ad_account_id=a.id,
            ad_account_name=a.ad_account_name,
            hierarchy_synced_at=a.hierarchy_synced_at,
            spend_synced_at=a.spend_synced_at,
            last_error=a.last_error,
        )
        for a in accounts
    ]


def _get_accounts(db: Session, org_id: UUID, account_id: UUID | None) -> list[MetaAdAccount]:
    """Get ad accounts for sync operations."""
    query = select(MetaAdAccount).where(
        MetaAdAccount.organization_id == org_id,
        MetaAdAccount.is_active.is_(True),
    )
    if account_id:
        query = query.where(MetaAdAccount.id == account_id)

    return list(db.scalars(query).all())
