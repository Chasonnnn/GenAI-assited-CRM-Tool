"""Add user signature override fields for name/title/phone/photo.

Users can override their profile info specifically for email signatures.
NULL = use profile default.

Revision ID: j1a2b3c4d5e6
Revises: i1a2b3c4d5e6
Create Date: 2026-01-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "j1a2b3c4d5e6"
down_revision = "c750cb72a8a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Signature override fields - NULL means use profile value
    op.add_column(
        "users",
        sa.Column(
            "signature_name",
            sa.String(255),
            nullable=True,
            comment="Override display_name in signature (NULL = use profile)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "signature_title",
            sa.String(100),
            nullable=True,
            comment="Override title in signature (NULL = use profile)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "signature_phone",
            sa.String(50),
            nullable=True,
            comment="Override phone in signature (NULL = use profile)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "signature_photo_url",
            sa.String(500),
            nullable=True,
            comment="Override avatar in signature (NULL = use profile)",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "signature_photo_url")
    op.drop_column("users", "signature_phone")
    op.drop_column("users", "signature_title")
    op.drop_column("users", "signature_name")
