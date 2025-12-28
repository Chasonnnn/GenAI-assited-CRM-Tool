"""add_user_email_signature_fields

Revision ID: cbad3b9adf61
Revises: c1a2b3d4e5f6
Create Date: 2025-12-24 11:59:50.578412

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cbad3b9adf61"
down_revision: Union[str, Sequence[str], None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email signature fields to users table."""
    op.add_column(
        "users", sa.Column("signature_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_title", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_company", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_phone", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_email", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_address", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_website", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("signature_logo_url", sa.String(length=500), nullable=True)
    )
    op.add_column("users", sa.Column("signature_html", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove email signature fields from users table."""
    op.drop_column("users", "signature_html")
    op.drop_column("users", "signature_logo_url")
    op.drop_column("users", "signature_website")
    op.drop_column("users", "signature_address")
    op.drop_column("users", "signature_email")
    op.drop_column("users", "signature_phone")
    op.drop_column("users", "signature_company")
    op.drop_column("users", "signature_title")
    op.drop_column("users", "signature_name")
