"""Meta admin service - ad account management helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
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
    ad_account_name: str | None = None,
    pixel_id: str | None = None,
    capi_enabled: bool = False,
    oauth_connection_id: UUID | None = None,
) -> MetaAdAccount:
    """Create a new Meta ad account record."""
    account = MetaAdAccount(
        organization_id=org_id,
        ad_account_external_id=ad_account_external_id,
        ad_account_name=ad_account_name,
        pixel_id=pixel_id,
        capi_enabled=capi_enabled,
        oauth_connection_id=oauth_connection_id,
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
    pixel_id: str | None = None,
    capi_enabled: bool | None = None,
    is_active: bool | None = None,
) -> MetaAdAccount:
    """Update an existing Meta ad account record."""
    if ad_account_name is not None:
        account.ad_account_name = ad_account_name
    if pixel_id is not None:
        account.pixel_id = pixel_id
    if capi_enabled is not None:
        account.capi_enabled = capi_enabled
    if is_active is not None:
        account.is_active = is_active

    db.commit()
    db.refresh(account)
    return account


def deactivate_ad_account(db: Session, account: MetaAdAccount) -> None:
    """Soft-delete an ad account (set inactive)."""
    account.is_active = False
    db.commit()


def unlink_accounts_by_connection(db: Session, connection_id: UUID) -> list[UUID]:
    """Unlink all ad accounts from an OAuth connection."""
    return list(
        db.execute(
            update(MetaAdAccount)
            .where(MetaAdAccount.oauth_connection_id == connection_id)
            .values(oauth_connection_id=None)
            .returning(MetaAdAccount.id)
        )
        .scalars()
        .all()
    )
