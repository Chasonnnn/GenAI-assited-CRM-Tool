"""CLI tools for Surrogacy Force administration."""

import click
from sqlalchemy import func

from app.db.enums import Role
from app.db.models import Organization, OrgInvite, User, Membership
from app.db.session import SessionLocal
from app.services import org_service


@click.group()
def cli():
    """Surrogacy Force CLI tools."""
    pass


@cli.command()
@click.option("--name", required=True, help="Organization name")
@click.option("--slug", required=True, help="URL-friendly slug (lowercase, no spaces)")
@click.option("--admin-email", required=True, help="Admin email address")
@click.option("--developer-email", required=False, help="Developer email address (optional)")
@click.option("--portal-domain", required=False, help="Portal domain host (e.g. ap.example.com)")
@click.option(
    "--base-domain",
    required=False,
    help="Base domain for portal (builds ap.<domain>)",
)
def create_org(
    name: str,
    slug: str,
    admin_email: str,
    developer_email: str | None,
    portal_domain: str | None,
    base_domain: str | None,
):
    """
    Create organization and initial admin invite.

    This is the bootstrap command for setting up a new tenant.
    The admin will need to log in with Google using the specified email.

    Example:
        python -m app.cli create-org --name "Acme Corp" --slug "acme" --admin-email "admin@acme.com"
        python -m app.cli create-org --name "Acme Corp" --slug "acme" --admin-email "admin@acme.com" --developer-email "dev@acme.com"
        python -m app.cli create-org --name "Acme Corp" --slug "acme" --admin-email "admin@acme.com" --base-domain "acme.com"
        python -m app.cli create-org --name "Acme Corp" --slug "acme" --admin-email "admin@acme.com" --portal-domain "ap.acme.com"
    """
    db = SessionLocal()
    try:
        admin_email = admin_email.lower().strip()
        developer_email = developer_email.lower().strip() if developer_email else None
        portal_domain = portal_domain.lower().strip() if portal_domain else None
        base_domain = base_domain.lower().strip() if base_domain else None

        if portal_domain and base_domain:
            click.echo("[ERROR] Provide either --portal-domain or --base-domain, not both")
            return

        # Validate slug format
        slug = slug.lower().strip()
        if not slug.replace("-", "").replace("_", "").isalnum():
            click.echo("[ERROR] Slug must be alphanumeric (with optional hyphens/underscores)")
            return

        # Check if org already exists
        existing = db.query(Organization).filter(Organization.slug == slug).first()
        if existing:
            click.echo(f"[ERROR] Organization with slug '{slug}' already exists")
            return

        if developer_email == admin_email:
            click.echo(
                "[INFO] Admin email matches developer email; creating developer invite only."
            )
            developer_email = None
            admin_role = Role.DEVELOPER.value
        else:
            admin_role = Role.ADMIN.value

        # Check for existing pending invite for admin email
        existing_admin_invite = (
            db.query(OrgInvite)
            .filter(
                OrgInvite.email == admin_email,
                OrgInvite.accepted_at.is_(None),
                OrgInvite.revoked_at.is_(None),
            )
            .first()
        )
        if existing_admin_invite:
            click.echo(f"[ERROR] Pending invite already exists for {admin_email}")
            return

        if developer_email:
            existing_dev_invite = (
                db.query(OrgInvite)
                .filter(
                    OrgInvite.email == developer_email,
                    OrgInvite.accepted_at.is_(None),
                    OrgInvite.revoked_at.is_(None),
                )
                .first()
            )
            if existing_dev_invite:
                click.echo(f"[ERROR] Pending invite already exists for {developer_email}")
                return

        # Check if admin email is already bound to a different org
        existing_user = db.query(User).filter(func.lower(User.email) == admin_email).first()
        if existing_user:
            existing_membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == existing_user.id,
                    Membership.is_active.is_(True),
                )
                .first()
            )
            if existing_membership:
                click.echo(f"[ERROR] User already belongs to an organization: {admin_email}")
                return

        if developer_email:
            existing_dev_user = (
                db.query(User).filter(func.lower(User.email) == developer_email).first()
            )
            if existing_dev_user:
                existing_dev_membership = (
                    db.query(Membership)
                    .filter(
                        Membership.user_id == existing_dev_user.id,
                        Membership.is_active.is_(True),
                    )
                    .first()
                )
                if existing_dev_membership:
                    click.echo(
                        f"[ERROR] User already belongs to an organization: {developer_email}"
                    )
                    return

        if base_domain and not portal_domain:
            try:
                portal_domain = org_service.build_portal_domain(base_domain)
            except ValueError as e:
                click.echo(f"[ERROR] {e}")
                return

        if portal_domain:
            try:
                portal_domain = org_service.normalize_portal_domain(portal_domain)
            except ValueError as e:
                click.echo(f"[ERROR] {e}")
                return

        # Create organization with defaults
        org = org_service.create_org(db, name=name, slug=slug, portal_domain=portal_domain)

        # Create admin invite (never expires for bootstrap)
        invite = OrgInvite(
            organization_id=org.id,
            email=admin_email,
            role=admin_role,
            expires_at=None,  # Never expires
            invited_by_user_id=None,  # CLI bootstrap has no inviter
        )
        db.add(invite)

        if developer_email:
            dev_invite = OrgInvite(
                organization_id=org.id,
                email=developer_email,
                role=Role.DEVELOPER.value,
                expires_at=None,
                invited_by_user_id=None,
            )
            db.add(dev_invite)
        db.commit()

        click.echo(f"[OK] Created organization: {name}")
        click.echo(f"  ID: {org.id}")
        click.echo(f"  Slug: {slug}")
        if portal_domain:
            click.echo(f"  Portal domain: {portal_domain}")
        click.echo(f"[OK] Created invite for {admin_email} with role: {admin_role}")
        if developer_email:
            click.echo(f"[OK] Created invite for {developer_email} with role: developer")
        click.echo("→ Invitee should log in with Google using that email")

    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--email", required=True, help="User email to promote")
