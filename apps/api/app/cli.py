"""CLI tools for CRM administration."""

import click

from app.db.enums import Role
from app.db.models import Organization, OrgInvite
from app.db.session import SessionLocal


@click.group()
def cli():
    """CRM CLI tools."""
    pass


@cli.command()
@click.option("--name", required=True, help="Organization name")
@click.option("--slug", required=True, help="URL-friendly slug (lowercase, no spaces)")
@click.option("--admin-email", required=True, help="Admin email address")
def create_org(name: str, slug: str, admin_email: str):
    """
    Create organization and initial manager invite.
    
    This is the bootstrap command for setting up a new tenant.
    The admin will need to log in with Google using the specified email.
    
    Example:
        python -m app.cli create-org --name "Acme Corp" --slug "acme" --admin-email "admin@acme.com"
    """
    db = SessionLocal()
    try:
        # Validate slug format
        slug = slug.lower().strip()
        if not slug.replace("-", "").replace("_", "").isalnum():
            click.echo("❌ Slug must be alphanumeric (with optional hyphens/underscores)")
            return
        
        # Check if org already exists
        existing = db.query(Organization).filter(Organization.slug == slug).first()
        if existing:
            click.echo(f"❌ Organization with slug '{slug}' already exists")
            return
        
        # Check for existing pending invite for this email
        existing_invite = db.query(OrgInvite).filter(
            OrgInvite.email == admin_email.lower(),
            OrgInvite.accepted_at.is_(None)
        ).first()
        if existing_invite:
            click.echo(f"❌ Pending invite already exists for {admin_email}")
            return
        
        # Create organization
        org = Organization(name=name, slug=slug)
        db.add(org)
        db.flush()
        
        # Create invite (never expires for bootstrap)
        invite = OrgInvite(
            organization_id=org.id,
            email=admin_email.lower(),
            role=Role.MANAGER.value,
            expires_at=None,  # Never expires
            invited_by_user_id=None,  # CLI bootstrap has no inviter
        )
        db.add(invite)
        db.commit()
        
        click.echo(f"✓ Created organization: {name}")
        click.echo(f"  ID: {org.id}")
        click.echo(f"  Slug: {slug}")
        click.echo(f"✓ Created invite for {admin_email} with role: manager")
        click.echo(f"→ Admin should log in with Google using that email")
        
    except Exception as e:
        db.rollback()
        click.echo(f"❌ Error: {e}")
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
            click.echo(f"❌ User not found: {email}")
            return
        
        old_version = user.token_version
        user.token_version += 1
        db.commit()
        
        click.echo(f"✓ Revoked all sessions for {email}")
        click.echo(f"  Token version: {old_version} → {user.token_version}")
        
    except Exception as e:
        db.rollback()
        click.echo(f"❌ Error: {e}")
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
    from datetime import datetime, timedelta
    from app.db.models import MetaPageMapping
    from app.core.encryption import encrypt_token, is_encryption_configured
    
    if not is_encryption_configured():
        click.echo("❌ META_ENCRYPTION_KEY not configured in .env")
        click.echo("   Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return
    
    db = SessionLocal()
    try:
        # Find organization
        org = db.query(Organization).filter(Organization.slug == org_slug.lower()).first()
        if not org:
            click.echo(f"❌ Organization not found: {org_slug}")
            return
        
        # Encrypt token
        encrypted = encrypt_token(access_token)
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # Check for existing mapping
        existing = db.query(MetaPageMapping).filter(
            MetaPageMapping.page_id == page_id
        ).first()
        
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
            click.echo(f"✓ Updated page mapping for page_id={page_id}")
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
            click.echo(f"✓ Created page mapping for page_id={page_id}")
        
        click.echo(f"  Organization: {org.name} ({org.slug})")
        click.echo(f"  Token expires: {expires_at.strftime('%Y-%m-%d')}")
        
    except Exception as e:
        db.rollback()
        click.echo(f"❌ Error: {e}")
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
        mapping = db.query(MetaPageMapping).filter(
            MetaPageMapping.page_id == page_id
        ).first()
        
        if not mapping:
            click.echo(f"❌ Page mapping not found: {page_id}")
            return
        
        mapping.is_active = False
        db.commit()
        
        click.echo(f"✓ Deactivated page mapping for page_id={page_id}")
        
    except Exception as e:
        db.rollback()
        click.echo(f"❌ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
