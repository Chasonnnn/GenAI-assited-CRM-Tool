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


if __name__ == "__main__":
    cli()
