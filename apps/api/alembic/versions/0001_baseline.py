"""Baseline migration - Authentication and Tenant tables

Revision ID: 0001_baseline
Revises: 
Create Date: 2025-12-12

This is the fresh baseline migration for the CRM platform.
Creates all authentication and tenant isolation tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create authentication and tenant tables."""
    
    # ==========================================================================
    # Enable required extensions
    # ==========================================================================
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')  # For gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS citext')    # For case-insensitive text
    
    # ==========================================================================
    # Organizations
    # ==========================================================================
    op.execute('''
        CREATE TABLE organizations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''')
    
    # ==========================================================================
    # Users
    # ==========================================================================
    op.execute('''
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email CITEXT UNIQUE NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            avatar_url VARCHAR(500),
            token_version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''')
    
    # ==========================================================================
    # Memberships (one org per user)
    # ==========================================================================
    op.execute('''
        CREATE TABLE memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''')
    op.execute('CREATE INDEX idx_memberships_org_id ON memberships(organization_id)')
    
    # ==========================================================================
    # Auth Identities (SSO linking)
    # ==========================================================================
    op.execute('''
        CREATE TABLE auth_identities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            provider_subject VARCHAR(255) NOT NULL,
            email CITEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(provider, provider_subject)
        )
    ''')
    op.execute('CREATE INDEX idx_auth_identities_user_id ON auth_identities(user_id)')
    
    # ==========================================================================
    # Org Invites
    # ==========================================================================
    op.execute('''
        CREATE TABLE org_invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            email CITEXT NOT NULL,
            role VARCHAR(50) NOT NULL,
            invited_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ,
            accepted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''')
    # Partial unique: only one pending invite per email globally
    op.execute('''
        CREATE UNIQUE INDEX uq_pending_invite_email 
        ON org_invites (email) 
        WHERE accepted_at IS NULL
    ''')
    op.execute('CREATE INDEX idx_org_invites_org_id ON org_invites(organization_id)')
    
    # ==========================================================================
    # Trigger: Auto-update updated_at on row modification
    # ==========================================================================
    op.execute('''
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    ''')
    
    op.execute('''
        CREATE TRIGGER update_organizations_updated_at
            BEFORE UPDATE ON organizations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    ''')
    
    op.execute('''
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    ''')


def downgrade() -> None:
    """Drop all authentication tables."""
    
    # Drop triggers first
    op.execute('DROP TRIGGER IF EXISTS update_users_updated_at ON users')
    op.execute('DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    
    # Drop tables in reverse order (respecting foreign keys)
    op.execute('DROP INDEX IF EXISTS idx_org_invites_org_id')
    op.execute('DROP INDEX IF EXISTS uq_pending_invite_email')
    op.execute('DROP TABLE IF EXISTS org_invites')
    
    op.execute('DROP INDEX IF EXISTS idx_auth_identities_user_id')
    op.execute('DROP TABLE IF EXISTS auth_identities')
    
    op.execute('DROP INDEX IF EXISTS idx_memberships_org_id')
    op.execute('DROP TABLE IF EXISTS memberships')
    
    op.execute('DROP TABLE IF EXISTS users')
    op.execute('DROP TABLE IF EXISTS organizations')
