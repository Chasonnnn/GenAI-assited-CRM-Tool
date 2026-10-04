"""Add the square organization logo, independent of email signature branding.

Revision ID: 20261004_1300_organization_logo
Revises: 20261004_1200_email_template_body_design
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_1300_organization_logo"
down_revision = "20261004_1200_email_template_body_design"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column("organizations", sa.Column("logo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_column("organizations", "logo_url")