@click.option("--org-slug", required=False, help="Org slug for membership validation")
def promote_to_developer(email: str, org_slug: str | None):
    """
    Promote an existing member to Developer role.

    Example:
        python -m app.cli promote-to-developer --email "dev@acme.com"
        python -m app.cli promote-to-developer --email "dev@acme.com" --org-slug "acme"
    """
    db = SessionLocal()
    try:
        email = email.lower().strip()
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            click.echo(f"[ERROR] User not found: {email}")
            return

        membership = (
            db.query(Membership)
            .filter(Membership.user_id == user.id, Membership.is_active.is_(True))
            .first()
        )
        if not membership:
            click.echo(f"[ERROR] No active membership found for {email}")
            return

        if org_slug:
            org = db.query(Organization).filter(Organization.slug == org_slug.lower()).first()
            if not org:
                click.echo(f"[ERROR] Organization not found: {org_slug}")
                return
            if membership.organization_id != org.id:
                click.echo("[ERROR] Membership does not match the specified org slug")
                return

        if membership.role == Role.DEVELOPER.value:
            click.echo(f"[OK] {email} is already a developer")
            return

        membership.role = Role.DEVELOPER.value
        db.commit()

        click.echo(f"[OK] Promoted {email} to developer role")
    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--email", required=True, help="User email to revoke sessions for")
def revoke_sessions(email: str):
    """
    Revoke all sessions for a user by bumping their token_version.

    Example:
        python -m app.cli revoke-sessions --email "user@example.com"
    """
    from app.db.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            click.echo(f"[ERROR] User not found: {email}")
            return

        old_version = user.token_version
        user.token_version += 1
        db.commit()

        click.echo(f"[OK] Revoked all sessions for {email}")
        click.echo(f"  Token version: {old_version} → {user.token_version}")

    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--page-id", required=True, help="Meta page ID")
