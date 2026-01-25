"""Organization service - org operations with version control."""

from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Organization
from app.services import version_service


def get_org_by_id(
    db: Session, org_id: UUID, *, include_deleted: bool = False
) -> Organization | None:
    """Get organization by ID."""
    query = db.query(Organization).filter(Organization.id == org_id)
    if not include_deleted:
        query = query.filter(Organization.deleted_at.is_(None))
    return query.first()


def list_orgs(db: Session, *, include_deleted: bool = False) -> list[Organization]:
    """List all organizations."""
    query = db.query(Organization)
    if not include_deleted:
        query = query.filter(Organization.deleted_at.is_(None))
    return query.all()


def get_org_by_slug(
    db: Session, slug: str, *, include_deleted: bool = False
) -> Organization | None:
    """Get organization by slug."""
    query = db.query(Organization).filter(Organization.slug == slug.lower())
    if not include_deleted:
        query = query.filter(Organization.deleted_at.is_(None))
    return query.first()


def create_org(
    db: Session,
    name: str,
    slug: str,
    portal_domain: str | None = None,
) -> Organization:
    """
    Create a new organization.

    Raises:
        IntegrityError: If slug already exists
    """
    org = Organization(name=name, slug=slug.lower())
    if portal_domain:
        org.portal_domain = normalize_portal_domain(portal_domain)
    db.add(org)
    db.commit()
    db.refresh(org)

    # Seed default role permissions for new org
    from app.services import permission_service, compliance_service

    permission_service.seed_role_defaults(db, org.id)
    db.commit()

    compliance_service.seed_default_retention_policies(db, org.id)

    seed_org_defaults(db, org.id)

    return org


def seed_org_defaults(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
) -> dict:
    """Seed default org configuration for pipelines, queues, and templates."""
    from app.services import queue_service, template_seeder

    seed_result = template_seeder.seed_all(db, org_id, user_id)
    queue_service.get_or_create_default_queue(db, org_id)
    queue_service.get_or_create_surrogate_pool_queue(db, org_id)
    db.commit()

    return {
        **seed_result,
        "queues_seeded": True,
    }


def normalize_portal_domain(domain: str) -> str:
    """Normalize a portal domain to host[:port] format."""
    value = domain.strip().lower()
    if not value:
        raise ValueError("Portal domain must not be empty")

    parsed = urlparse(value if "://" in value else f"https://{value}")
    if not parsed.hostname:
        raise ValueError("Portal domain is invalid")
    if parsed.username or parsed.password:
        raise ValueError("Portal domain must not include credentials")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Portal domain must not include a path or query")

    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return host


def build_portal_domain(base_domain: str, prefix: str = "ap") -> str:
    """Build a portal domain from a base domain and prefix."""
    base_host = normalize_portal_domain(base_domain)
    prefix_value = prefix.strip().lower().strip(".")
    if not prefix_value:
        raise ValueError("Portal prefix must not be empty")
    if base_host.startswith(f"{prefix_value}."):
        return base_host
    return normalize_portal_domain(f"{prefix_value}.{base_host}")


def get_org_portal_base_url(org: Organization | None) -> str:
    """Resolve the portal base URL for an organization."""
    if org and org.portal_domain:
        return f"https://{org.portal_domain}"
    return settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""


def get_org_display_name(org: Organization | None) -> str:
    """Resolve the organization name for external display."""
    if not org:
        return "Unknown Organization"
    branded_name = (org.signature_company_name or "").strip()
    return branded_name or org.name


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


PORTAL_DOMAIN_UNSET = object()


def update_org_contact(
    db: Session,
    org: Organization,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    portal_domain: str | None | object = PORTAL_DOMAIN_UNSET,
) -> Organization:
    """Update organization contact settings."""
    if name is not None:
        org.name = name
    if address is not None and hasattr(org, "address"):
        org.address = address
    if phone is not None and hasattr(org, "phone"):
        org.phone = phone
    if email is not None and hasattr(org, "contact_email"):
        org.contact_email = email
    if portal_domain is not PORTAL_DOMAIN_UNSET:
        org.portal_domain = portal_domain

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
    version = version_service.get_version_at(db, org.id, "organization", org.id, target_version)
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
