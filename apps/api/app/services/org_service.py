"""Organization service - org operations with version control."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Organization
from app.services import version_service


# Reserved slugs that cannot be used for organizations (system/infra/env names)
RESERVED_SLUGS = frozenset(
    {
        # System
        "ops",
        "api",
        "admin",
        "app",
        "www",
        # Infra
        "cdn",
        "static",
        "assets",
        "media",
        # Env
        "dev",
        "test",
        "staging",
        "prod",
        "demo",
        "qa",
        # Email/Network
        "mail",
        "smtp",
        "imap",
        "pop",
        "ftp",
        # Support
        "support",
        "help",
        "status",
    }
)


def validate_slug(slug: str) -> str:
    """
    Validate organization slug for DNS compliance.

    Returns normalized (lowercase) slug or raises ValueError.

    Rules:
    - Minimum 2 characters
    - Alphanumeric with hyphens only (no underscores)
    - Cannot start or end with hyphen
    - Cannot be a reserved slug
    """
    normalized = slug.strip().lower()

    if len(normalized) < 2:
        raise ValueError("Slug must be at least 2 characters")

    # DNS hostname compliant: letters, digits, hyphens only (no underscores)
    if not normalized.replace("-", "").isalnum():
        raise ValueError("Slug must be alphanumeric with hyphens only")

    # Cannot start or end with hyphen
    if normalized.startswith("-") or normalized.endswith("-"):
        raise ValueError("Slug cannot start or end with hyphen")

    if normalized in RESERVED_SLUGS:
        raise ValueError(f"Reserved slug: {normalized}")

    return normalized


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
) -> Organization:
    """
    Create a new organization.

    Args:
        db: Database session
        name: Organization display name
        slug: URL slug (will be validated and normalized)

    Raises:
        ValueError: If slug is invalid or reserved
        IntegrityError: If slug already exists
    """
    validated_slug = validate_slug(slug)
    org = Organization(name=name, slug=validated_slug)
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


def get_org_portal_base_url(org: Organization | None) -> str:
    """
    Compute the portal base URL for an organization from its slug.

    Returns: https://{slug}.{PLATFORM_BASE_DOMAIN} in production,
             or FRONTEND_URL fallback for dev/test.
    """
    if org and org.slug and settings.PLATFORM_BASE_DOMAIN:
        return f"https://{org.slug}.{settings.PLATFORM_BASE_DOMAIN}"
    return settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""


def get_org_by_host(db: Session, host: str) -> Organization | None:
    """
    Get organization by hostname (e.g., ewi.surrogacyforce.com → org with slug=ewi).

    Args:
        db: Database session
        host: Request hostname (may include port)

    Returns:
        Organization if found, None otherwise
    """
    # Normalize: lowercase, strip port, strip trailing dot
    host = host.lower().split(":")[0].rstrip(".")

    base_domain = settings.PLATFORM_BASE_DOMAIN

    # Dev bypass: allow localhost, *.localhost, *.test
    # Exception: If PLATFORM_BASE_DOMAIN=localhost, allow .localhost subdomains for testing
    if settings.ENV.lower() in ("dev", "development", "test"):
        # Skip bypass for .localhost when testing with PLATFORM_BASE_DOMAIN=localhost
        is_local_proxy_test = base_domain == "localhost" and host.endswith(".localhost")
        if not is_local_proxy_test and (
            host in ("localhost", "127.0.0.1")
            or host.endswith(".localhost")
            or host.endswith(".test")
        ):
            return None  # Skip org resolution for dev

    if not host.endswith(f".{base_domain}"):
        return None

    slug = host.removesuffix(f".{base_domain}")
    if not slug:
        return None

    return get_org_by_slug(db, slug)


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


def update_org_contact(
    db: Session,
    org: Organization,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
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

    db.commit()
    db.refresh(org)
    return org


def update_org_slug(
    db: Session,
    org: Organization,
    new_slug: str,
) -> tuple[Organization, str]:
    """
    Update organization slug (platform admin only).

    After slug change, existing sessions on the old subdomain will be rejected
    when they try to access the new subdomain. Users must re-login.

    Args:
        db: Database session
        org: Organization to update
        new_slug: New slug (will be validated and normalized)

    Returns:
        Tuple of (updated org, old_slug for audit logging)

    Raises:
        ValueError: If slug is invalid, reserved, or already taken
    """
    validated_slug = validate_slug(new_slug)

    if validated_slug == org.slug:
        return org, org.slug  # No change

    # Check uniqueness
    existing = get_org_by_slug(db, validated_slug)
    if existing and existing.id != org.id:
        raise ValueError("Slug already in use")

    old_slug = org.slug
    org.slug = validated_slug
    db.commit()
    db.refresh(org)

    return org, old_slug


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
