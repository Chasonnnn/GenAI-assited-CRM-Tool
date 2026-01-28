"""Meta admin service - ad account management helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MetaAdAccount


def list_ad_accounts(db: Session, org_id: UUID) -> list[MetaAdAccount]:
    """List all Meta ad accounts for an organization."""
    return list(
        db.scalars(
            select(MetaAdAccount)
            .where(MetaAdAccount.organization_id == org_id)
            .order_by(MetaAdAccount.created_at.desc())
        ).all()
    )


def list_active_ad_accounts(db: Session, org_id: UUID | None = None) -> list[MetaAdAccount]:
    """List active Meta ad accounts, optionally filtered by org."""
    query = select(MetaAdAccount).where(MetaAdAccount.is_active.is_(True))
    if org_id:
        query = query.where(MetaAdAccount.organization_id == org_id)
    return list(db.scalars(query.order_by(MetaAdAccount.created_at.desc())).all())


def list_active_ad_accounts_for_org(
    db: Session,
    org_id: UUID,
    account_id: UUID | None = None,
) -> list[MetaAdAccount]:
    """List active ad accounts for an org, optionally filtered to a single account."""
    query = select(MetaAdAccount).where(
        MetaAdAccount.organization_id == org_id,
        MetaAdAccount.is_active.is_(True),
    )
    if account_id:
        query = query.where(MetaAdAccount.id == account_id)
    return list(db.scalars(query.order_by(MetaAdAccount.created_at.desc())).all())


def get_ad_account(db: Session, account_id: UUID, org_id: UUID) -> MetaAdAccount | None:
    """Get Meta ad account by ID (org-scoped)."""
    return db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.id == account_id,
            MetaAdAccount.organization_id == org_id,
        )
    )


def get_ad_account_by_external_id(
    db: Session,
    org_id: UUID,
    external_id: str,
) -> MetaAdAccount | None:
    """Get Meta ad account by external ID (org-scoped)."""
    return db.scalar(
        select(MetaAdAccount).where(
            MetaAdAccount.organization_id == org_id,
            MetaAdAccount.ad_account_external_id == external_id,
        )
    )


def create_ad_account(
    db: Session,
    *,
    org_id: UUID,
    ad_account_external_id: str,
    ad_account_name: str | None,
    system_token_encrypted: str | None,
    token_expires_at: datetime | None,
    pixel_id: str | None,
    capi_enabled: bool,
    capi_token_encrypted: str | None,
) -> MetaAdAccount:
    """Create a new Meta ad account record."""
    account = MetaAdAccount(
        organization_id=org_id,
        ad_account_external_id=ad_account_external_id,
        ad_account_name=ad_account_name,
        system_token_encrypted=system_token_encrypted,
        token_expires_at=token_expires_at,
        pixel_id=pixel_id,
        capi_enabled=capi_enabled,
        capi_token_encrypted=capi_token_encrypted,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_ad_account(
    db: Session,
    account: MetaAdAccount,
    *,
    ad_account_name: str | None = None,
    system_token_encrypted: str | None = None,
    token_expires_at: datetime | None = None,
    pixel_id: str | None = None,
    capi_enabled: bool | None = None,
    capi_token_encrypted: str | None = None,
    is_active: bool | None = None,
) -> MetaAdAccount:
    """Update an existing Meta ad account record."""
    if ad_account_name is not None:
        account.ad_account_name = ad_account_name
    if system_token_encrypted is not None:
        account.system_token_encrypted = system_token_encrypted
    if token_expires_at is not None:
        account.token_expires_at = token_expires_at
    if pixel_id is not None:
        account.pixel_id = pixel_id
    if capi_enabled is not None:
        account.capi_enabled = capi_enabled
    if capi_token_encrypted is not None:
        account.capi_token_encrypted = capi_token_encrypted
    if is_active is not None:
        account.is_active = is_active

    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)
    return account


def deactivate_ad_account(db: Session, account: MetaAdAccount) -> None:
    """Soft-delete an ad account (set inactive)."""
    account.is_active = False
    account.updated_at = datetime.now(timezone.utc)
    db.commit()
