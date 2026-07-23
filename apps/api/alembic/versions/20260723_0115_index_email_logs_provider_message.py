"""Index tenant-scoped provider message lookups.

Revision ID: 20260723_0115
Revises: 20260723_0048
Create Date: 2026-07-23 01:15:00
"""

from alembic import op


revision = "20260723_0115"
down_revision = "20260723_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_email_logs_org_external_id",
        "email_logs",
        ["organization_id", "external_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_email_logs_org_external_id", table_name="email_logs")
