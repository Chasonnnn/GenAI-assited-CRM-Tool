"""Enforce audit logs as append-only.

Revision ID: c7e8f9a0b1c2
Revises: c6d2e3f4a5b6
Create Date: 2025-02-20 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c6d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_immutable_guard() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs are append-only';
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_guard();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_guard();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable_guard();")
