"""Organization service - org operations."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Organization


def get_org_by_id(db: Session, org_id: UUID) -> Organization | None:
    """Get organization by ID."""
    return db.query(Organization).filter(Organization.id == org_id).first()


def get_org_by_slug(db: Session, slug: str) -> Organization | None:
    """Get organization by slug."""
    return db.query(Organization).filter(Organization.slug == slug.lower()).first()


def create_org(db: Session, name: str, slug: str) -> Organization:
    """
    Create a new organization.
    
    Raises:
        IntegrityError: If slug already exists
    """
    org = Organization(name=name, slug=slug.lower())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def update_org(
    db: Session,
    org_id: UUID,
    name: str | None = None,
) -> Organization | None:
    """
    Update organization details.
    
    Note: Slug is not updateable to preserve URL stability.
    
    Returns:
        Updated org or None if not found
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return None
    
    if name is not None:
        org.name = name
    
    db.commit()
    db.refresh(org)
    return org
