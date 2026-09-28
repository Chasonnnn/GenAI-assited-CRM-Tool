"""Copy intended parent edit overrides to the new stage-change permission.

change_intended_parent_status moves intended parent stage changes out of
edit_intended_parents. Role defaults grant both keys to the same roles. Stored
organization role overrides and user overrides of edit_intended_parents are copied
to the new key, so each member keeps the same stage-change access after upgrade.
Rows that already exist for the new key are not changed. Downgrade removes the new
key's rows, because the key does not exist before this revision.

Revision ID: 20260928_1200_ip_stage_permission
Revises: 20260926_1200_donor_match_stages
"""

from alembic import op

revision = "20260928_1200_ip_stage_permission"
down_revision = "20260926_1200_donor_match_stages"
branch_labels = None
depends_on = None

SOURCE_PERMISSION = "edit_intended_parents"
TARGET_PERMISSION = "change_intended_parent_status"


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.execute(
        f"""
        INSERT INTO role_permissions (organization_id, role, permission, is_granted)
        SELECT organization_id, role, '{TARGET_PERMISSION}', is_granted
        FROM role_permissions
        WHERE permission = '{SOURCE_PERMISSION}'
        ON CONFLICT ON CONSTRAINT uq_role_permissions_org_role_perm DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO user_permission_overrides
            (organization_id, user_id, permission, override_type)
        SELECT organization_id, user_id, '{TARGET_PERMISSION}', override_type
        FROM user_permission_overrides
        WHERE permission = '{SOURCE_PERMISSION}'
        ON CONFLICT ON CONSTRAINT uq_user_overrides_org_user_perm DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM role_permissions WHERE permission = '{TARGET_PERMISSION}'")
    op.execute(f"DELETE FROM user_permission_overrides WHERE permission = '{TARGET_PERMISSION}'")
