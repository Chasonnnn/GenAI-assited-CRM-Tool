"""Organization service - org operations with version control."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Organization
from app.services import version_service


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


def update_org_settings(
    db: Session,
    org: Organization,
    user_id: UUID,
    name: str | None = None,
    ai_enabled: bool | None = None,
    expected_version: int | None = None,
) -> Organization:
    """
    Update organization settings with version snapshot.
    
    Creates a version snapshot before applying changes.
    
    Raises:
        VersionConflictError: If expected_version doesn't match
    """
    # Optimistic locking check
    if expected_version is not None and org.current_version != expected_version:
        raise version_service.VersionConflictError(expected_version, org.current_version)
    
    # Create snapshot of current state
    before_version = version_service.create_version_snapshot(
        db,
        org_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        version=org.current_version,
        payload={
            "name": org.name,
            "slug": org.slug,
            "ai_enabled": org.ai_enabled,
        },
        user_id=user_id,
        comment="Before settings update",
    )
    
    # Apply changes
    if name is not None:
        org.name = name
    if ai_enabled is not None:
        org.ai_enabled = ai_enabled
    
    org.current_version += 1
    
    # Create snapshot of new state
    version_service.create_version_snapshot(
        db,
        org_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        version=org.current_version,
        payload={
            "name": org.name,
            "slug": org.slug,
            "ai_enabled": org.ai_enabled,
        },
        user_id=user_id,
        comment="After settings update",
    )
    
    db.commit()
    db.refresh(org)
    return org


def get_org_versions(db: Session, org_id: UUID) -> list:
    """Get version history for an organization."""
    return version_service.get_versions(db, org_id, "organization", org_id)


def rollback_org_settings(
    db: Session,
    org: Organization,
    target_version: int,
    user_id: UUID,
) -> Organization:
    """
    Rollback organization settings to a previous version.
    
    Creates a new version with the old settings (history is never rewritten).
    """
    # Get the target version payload
    version = version_service.get_version_at(
        db, org.id, "organization", org.id, target_version
    )
    if not version:
        raise ValueError(f"Version {target_version} not found")
    
    payload = version_service.decrypt_version_payload(version)
    
    # Create new version from old state
    org.name = payload.get("name", org.name)
    org.ai_enabled = payload.get("ai_enabled", org.ai_enabled)
    org.current_version += 1
    
    version_service.create_version_snapshot(
        db,
        org_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        version=org.current_version,
        payload={
            "name": org.name,
            "slug": org.slug,
            "ai_enabled": org.ai_enabled,
        },
        user_id=user_id,
        comment=f"Rolled back from v{target_version}",
    )
    
    db.commit()
    db.refresh(org)
    return org


# Legacy function for backward compatibility
def update_org(
    db: Session,
    org_id: UUID,
    name: str | None = None,
) -> Organization | None:
    """
    Update organization details (legacy - no version control).
    
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
