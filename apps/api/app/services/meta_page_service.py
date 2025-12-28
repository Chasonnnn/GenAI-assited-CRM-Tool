"""Meta page mapping service."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import MetaPageMapping


def list_meta_pages(db: Session, org_id: UUID) -> list[MetaPageMapping]:
    """List meta page mappings for an organization."""
    return (
        db.query(MetaPageMapping)
        .filter(MetaPageMapping.organization_id == org_id)
        .order_by(MetaPageMapping.created_at.desc())
        .all()
    )


def list_active_mappings(db: Session) -> list[MetaPageMapping]:
    """List active Meta page mappings across all orgs."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.is_active.is_(True),
        )
        .all()
    )


def list_problem_pages(db: Session) -> list[MetaPageMapping]:
    """List Meta page mappings with recent errors."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.last_error.isnot(None),
        )
        .all()
    )


def get_mapping_by_page_id(
    db: Session,
    org_id: UUID,
    page_id: str,
) -> MetaPageMapping | None:
    """Get mapping by page id scoped to org."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.page_id == page_id,
            MetaPageMapping.organization_id == org_id,
        )
        .first()
    )


def get_mapping_by_page_id_any_org(
    db: Session,
    page_id: str,
) -> MetaPageMapping | None:
    """Get mapping by page id without org scoping."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.page_id == page_id,
        )
        .first()
    )


def get_active_mapping_by_page_id(
    db: Session,
    page_id: str,
) -> MetaPageMapping | None:
    """Get active mapping for a page id."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.page_id == page_id,
            MetaPageMapping.is_active.is_(True),
        )
        .first()
    )


def get_first_active_mapping(db: Session) -> MetaPageMapping | None:
    """Get first active mapping (for dev/test use)."""
    return (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.is_active.is_(True),
        )
        .first()
    )


def create_mapping(
    db: Session,
    org_id: UUID,
    page_id: str,
    page_name: str | None,
    access_token_encrypted: str,
    token_expires_at: datetime,
) -> MetaPageMapping:
    """Create a new meta page mapping."""
    mapping = MetaPageMapping(
        organization_id=org_id,
        page_id=page_id,
        page_name=page_name,
        access_token_encrypted=access_token_encrypted,
        token_expires_at=token_expires_at,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def update_mapping(
    db: Session,
    mapping: MetaPageMapping,
    page_name: str | None = None,
    access_token_encrypted: str | None = None,
    token_expires_at: datetime | None = None,
    is_active: bool | None = None,
) -> MetaPageMapping:
    """Update a meta page mapping."""
    if page_name is not None:
        mapping.page_name = page_name
    if access_token_encrypted is not None:
        mapping.access_token_encrypted = access_token_encrypted
    if token_expires_at is not None:
        mapping.token_expires_at = token_expires_at
    if is_active is not None:
        mapping.is_active = is_active
        if is_active:
            mapping.last_error = None

    db.commit()
    db.refresh(mapping)
    return mapping


def delete_mapping(db: Session, mapping: MetaPageMapping) -> None:
    """Delete a meta page mapping."""
    db.delete(mapping)
    db.commit()
