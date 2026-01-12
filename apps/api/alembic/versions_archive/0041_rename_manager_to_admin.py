"""Rename manager role to admin.

Revision ID: 0041_rename_manager_to_admin
Revises: 0040_permission_system
Create Date: 2024-12-20
"""

from alembic import op


revision = "0041_rename_manager_to_admin"
down_revision = "0040_permission_system"
branch_labels = None
depends_on = None


def upgrade():
    """Rename 'manager' to 'admin' in role columns."""
    # Update memberships.role (note: plural table name)
    op.execute("UPDATE memberships SET role = 'admin' WHERE role = 'manager'")

    # Update org_invites.role (note: plural table name)
    op.execute("UPDATE org_invites SET role = 'admin' WHERE role = 'manager'")

    # Update role_permissions.role (RBAC role defaults, note: plural)
    op.execute("UPDATE role_permissions SET role = 'admin' WHERE role = 'manager'")


def downgrade():
    """Rename 'admin' back to 'manager'."""
    op.execute("UPDATE memberships SET role = 'manager' WHERE role = 'admin'")
    op.execute("UPDATE org_invites SET role = 'manager' WHERE role = 'admin'")
    op.execute("UPDATE role_permissions SET role = 'manager' WHERE role = 'admin'")
