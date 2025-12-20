"""Rename manager role to admin.

Revision ID: 0041_rename_manager_to_admin
Revises: 0040_permission_system
Create Date: 2024-12-20
"""
from alembic import op
import sqlalchemy as sa


revision = '0041_rename_manager_to_admin'
down_revision = '0040_permission_system'
branch_labels = None
depends_on = None


def upgrade():
    """Rename 'manager' to 'admin' in role columns."""
    # Update membership.role
    op.execute("UPDATE membership SET role = 'admin' WHERE role = 'manager'")
    
    # Update org_invite.role
    op.execute("UPDATE org_invite SET role = 'admin' WHERE role = 'manager'")
    
    # Update role_permission.role (RBAC role defaults)
    op.execute("UPDATE role_permission SET role = 'admin' WHERE role = 'manager'")


def downgrade():
    """Rename 'admin' back to 'manager'."""
    op.execute("UPDATE membership SET role = 'manager' WHERE role = 'admin'")
    op.execute("UPDATE org_invite SET role = 'manager' WHERE role = 'admin'")
    op.execute("UPDATE role_permission SET role = 'manager' WHERE role = 'admin'")