@click.option("--access-token", required=True, help="Page access token")
@click.option("--org-slug", required=True, help="Organization slug")
@click.option("--page-name", default=None, help="Optional page name for display")
@click.option("--expires-days", default=60, help="Token expiry in days (default: 60)")
def update_meta_page_token(
    page_id: str,
    access_token: str,
    org_slug: str,
    page_name: str | None,
    expires_days: int,
):
    """
    Create or update Meta page mapping with encrypted token.
    
    This is used to onboard a Meta page for lead ad integration.
    The access token will be encrypted at rest.
    
    Example:
        python -m app.cli update-meta-page-token \\
            --page-id "123456789" \\
            --access-token "EAAxx..." \\
            --org-slug "acme" \\
            --page-name "Acme Agency" \\
            --expires-days 60
    """
    from datetime import datetime, timedelta, timezone
    from app.db.models import MetaPageMapping
    from app.core.encryption import encrypt_token, is_encryption_configured

    if not is_encryption_configured():
        click.echo("[ERROR] META_ENCRYPTION_KEY not configured in .env")
        click.echo(
            '   Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
        return

    db = SessionLocal()
    try:
        # Find organization
        org = db.query(Organization).filter(Organization.slug == org_slug.lower()).first()
        if not org:
            click.echo(f"[ERROR] Organization not found: {org_slug}")
            return

        # Encrypt token
        encrypted = encrypt_token(access_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        # Check for existing mapping
        existing = db.query(MetaPageMapping).filter(MetaPageMapping.page_id == page_id).first()

        if existing:
            # Update existing
            existing.organization_id = org.id
            existing.access_token_encrypted = encrypted
            existing.token_expires_at = expires_at
            existing.is_active = True
            existing.last_error = None
            if page_name:
                existing.page_name = page_name
            db.commit()
            click.echo(f"[OK] Updated page mapping for page_id={page_id}")
        else:
            # Create new
            mapping = MetaPageMapping(
                organization_id=org.id,
                page_id=page_id,
                page_name=page_name,
                access_token_encrypted=encrypted,
                token_expires_at=expires_at,
                is_active=True,
            )
            db.add(mapping)
            db.commit()
            click.echo(f"[OK] Created page mapping for page_id={page_id}")

        click.echo(f"  Organization: {org.name} ({org.slug})")
        click.echo(f"  Token expires: {expires_at.strftime('%Y-%m-%d')}")

    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--page-id", required=True, help="Meta page ID to deactivate")
def deactivate_meta_page(page_id: str):
    """
    Deactivate a Meta page mapping.

    This disables webhook processing for the page without deleting the mapping.

    Example:
        python -m app.cli deactivate-meta-page --page-id "123456789"
    """
    from app.db.models import MetaPageMapping

    db = SessionLocal()
    try:
        mapping = db.query(MetaPageMapping).filter(MetaPageMapping.page_id == page_id).first()

        if not mapping:
            click.echo(f"[ERROR] Page mapping not found: {page_id}")
            return

        mapping.is_active = False
        db.commit()

        click.echo(f"[OK] Deactivated page mapping for page_id={page_id}")

    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
def backfill_permissions(dry_run: bool):
    """
    Backfill new permissions to all organizations.

    Run this after adding new permissions to PERMISSION_REGISTRY or ROLE_DEFAULTS.
    Creates missing role_permissions rows for each org.

    Recommended: Run nightly via cron or on deploy.

    Example:
        python -m app.cli backfill-permissions
        python -m app.cli backfill-permissions --dry-run
    """
    from app.services import permission_service
    from app.core.permissions import PERMISSION_REGISTRY, ROLE_DEFAULTS

    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        click.echo(f"Found {len(orgs)} organization(s)")
        click.echo(f"Permission registry: {len(PERMISSION_REGISTRY)} permissions")
        click.echo(f"Role defaults: {list(ROLE_DEFAULTS.keys())}")
        click.echo()

        if dry_run:
            click.echo("🔍 DRY RUN - no changes will be made")
            click.echo()

        total_created = 0
        for org in orgs:
            if dry_run:
                # Count what would be created
                from app.db.models import RolePermission

                count = 0
                for role, permissions in ROLE_DEFAULTS.items():
                    if role == "developer":
                        continue
                    for permission in permissions:
                        existing = (
                            db.query(RolePermission)
                            .filter(
                                RolePermission.organization_id == org.id,
                                RolePermission.role == role,
                                RolePermission.permission == permission,
                            )
                            .first()
                        )
                        if not existing:
                            count += 1
                if count > 0:
                    click.echo(f"  {org.slug}: would create {count} permissions")
                    total_created += count
            else:
                created = permission_service.seed_role_defaults(db, org.id)
                if created > 0:
                    click.echo(f"  {org.slug}: created {created} permissions")
                    total_created += created

        if not dry_run:
            db.commit()

        click.echo()
        if total_created > 0:
            verb = "would create" if dry_run else "created"
            click.echo(f"[OK] {verb.capitalize()} {total_created} total permission(s)")
        else:
            click.echo("[OK] All permissions already up to date")

    except Exception as e:
        db.rollback()
        click.echo(f"[ERROR] Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cli()
